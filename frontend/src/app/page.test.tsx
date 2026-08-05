import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import Home from "@/app/page";

const replace = vi.fn();
const router = { replace };

vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));

describe("Home", () => {
  beforeEach(() => {
    replace.mockClear();
    vi.stubGlobal("fetch", vi.fn());
  });

  it("redirects to /login when not authenticated", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ authenticated: false }),
    });

    render(<Home />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText("Kanban Studio")).not.toBeInTheDocument();
  });

  it("renders the board when authenticated", async () => {
    (fetch as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ authenticated: true }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ columns: [], cards: {} }),
      });

    render(<Home />);

    expect(await screen.findByText("Kanban Studio")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
