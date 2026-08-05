# High level steps for project

See root `AGENTS.md` for business requirements, technical decisions, and coding standards. This document breaks the work into parts, each with a checklist, tests, and success criteria. Work proceeds part by part; each part should be complete (tests passing) before starting the next, unless the user directs otherwise.

---

## Part 1: Plan

- [x] Enrich this document with substeps, tests, and success criteria per part
- [x] Create `frontend/AGENTS.md` describing the existing frontend code
- [ ] User checks and approves the plan

**Success criteria:** user has explicitly signed off on this document before Part 2 begins.

---

## Part 2: Scaffolding

- [x] Create `backend/` FastAPI app skeleton using `uv` for dependency management (`pyproject.toml`, `uv.lock`)
- [x] Add a single `GET /api/hello` route returning a small JSON payload (e.g. `{"message": "Hello from FastAPI"}`)
- [x] Serve a static `index.html` (placeholder, not yet the real frontend) from FastAPI at `/`, which calls `/api/hello` via fetch on load and displays the result
- [x] Write a `Dockerfile` (single-stage for now; build context is the repo root so `frontend/` can be added in Part 3) and `docker-compose.yml` that runs the FastAPI app
- [x] Write `scripts/start.sh` / `stop.sh` (Mac/Linux) and `scripts/start.ps1` / `stop.ps1` (PC), wrapping `docker compose up`/`down`
- [x] Update `backend/AGENTS.md` and `scripts/AGENTS.md` with real descriptions replacing the placeholder text
- [x] Add root `.env.example` documenting `OPENROUTER_API_KEY` — note: no `.env` file actually exists in the repo yet (despite root `AGENTS.md` assuming one); `docker-compose.yml` treats it as optional (`required: false`) so `docker compose up` works until Part 8 needs the real key

**Tests:**
- Backend: a `pytest` test hitting `/api/hello` with FastAPI's `TestClient`, asserting 200 and expected JSON shape
- Manual/script-level: starting the container and curling `/` and `/api/hello` returns expected results

**Success criteria:** running the start script boots a Docker container; visiting `http://localhost:<port>/` in a browser shows the placeholder page successfully displaying data fetched from the API; stop script cleanly stops the container; `pytest` passes.

---

## Part 3: Add in Frontend

