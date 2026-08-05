import type { BoardData, Card, Column } from "@/lib/kanban";

export class UnauthorizedError extends Error {
  constructor() {
    super("Not authenticated");
    this.name = "UnauthorizedError";
  }
}

const request = async (path: string, init?: RequestInit): Promise<Response> => {
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
  return response.json();
};

export const renameColumn = async (columnId: string, title: string): Promise<Column> => {
  const response = await request(`/api/columns/${columnId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
  return response.json();
};

export const createCard = async (
  columnId: string,
  title: string,
  details: string
): Promise<Card> => {
  const response = await request("/api/cards", {
    method: "POST",
    body: JSON.stringify({ column_id: columnId, title, details }),
  });
  return response.json();
};

export const moveCard = async (
  cardId: string,
  columnId: string,
  position: number
): Promise<Card> => {
  const response = await request(`/api/cards/${cardId}`, {
    method: "PATCH",
    body: JSON.stringify({ column_id: columnId, position }),
  });
  return response.json();
};

export const deleteCard = async (cardId: string): Promise<void> => {
  await request(`/api/cards/${cardId}`, { method: "DELETE" });
};
