import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import LoginPage from "@/app/login/page";

const replace = vi.fn();
const router = { replace };

vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));

describe("LoginPage", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    replace.mockClear();
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  it("redirects to / when already authenticated", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ authenticated: true }),
    });

    render(<LoginPage />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
  });

  it("shows an error for invalid credentials", async () => {
    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => ({ authenticated: false }) })
      .mockResolvedValueOnce({ ok: false });

    render(<LoginPage />);

    const usernameInput = await screen.findByLabelText("Username");
    await userEvent.type(usernameInput, "user");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/invalid username or password/i)).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("redirects to / after a successful login", async () => {
    fetchMock
      .mockResolvedValueOnce({ ok: true, json: async () => ({ authenticated: false }) })
      .mockResolvedValueOnce({ ok: true });

    render(<LoginPage />);

    const usernameInput = await screen.findByLabelText("Username");
    await userEvent.type(usernameInput, "user");
    await userEvent.type(screen.getByLabelText("Password"), "password");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
  });
});
