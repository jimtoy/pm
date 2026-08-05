import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { KanbanBoard } from "@/components/KanbanBoard";
import type { BoardData } from "@/lib/kanban";
import { UnauthorizedError } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    fetchBoard: vi.fn(),
    renameColumn: vi.fn(),
    createCard: vi.fn(),
    moveCard: vi.fn(),
    deleteCard: vi.fn(),
  };
});

import * as api from "@/lib/api";

const mockedApi = vi.mocked(api);

const buildBoard = (): BoardData => ({
  columns: [
    { id: "1", title: "Backlog", cardIds: ["1"] },
    { id: "2", title: "Discovery", cardIds: [] },
  ],
  cards: {
    "1": { id: "1", title: "Existing card", details: "Some details" },
  },
});

const getFirstColumn = () => screen.getAllByTestId(/^column-/)[0];

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.fetchBoard.mockResolvedValue(buildBoard());
});

describe("KanbanBoard", () => {
  it("loads the board from the API on mount", async () => {
    render(<KanbanBoard />);
    expect(await screen.findByText("Existing card")).toBeInTheDocument();
    expect(mockedApi.fetchBoard).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state before the board arrives", async () => {
    let resolveFetch: (value: BoardData) => void = () => {};
    mockedApi.fetchBoard.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      })
    );

    render(<KanbanBoard />);
    expect(screen.getByText(/loading board/i)).toBeInTheDocument();

    resolveFetch(buildBoard());
    await screen.findByText("Existing card");
  });

  it("shows a retry option when the initial load fails", async () => {
    mockedApi.fetchBoard.mockRejectedValueOnce(new Error("network down"));
    render(<KanbanBoard />);

    const retryButton = await screen.findByRole("button", { name: /try again/i });
    mockedApi.fetchBoard.mockResolvedValueOnce(buildBoard());
    await userEvent.click(retryButton);

    expect(await screen.findByText("Existing card")).toBeInTheDocument();
  });

  it("redirects when the initial board fetch is unauthorized", async () => {
    mockedApi.fetchBoard.mockRejectedValueOnce(new UnauthorizedError());
    const onSessionExpired = vi.fn();

    render(<KanbanBoard onSessionExpired={onSessionExpired} />);

    await waitFor(() => expect(onSessionExpired).toHaveBeenCalledTimes(1));
  });

  it("renames a column via the API when the title input loses focus", async () => {
    mockedApi.renameColumn.mockResolvedValue({
      id: "1",
      title: "Renamed",
      cardIds: ["1"],
    });

    render(<KanbanBoard />);
    await screen.findByText("Existing card");

    const input = within(getFirstColumn()).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "Renamed");
    await userEvent.tab();

    await waitFor(() =>
      expect(mockedApi.renameColumn).toHaveBeenCalledWith("1", "Renamed")
    );
  });

  it("does not call the API when a column title is unchanged", async () => {
    render(<KanbanBoard />);
    await screen.findByText("Existing card");

    const input = within(getFirstColumn()).getByLabelText("Column title");
    await userEvent.click(input);
    await userEvent.tab();

    expect(mockedApi.renameColumn).not.toHaveBeenCalled();
  });

  it("adds a card via the API and renders the server response", async () => {
    mockedApi.createCard.mockResolvedValue({
      id: "99",
      title: "New card",
      details: "Notes",
    });

    render(<KanbanBoard />);
    await screen.findByText("Existing card");
    const column = getFirstColumn();

    await userEvent.click(within(column).getByRole("button", { name: /add a card/i }));
    await userEvent.type(within(column).getByPlaceholderText(/card title/i), "New card");
    await userEvent.type(within(column).getByPlaceholderText(/details/i), "Notes");
    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    await waitFor(() =>
      expect(mockedApi.createCard).toHaveBeenCalledWith("1", "New card", "Notes")
    );
    expect(await within(column).findByText("New card")).toBeInTheDocument();
  });

  it("keeps the add-card form open with an error banner when creation fails", async () => {
    mockedApi.createCard.mockRejectedValue(new Error("boom"));

    render(<KanbanBoard />);
    await screen.findByText("Existing card");
    const column = getFirstColumn();

    await userEvent.click(within(column).getByRole("button", { name: /add a card/i }));
    await userEvent.type(within(column).getByPlaceholderText(/card title/i), "New card");
    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/couldn.t add/i);
    expect(within(column).getByPlaceholderText(/card title/i)).toHaveValue("New card");
  });

  it("deletes a card via the API", async () => {
    mockedApi.deleteCard.mockResolvedValue(undefined);

    render(<KanbanBoard />);
    await screen.findByText("Existing card");
    const column = getFirstColumn();

    await userEvent.click(
      within(column).getByRole("button", { name: /delete existing card/i })
    );

    await waitFor(() => expect(mockedApi.deleteCard).toHaveBeenCalledWith("1"));
    expect(within(column).queryByText("Existing card")).not.toBeInTheDocument();
  });

  it("reverts the board and shows an error banner when delete fails", async () => {
    mockedApi.deleteCard.mockRejectedValue(new Error("boom"));

    render(<KanbanBoard />);
    await screen.findByText("Existing card");
    const column = getFirstColumn();

    await userEvent.click(
      within(column).getByRole("button", { name: /delete existing card/i })
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(/something went wrong/i);
    expect(within(column).getByText("Existing card")).toBeInTheDocument();
  });

  it("redirects on session expiry when a mutation returns unauthorized", async () => {
    mockedApi.deleteCard.mockRejectedValue(new UnauthorizedError());
    const onSessionExpired = vi.fn();

    render(<KanbanBoard onSessionExpired={onSessionExpired} />);
    await screen.findByText("Existing card");
    const column = getFirstColumn();

    await userEvent.click(
      within(column).getByRole("button", { name: /delete existing card/i })
    );

    await waitFor(() => expect(onSessionExpired).toHaveBeenCalledTimes(1));
  });
});
