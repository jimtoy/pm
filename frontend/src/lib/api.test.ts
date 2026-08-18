import { vi } from "vitest";
import { createCard, deleteCard, fetchBoard, moveCard, renameColumn } from "@/lib/api";

// board_columns and cards are separate SQL tables that each auto-increment
// independently, so a column and a card can share a raw numeric id (column
// "3" and card "3" both exist below). moveCard()/dnd-kit require every id in
// the board to be globally unique, so api.ts must prefix ids at the boundary
// — these tests pin that behavior directly, since the failure mode (a card
// silently refusing to move) has no error message and is easy to reintroduce.
const rawBoard = {
  columns: [
    { id: "1", title: "Backlog", cardIds: ["1", "2"] },
    { id: "2", title: "Discovery", cardIds: ["3"] },
    { id: "3", title: "In Progress", cardIds: ["4", "5"] },
  ],
  cards: {
    "1": { id: "1", title: "Align roadmap themes", details: "" },
    "2": { id: "2", title: "Gather customer signals", details: "" },
    "3": { id: "3", title: "Prototype analytics view", details: "" },
    "4": { id: "4", title: "Refine status language", details: "" },
    "5": { id: "5", title: "Design card layout", details: "" },
  },
};

const jsonResponse = (body: unknown) =>
  ({ ok: true, status: 200, json: async () => body }) as Response;

const mockFetch = () => fetch as ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

describe("fetchBoard", () => {
  it("prefixes column and card ids so they never collide", async () => {
    mockFetch().mockResolvedValueOnce(jsonResponse(rawBoard));

    const board = await fetchBoard();

    expect(board.columns.map((c) => c.id)).toEqual(["col-1", "col-2", "col-3"]);
    expect(board.columns[1].cardIds).toEqual(["card-3"]);
    expect(Object.keys(board.cards)).toEqual(["card-1", "card-2", "card-3", "card-4", "card-5"]);
    expect(board.cards["card-3"]).toEqual({
      id: "card-3",
      title: "Prototype analytics view",
      details: "",
    });

    // The specific case that was silently broken: a card and an unrelated
    // column sharing a raw id must resolve to distinct prefixed ids.
    expect(board.cards["card-3"].id).not.toBe(board.columns[2].id);
  });
});

describe("mutation functions strip prefixes before calling the API", () => {
  it("renameColumn", async () => {
    mockFetch().mockResolvedValueOnce(
      jsonResponse({ id: "3", title: "Renamed", cardIds: ["4", "5"] })
    );

    await renameColumn("col-3", "Renamed");

    expect(mockFetch()).toHaveBeenCalledWith(
      "/api/columns/3",
      expect.objectContaining({ method: "PATCH" })
    );
  });

  it("createCard", async () => {
    mockFetch().mockResolvedValueOnce(jsonResponse({ id: "9", title: "New", details: "" }));

    const card = await createCard("col-3", "New", "");

    const [, init] = mockFetch().mock.calls[0];
    expect(JSON.parse(init.body).column_id).toBe("3");
    expect(card.id).toBe("card-9");
  });

  it("moveCard", async () => {
    mockFetch().mockResolvedValueOnce(jsonResponse({ id: "3", title: "x", details: "" }));

    await moveCard("card-3", "col-1", 0);

    const [url, init] = mockFetch().mock.calls[0];
    expect(url).toBe("/api/cards/3");
    expect(JSON.parse(init.body).column_id).toBe("1");
  });

  it("deleteCard", async () => {
    mockFetch().mockResolvedValueOnce(jsonResponse({}));

    await deleteCard("card-3");

    expect(mockFetch()).toHaveBeenCalledWith(
      "/api/cards/3",
      expect.objectContaining({ method: "DELETE" })
    );
  });
});