- [x] Configure Next.js for static export (`output: "export"` in `next.config.ts`)
- [x] Update FastAPI to serve the exported static frontend build (`frontend/out`, copied to `backend`'s static dir at Docker build time) at `/` — `STATIC_DIR` is now configurable via env var
- [x] Update Docker build to be multi-stage: `node` stage builds the Next.js static export, copied into the final `uv`/Python image
- [x] Start/stop scripts unchanged (still just wrap `docker compose`); no changes needed
- [x] Confirmed the existing Kanban demo (in-memory, no backend calls yet) renders correctly when served this way

**Tests:**
- [x] Existing frontend unit tests (Vitest) and e2e tests (Playwright, dev-mode) continue to pass — verified: 6/6 unit, 3/3 e2e
- [x] Added e2e tests (`tests/kanban.spec.ts`, run via `npm run test:e2e`), which build and run the real Docker image and assert the Kanban board renders seed data and drag-and-drop works when served by FastAPI — verified: 3/3 passing
- [x] Backend test decoupled from the real frontend build (tests the static-mount mechanism generically via a fixture dir + `STATIC_DIR` env var, rather than depending on frontend content) — verified: 2/2 passing
- [x] Manually verified via `curl` that a JS chunk referenced by the built page (`/_next/static/chunks/...`) is served correctly (200) through FastAPI, not just the HTML shell

**Success criteria:** met. `docker compose up` (via `scripts/start.sh`) serves the actual Kanban UI at `/`; drag-and-drop and card editing work (still in-memory only); all frontend and backend test suites pass.

**Note:** couldn't do a live interactive browser check (Claude-in-Chrome extension not connected in this session) — verification relied on Playwright automation against the real Docker container plus manual curl checks instead.

---

## Part 4: Add in a fake user sign in experience

- [x] Add a login page/form requiring username `user` / password `password` (hardcoded per AGENTS.md)
- [x] On success, set a session (simple signed cookie or server-side session token — no need for JWT complexity or expiry logic given MVP scope) so refreshing stays logged in
- [x] Redirect unauthenticated requests for the Kanban view to the login page; redirect authenticated users hitting login to the board
- [x] Add a logout action that clears the session and redirects to login
- [x] Backend: add `/api/login`, `/api/logout`, and session-check middleware/dependency protecting Kanban-related routes (routes don't exist yet until Part 6, but the auth dependency should exist now for reuse)

**Tests:**
- [x] Backend unit tests: correct credentials succeed and set a session cookie; incorrect credentials return 401; protected route without session returns 401/redirect; logout clears session — verified: 8/8 passing (`backend/tests/test_auth.py` + `test_hello.py`)
- [x] Frontend/e2e: cannot reach board content without logging in; login with correct credentials shows the board; wrong credentials shows an error; logout returns to login and re-blocks access — verified: 8/8 Playwright e2e passing against the real Docker build; 11/11 Vitest unit tests passing

**Success criteria:** met. A fresh browser session is forced to log in before seeing the Kanban board; logout works; all new tests pass alongside existing ones.

**Note:** manual live-browser click-through was attempted via the Claude-in-Chrome extension but blocked by a password-manager autofill popup stealing tab focus (unrelated to the app). Verification instead relied on the full automated suite above plus a partial manual check (fresh-tab unauthenticated redirect to `/login`, and logout redirecting back to `/login`), both confirmed working.

**Follow-up review (after Part 6).** Re-verified against the running Docker build; no regressions (11/11 Vitest, 8/8 Playwright, backend green). Findings:

- *Test gap closed.* Auth was only *proven* for `GET /api/board` — the other four board routes relied on the router-level `dependencies=[Depends(require_auth)]` with nothing asserting it, so the protection could be silently lost. Added parametrized coverage for all five routes plus a test that rejected requests leave the board unmutated. Confirmed load-bearing: removing the dependency fails exactly those 6 tests.
- *Auth itself is sound.* Manually probed every route unauthenticated (all 401, nothing mutated). Session cookie is signed, `httponly`, `samesite=lax`, and correctly expired on logout.
- *Redirect is client-side by design.* Because the frontend is a static export, Next.js middleware does not run and `GET /` returns 200 with the HTML shell to anonymous users — the only "Kanban Studio" text in it is the `<title>` tag, not board content, so the e2e assertion is valid. The real security boundary is the API, which is correctly enforced. Worth stating plainly so "cannot reach board content without logging in" is not read as server-side route protection.
- *Seed data is currently public.* The demo cards are compiled into a JS chunk that anyone can fetch without a session. This is inherent to Part 4's in-memory demo and resolves itself in Part 7, when board data moves behind `GET /api/board`.
- *`SESSION_SECRET` is unset in Docker*, so the hardcoded default is used. Not worth fixing for this MVP: the credentials are themselves hardcoded and displayed on the login page, so forging a cookie gains nothing over logging in.

---

## Part 5: Database modeling

- [x] Propose a schema (tables: `users`, `boards`, `columns`, `cards`, with foreign keys and ordering columns for column/card sequence) even though MVP only needs one user and one board — schema should support multiple users/boards for the future per AGENTS.md limitations
- [x] Save the schema as JSON (e.g. `docs/schema.json`) describing tables, columns, types, and relationships
- [x] Write `docs/DATABASE.md` documenting the approach: SQLite, file location, migration/creation-on-first-run strategy, how ordering of columns/cards is stored (e.g. integer `position` field vs array-of-ids)
- [x] Get explicit user sign-off on the schema before implementing it in Part 6

**Tests:** none (design-only part), but schema JSON should be valid JSON (lint-checked).

**Success criteria:** user has reviewed and approved `docs/schema.json` and `docs/DATABASE.md`.

---

## Part 6: Backend

- [x] Implement SQLite database using the approved schema; create the DB file and tables automatically if the file doesn't exist on startup
- [x] Add API routes (all behind the auth dependency from Part 4): `GET /api/board` (fetch current user's board with columns+cards), `PATCH /api/columns/{id}` (rename), `POST /api/cards`, `PATCH /api/cards/{id}` (edit/move), `DELETE /api/cards/{id}`
- [x] Seed the database with the same demo data currently hardcoded in `frontend/src/lib/kanban.ts` on first run, so behavior matches today's demo
- [x] Backend unit tests using a temporary/in-memory SQLite DB per test (not the real dev DB)

**Tests:**
- [x] CRUD coverage: create card, rename column, move card between columns, move card within a column (reorder), delete card, fetch full board — verified: `backend/tests/test_board.py`
- [x] Edge cases: fetching board with no data yet (first run auto-seeds), invalid ids return 404, unauthenticated requests return 401
- [x] DB-creation test: deleting the DB file and starting the app recreates it with seed data; a second startup against an existing DB does not re-seed over edits
- [x] Full suite: 22/22 passing (`uv run pytest`)
- [x] Schema conformance: `docs/schema.json` diffed programmatically against the SQLite tables the code actually creates — all tables, column types, nullability, primary keys, foreign keys, and the `users.username` unique index match

**Success criteria:** met. All backend routes work correctly via `pytest` + `TestClient` against a real (temp) SQLite file, matching the schema from Part 5. Also verified against the real Docker build: renamed a column and added a card, ran `scripts/stop.sh` + `scripts/start.sh`, and confirmed both changes persisted; `docker compose down -v` resets to seed data.

**Two issues found in a follow-up review and fixed:**
1. *Data loss across restarts.* `docker-compose.yml` had no volume for `/app/data`, so the SQLite file lived in the container's writable layer and was destroyed by `stop.sh` (`docker compose down`) — every stop/start silently reset the board. Fixed with an `app-data` named volume; verified by round-tripping real edits through a full stop/start cycle.
2. *Untested startup path + per-request waste.* `init_db()` was being called from the per-request `get_db()` dependency, so the schema script ran on every API request, and the documented "created on startup" path was never exercised by tests (a bare `TestClient(app)` does not run lifespan events, which was masking this). Removed the per-request call; tests now use `with TestClient(app)` so they cover the real production path, plus a `conftest.py` autouse fixture guarantees no test can touch the dev DB.

**Note:** the local `uv` CLI wasn't on PATH in this environment, so tests were run inside a throwaway `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` container (`docker run -v backend:/app ... uv run pytest`) rather than natively; a stale `.venv` left over from a previous container build (broken interpreter symlink) was removed and resynced first.

---

## Part 7: Frontend + Backend

- [x] Replace in-memory `useState`/`initialData` in `KanbanBoard.tsx` with data fetched from `/api/board` on load
- [x] Wire `onRename`, `onAddCard`, `onDeleteCard`, and drag-and-drop move handlers to call the corresponding API routes, updating local state optimistically or after response
- [x] Handle loading and error states (e.g. API unreachable, session expired mid-use redirects to login)
- [x] Keep `src/lib/kanban.ts`'s pure logic (like `moveCard`) reusable for optimistic local updates before/independent of server confirmation

**Implementation notes:**
- New `frontend/src/lib/api.ts` is the API client (`fetchBoard`, `renameColumn`, `createCard`, `moveCard`, `deleteCard`), throwing `UnauthorizedError` on 401 so callers can redirect rather than show an error banner.
- Rename commits on blur/Enter (not per keystroke) via local draft state in `KanbanColumn`, to avoid a PATCH per character typed. Add-card is non-optimistic (awaits the server response, since the id is server-assigned); rename/move/delete are optimistic with revert-on-failure.
- `initialData` and `createId` were deleted from `kanban.ts` — dead code once the board is server-backed; `moveCard` (the pure reducer) stays and is reused for the optimistic drag-and-drop update.
- `KanbanBoard`/`page.tsx` gained an `onSessionExpired` callback (reuses the existing logout-and-redirect handler) so a 401 from any board API call sends the user back to `/login`.

**Tests:**
- [x] Frontend unit tests: `KanbanBoard.test.tsx` mocks `@/lib/api` and asserts each action (rename, add, delete) calls the right API function with the right args, plus loading/error/session-expiry states and optimistic-revert-on-failure — 19/19 Vitest passing
- [x] E2E (Playwright): full flow — log in, add a card, rename a column, drag a card to another column, delete a card, reload the page, and confirm all changes persisted against the real backend — 7/7 passing
- [x] Backend tests from Part 6 still passing — 27/27

**Success criteria:** met. Reloading the browser preserves all board changes (verified via the e2e reload assertions, and separately via raw `curl` against a running container). E2E exercises the full persistent loop against the real backend with a throwaway DB, not mocks.

**The two carried-over items from the Part 4/6 review, and what actually shipped:**
- *Throwaway e2e DB:* added `docker-compose.e2e.yml`, an override that replaces the `app-data` named volume with an anonymous one at the same mount point (verified via `docker compose config` that this fully replaces rather than merges with the base volume). `playwright.config.ts`'s `webServer.command` now runs against both compose files with `--force-recreate`.
- *Selectors:* e2e now resolves each column's real backend-assigned testid once per test, before any mutation (see below for why), instead of hardcoding the old frontend ids.

**Three bugs found while getting e2e green, worth recording:**
1. *Dynamic locators silently re-targeted after a mutation.* The first draft of the persistence e2e test located columns with `.filter({ hasText: "<seed card title>" })`. Playwright locators are lazy/re-evaluated on each use, so once the drag step moved that seed card into a different column, the *same* locator started resolving to the new column instead of the original one — a later step then tried to click a button that didn't exist there and timed out. Fixed by resolving each column's concrete `data-testid` once, up front, and building fixed `getByTestId(...)` locators from it for the rest of the test.
2. *`getByRole` ambiguity from dnd-kit.* `useSortable` spreads `role="button"` onto the card's own `<article>`, and Chromium's accessible-name algorithm folds a nested button's label into its ancestor's computed name — so `getByRole("button", { name: /delete .../i })` matched both the card and the delete button ("strict mode violation"). Switched to `getByLabel(...)`, which only honors explicit `aria-label` and ignores the content-fallback that caused the collision.
3. *`reuseExistingServer: false` fails before `globalSetup` runs.* Tried adding a Playwright `globalSetup` to force-clear any stale container left by an interrupted previous run. Proved empirically (by making it throw unconditionally) that Playwright's port-conflict preflight check runs *before* `globalSetup` when `reuseExistingServer` is false — so a leftover container from a prior run, or from `scripts/start.sh`, made every subsequent `npm run test:e2e` fail immediately with no way for `globalSetup` to fix it in time. Replaced it with `frontend/tests/run-e2e.mjs`, a small Node wrapper (cross-platform per `AGENTS.md`'s Mac/Linux/PC requirement, not a shell one-liner) that tears down any existing container as a step *before* invoking `playwright test` at all. `package.json`'s `test:e2e` now points at this wrapper. Verified self-healing by deliberately leaving a container running from `scripts/start.sh` and confirming `npm run test:e2e` cleans up and passes without manual intervention, and confirmed via two consecutive full runs that state doesn't leak between them.

**Post-merge user report, investigated after the fact: cards visually "popping up out of the div" during a cross-column drag.** Two real bugs, found by scripting real Playwright drags against the running Docker build and screenshotting every ~15-20ms around the drop (manual browser automation couldn't reproduce it at all — the extension's synthetic drag doesn't send enough intermediate pointer events to clear dnd-kit's activation threshold):
1. `DragOverlay`'s ghost card was hardcoded to `w-[260px]` while a column is only ~227px wide (~195px of content) — the ghost was structurally wider than a single column, so it visibly overlapped the neighboring column for the whole drag. Fixed by sizing the overlay from `event.active.rect.current.initial.width` (the real dragged card's measured width) instead of a guessed constant.
2. Even after that fix, the overlay's default drop-settle animation still visibly slid across existing cards *within* its own destination column for ~150-300ms after release, reading as the same "popping up" glitch. Fixed with `<DragOverlay dropAnimation={null}>` — the overlay now disappears the instant the mouse releases, with the real card already in place underneath.

**A third, more serious bug surfaced investigating "still happening, only in Backlog":** `board_columns` and `cards` are separate SQL tables that each auto-increment independently, so a column and a card can share a raw numeric id — e.g. seed data has "In Progress" as column `3` and "Prototype analytics view" as card `3`. `moveCard()` (`kanban.ts`) and dnd-kit both require every id in the board to be globally unique; without that, `findColumnId` misread the card as already living in "In Progress" and `moveCard` silently no-op'd instead of moving it — no error, the card just didn't go anywhere, which is what actually explained the "still happening" report (Backlog is column `1`, colliding with card `1`, one of the most-dragged cards, so it surfaced there most often even though the bug isn't Backlog-specific). Confirmed with a standalone repro (`findColumnId` returning `"3"` instead of the correct `"2"`) before touching any code. Fixed by restoring the old in-memory demo's id-prefixing convention (`col-<id>` / `card-<id>`) inside `frontend/src/lib/api.ts`, at the API boundary — nothing above that layer ever sees a raw, unprefixed id again. Added `frontend/src/lib/api.test.ts` (pins the prefixing behavior directly against a raw response with a deliberate id collision) and a dedicated e2e regression test in `kanban.spec.ts`; verified both fail against the pre-fix code and pass after.

---

## Part 8: AI connectivity

- [ ] Add OpenRouter client setup in the backend (reading `OPENROUTER_API_KEY` from `.env`), using `openai/gpt-oss-120b`
- [ ] Add a minimal `/api/ai/ping` (or similar) route that sends a "what is 2+2?" prompt and returns the model's response, to prove connectivity end-to-end
- [ ] Handle and surface API errors (missing key, network failure, bad response) clearly rather than silently failing

**Tests:**
- Backend test that calls the real OpenRouter API (may be a manual/integration test rather than part of the default fast test suite, since it costs money/network) and asserts a sane response containing "4"
- Unit test with a mocked OpenRouter client verifying request shape (model name, prompt) and error handling paths

**Success criteria:** hitting the ping route returns a real AI-generated answer confirming "4" (or similar), proving the OpenRouter integration is correctly configured.

---

## Part 9: Structured AI chat with Kanban context

- [ ] Extend the AI route to accept a user message + conversation history, and always include the current board's JSON as context in the prompt/system message
- [ ] Use Structured Outputs (OpenRouter/OpenAI-compatible `response_format` with a JSON schema) so the model returns `{ reply: string, board_update: <optional patch/replacement> | null }`
- [ ] Define the `board_update` schema (decide during implementation: full board replace vs. targeted operations like "move card X to column Y" — favor the simplest approach that keeps the model's job easy and validates cleanly against the DB schema)
- [ ] If `board_update` is present, apply it to the database using the same logic/routes as Part 6 (reuse, don't duplicate)
- [ ] Persist conversation history (in DB or in-memory per session — decide based on simplicity; DB preferred for consistency with "survives refresh" expectations)

**Tests:**
- Unit tests with a mocked AI client: given a canned structured response, confirm the board is updated correctly in the DB and the reply text is returned to the caller
- Integration test (real API call, manual/tagged as slow): ask the AI to "move the card about X to Done" against a known seeded board and confirm the resulting DB state
- Validation test: malformed/unexpected structured output from the model is handled gracefully (no crash, clear error)

**Success criteria:** sending a natural-language instruction that implies a board change results in the correct DB update and a sensible chat reply, verified by both a mocked unit test and at least one real end-to-end call.

---

## Part 10: AI chat sidebar UI

- [ ] Add a sidebar component with a chat interface (message list + input) styled per the brand palette in root `AGENTS.md`
- [ ] Wire it to the Part 9 chat route, sending user messages and conversation history, displaying the AI's reply
- [ ] When a response includes a board update, refresh the Kanban board view automatically (refetch from `/api/board` or apply the returned patch directly) without a full page reload
- [ ] Handle loading/error states in the chat UI (e.g. "thinking...", API failure message)

**Tests:**
- Frontend unit tests: chat component sends correct payload, renders messages, triggers board refresh callback when a board update is present
- E2E (Playwright): send a chat message that requests a card move via the real (or a test-mode) AI backend, confirm the chat shows a reply and the Kanban board visibly updates without manual refresh

**Success criteria:** user can ask the AI in the sidebar to make a change to the Kanban board, see a conversational reply, and see the board update live in the UI — completing the full MVP described in root `AGENTS.md`.
