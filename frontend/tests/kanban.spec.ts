import { expect, test, type Page } from "@playwright/test";

const authenticate = async (page: Page) => {
  const response = await page.request.post("/api/login", {
    data: { username: "user", password: "password" },
  });
  expect(response.ok()).toBeTruthy();
};

test("redirects to /login when not authenticated", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expect(page.getByText("Kanban Studio")).toHaveCount(0);
});

test("shows an error for invalid credentials", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("wrong-password");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByText(/invalid username or password/i)).toBeVisible();
  await expect(page).toHaveURL(/\/login/);
});

test("logs in with correct credentials and shows the board", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/^(?!.*\/login).*$/);
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
});

test("already-authenticated users hitting /login are redirected to the board", async ({ page }) => {
  await authenticate(page);
  await page.goto("/login");
  await expect(page).toHaveURL(/^(?!.*\/login).*$/);
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
});

test("logs out and re-blocks access to the board", async ({ page }) => {
  await authenticate(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();

  await page.getByRole("button", { name: /log out/i }).click();
  await expect(page).toHaveURL(/\/login/);

  await page.goto("/");
  await expect(page).toHaveURL(/\/login/);
});

test("kanban board renders with seed data fetched from the backend", async ({ page }) => {
  await authenticate(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
  await expect(page.getByText("Align roadmap themes")).toBeVisible();
});

test("add, rename, move, and delete all persist across a reload", async ({ page }) => {
  await authenticate(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();

  // Resolve each column's real (backend-assigned) testid once, up front, by
  // its known seed content. Locators built from these ids stay pinned to the
  // right column even after cards move between columns later in this test —
  // a content-based filter would silently re-target once the card it matches
  // on relocates.
  const columnTestId = async (seedCardText: string) =>
    page.locator('[data-testid^="column-"]').filter({ hasText: seedCardText }).getAttribute(
      "data-testid"
    );

  const backlogColumn = page.getByTestId((await columnTestId("Align roadmap themes"))!);
  const discoveryColumn = page.getByTestId(
    (await columnTestId("Prototype analytics view"))!
  );
  const reviewColumn = page.getByTestId((await columnTestId("QA micro-interactions"))!);

  // Add a card.
  await backlogColumn.getByRole("button", { name: /add a card/i }).click();
  await backlogColumn.getByPlaceholder("Card title").fill("Playwright card");
  await backlogColumn.getByPlaceholder("Details").fill("Added via e2e.");
  await backlogColumn.getByRole("button", { name: /add card/i }).click();
  await expect(backlogColumn.getByText("Playwright card")).toBeVisible();

  // Rename a column (commits on blur).
  const discoveryTitleInput = discoveryColumn.getByLabel("Column title");
  await discoveryTitleInput.fill("Renamed via e2e");
  await discoveryTitleInput.blur();
  await expect(discoveryTitleInput).toHaveValue("Renamed via e2e");

  // Move a card from Backlog into Review via drag and drop.
  const movedCard = page.getByText("Align roadmap themes");
  const cardBox = await movedCard.boundingBox();
  const columnBox = await reviewColumn.boundingBox();
  if (!cardBox || !columnBox) {
    throw new Error("Unable to resolve drag coordinates.");
  }
  await page.mouse.move(cardBox.x + cardBox.width / 2, cardBox.y + cardBox.height / 2);
  await page.mouse.down();
  await page.mouse.move(columnBox.x + columnBox.width / 2, columnBox.y + 120, {
    steps: 12,
  });
  await page.mouse.up();
  await expect(reviewColumn.getByText("Align roadmap themes")).toBeVisible();

  // Delete a card. dnd-kit gives the card article itself role="button" too, so
  // getByRole would match both it and the delete button; getByLabel targets
  // only the element with the explicit aria-label.
  await backlogColumn.getByLabel("Delete Gather customer signals").click();
  await expect(page.getByText("Gather customer signals")).toHaveCount(0);

  // Reload and confirm every change came from the backend, not local state.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();

  // These locators are pinned to real backend ids (via getByTestId), so they
  // remain valid after the reload without re-deriving anything.
  await expect(backlogColumn.getByText("Playwright card")).toBeVisible();
  await expect(reviewColumn.getByText("Align roadmap themes")).toBeVisible();
  await expect(page.getByText("Gather customer signals")).toHaveCount(0);
  await expect(discoveryColumn.getByLabel("Column title")).toHaveValue("Renamed via e2e");
});
