import type { BoardData, Card, Column } from "@/lib/kanban";

export class UnauthorizedError extends Error {
  constructor() {
    super("Not authenticated");
    this.name = "UnauthorizedError";
  }
}

// The backend's `columns` and `cards` tables are separate SQL tables, each
// auto-incrementing independently — a column and a card can share the same
// raw numeric id. dnd-kit and moveCard() require every id in the board to be
// globally unique, so the API client prefixes ids at the boundary (mirroring
// the old in-memory demo's col-*/card-* convention) and strips them back off
// before talking to the backend. Nothing above this layer ever sees a raw id.
const toColumnId = (rawId: string): string => `col-${rawId}`;
const toCardId = (rawId: string): string => `card-${rawId}`;
const fromColumnId = (columnId: string): string => columnId.replace(/^col-/, "");
const fromCardId = (cardId: string): string => cardId.replace(/^card-/, "");

type RawCard = { id: string; title: string; details: string };
type RawColumn = { id: string; title: string; cardIds: string[] };
type RawBoardData = { columns: RawColumn[]; cards: Record<string, RawCard> };

export const request = async (path: string, init?: RequestInit): Promise<Response> => {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (response.status === 401) {
    throw new UnauthorizedError();
  }
  if (!response.ok) {
    throw new Error(`Request to ${path} failed with status ${response.status}`);
  }
  return response;
};

export const fetchBoard = async (): Promise<BoardData> => {
  const response = await request("/api/board");
  const raw: RawBoardData = await response.json();

  const cards: Record<string, Card> = {};
  for (const card of Object.values(raw.cards)) {
    const id = toCardId(card.id);
    cards[id] = { id, title: card.title, details: card.details };
  }

  const columns: Column[] = raw.columns.map((column) => ({
    id: toColumnId(column.id),
    title: column.title,
    cardIds: column.cardIds.map(toCardId),
  }));

  return { columns, cards };
};

export const renameColumn = async (columnId: string, title: string): Promise<Column> => {
  const response = await request(`/api/columns/${fromColumnId(columnId)}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
  const raw: RawColumn = await response.json();
  return { id: toColumnId(raw.id), title: raw.title, cardIds: raw.cardIds.map(toCardId) };
};

export const createCard = async (
  columnId: string,
  title: string,
  details: string
): Promise<Card> => {
  const response = await request("/api/cards", {
    method: "POST",
    body: JSON.stringify({ column_id: fromColumnId(columnId), title, details }),
  });
  const raw: RawCard = await response.json();
  return { id: toCardId(raw.id), title: raw.title, details: raw.details };
};

export const moveCard = async (
  cardId: string,
  columnId: string,
  position: number
): Promise<Card> => {
  const response = await request(`/api/cards/${fromCardId(cardId)}`, {
    method: "PATCH",
    body: JSON.stringify({ column_id: fromColumnId(columnId), position }),
  });
  const raw: RawCard = await response.json();
  return { id: toCardId(raw.id), title: raw.title, details: raw.details };
};

export const deleteCard = async (cardId: string): Promise<void> => {
  await request(`/api/cards/${fromCardId(cardId)}`, { method: "DELETE" });
};
