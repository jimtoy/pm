import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { KanbanColumn } from "@/components/KanbanColumn";

const renderColumn = (title: string, onRename = vi.fn()) => {
  const props = {
    column: { id: "col-1", title, cardIds: [] },
    cards: [],
    onRename,
    onAddCard: vi.fn(),
    onDeleteCard: vi.fn(),
  };
  const { rerender } = render(<KanbanColumn {...props} />);
  return {
    onRename,
    input: screen.getByLabelText("Column title"),
    // Simulates a background board refetch (e.g. triggered by the AI chat sidebar).
    refresh: (nextTitle: string) =>
      rerender(<KanbanColumn {...props} column={{ ...props.column, title: nextTitle }} />),
  };
};

describe("KanbanColumn", () => {
  it("does not overwrite an in-progress title edit when the column prop refreshes", async () => {
    const user = userEvent.setup();
    const { input, onRename, refresh } = renderColumn("Backlog");

    await user.click(input);
    await user.clear(input);
    await user.type(input, "Work in progress");

    refresh("Backlog");
    expect(input).toHaveValue("Work in progress");

    await user.tab();
    expect(onRename).toHaveBeenCalledWith("col-1", "Work in progress");
  });

  it("still syncs the displayed title from props when the input isn't focused", () => {
    const { input, refresh } = renderColumn("Backlog");

    refresh("Renamed elsewhere");

    expect(input).toHaveValue("Renamed elsewhere");
  });
});
