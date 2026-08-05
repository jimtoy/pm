"use client";

import { useEffect, useMemo, useState } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import { moveCard, type BoardData } from "@/lib/kanban";
import {
  fetchBoard,
  renameColumn as renameColumnApi,
  createCard as createCardApi,
  moveCard as moveCardApi,
  deleteCard as deleteCardApi,
  UnauthorizedError,
} from "@/lib/api";

type KanbanBoardProps = {
  onLogout?: () => void;
  onSessionExpired?: () => void;
};

type LoadState = "loading" | "ready" | "error";

export const KanbanBoard = ({ onLogout, onSessionExpired }: KanbanBoardProps) => {
  const [board, setBoard] = useState<BoardData | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [actionError, setActionError] = useState<string | null>(null);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  );

  const loadBoard = () => {
    setLoadState("loading");
    fetchBoard()
      .then((data) => {
        setBoard(data);
        setLoadState("ready");
      })
      .catch((error) => {
        if (error instanceof UnauthorizedError) {
          onSessionExpired?.();
          return;
        }
        setLoadState("error");
      });
  };

  useEffect(() => {
    loadBoard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const cardsById = useMemo(() => board?.cards ?? {}, [board]);

  const handleMutationError = (error: unknown, previousBoard: BoardData) => {
    if (error instanceof UnauthorizedError) {
      onSessionExpired?.();
      return;
    }
    setBoard(previousBoard);
    setActionError("Something went wrong saving that change. Please try again.");
  };

  const handleDragStart = (event: DragStartEvent) => {
    setActiveCardId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCardId(null);

    if (!board || !over || active.id === over.id) {
      return;
    }

    const previousBoard = board;
    const nextColumns = moveCard(board.columns, active.id as string, over.id as string);
    if (nextColumns === board.columns) {
      return;
    }

    const cardId = active.id as string;
    const targetColumn = nextColumns.find((column) => column.cardIds.includes(cardId));
    if (!targetColumn) {
      return;
    }
    const position = targetColumn.cardIds.indexOf(cardId);

    setActionError(null);
    setBoard({ ...board, columns: nextColumns });

    moveCardApi(cardId, targetColumn.id, position).catch((error) =>
      handleMutationError(error, previousBoard)
    );
  };

  const handleRenameColumn = (columnId: string, title: string) => {
    if (!board) {
      return;
    }
    const previousBoard = board;
    setActionError(null);
    setBoard({
      ...board,
      columns: board.columns.map((column) =>
        column.id === columnId ? { ...column, title } : column
      ),
    });

    renameColumnApi(columnId, title).catch((error) =>
      handleMutationError(error, previousBoard)
    );
  };

  const handleAddCard = async (columnId: string, title: string, details: string) => {
    if (!board) {
      return;
    }
    setActionError(null);
    try {
      const card = await createCardApi(columnId, title, details);
      setBoard((prev) =>
        prev
          ? {
              ...prev,
              cards: { ...prev.cards, [card.id]: card },
              columns: prev.columns.map((column) =>
                column.id === columnId
                  ? { ...column, cardIds: [...column.cardIds, card.id] }
                  : column
              ),
            }
          : prev
      );
    } catch (error) {
      if (error instanceof UnauthorizedError) {
        onSessionExpired?.();
        return;
      }
      setActionError("Couldn't add that card. Please try again.");
      throw error;
    }
  };

  const handleDeleteCard = (columnId: string, cardId: string) => {
    if (!board) {
      return;
    }
    const previousBoard = board;
    setActionError(null);
    setBoard({
      ...board,
      cards: Object.fromEntries(
        Object.entries(board.cards).filter(([id]) => id !== cardId)
      ),
      columns: board.columns.map((column) =>
        column.id === columnId
          ? { ...column, cardIds: column.cardIds.filter((id) => id !== cardId) }
          : column
      ),
    });

    deleteCardApi(cardId).catch((error) => handleMutationError(error, previousBoard));
  };

  const activeCard = activeCardId ? cardsById[activeCardId] : null;

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-[1500px] flex-col gap-10 px-6 pb-16 pt-12">
        <header className="flex flex-col gap-6 rounded-[32px] border border-[var(--stroke)] bg-white/80 p-8 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Single Board Kanban
              </p>
              <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                Kanban Studio
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--gray-text)]">
                Keep momentum visible. Rename columns, drag cards between stages,
                and capture quick notes without getting buried in settings.
              </p>
            </div>
            <div className="flex items-start gap-4">
              <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                  Focus
                </p>
                <p className="mt-2 text-lg font-semibold text-[var(--primary-blue)]">
                  One board. Five columns. Zero clutter.
                </p>
              </div>
              {onLogout && (
                <button
                  type="button"
                  onClick={onLogout}
                  className="rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)] transition hover:text-[var(--navy-dark)]"
                >
                  Log out
                </button>
              )}
            </div>
          </div>
          {board && (
            <div className="flex flex-wrap items-center gap-4">
              {board.columns.map((column) => (
                <div
                  key={column.id}
                  className="flex items-center gap-2 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)]"
                >
                  <span className="h-2 w-2 rounded-full bg-[var(--accent-yellow)]" />
                  {column.title}
                </div>
              ))}
            </div>
          )}
          {actionError && (
            <div
              role="alert"
              className="flex items-center justify-between gap-4 rounded-2xl border border-red-200 bg-red-50 px-5 py-3 text-sm text-red-700"
            >
              <span>{actionError}</span>
              <button
                type="button"
                onClick={() => setActionError(null)}
                className="text-xs font-semibold uppercase tracking-wide text-red-700 hover:underline"
              >
                Dismiss
              </button>
            </div>
          )}
        </header>

        {loadState === "loading" && (
          <p className="text-center text-sm font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
            Loading board...
          </p>
        )}

        {loadState === "error" && (
          <div className="flex flex-col items-center gap-4 rounded-3xl border border-[var(--stroke)] bg-white p-10 text-center">
            <p className="text-sm text-[var(--gray-text)]">
              Couldn&apos;t load the board. Check your connection and try again.
            </p>
            <button
              type="button"
              onClick={loadBoard}
              className="rounded-full bg-[var(--secondary-purple)] px-5 py-2 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110"
            >
              Try again
            </button>
          </div>
        )}

        {loadState === "ready" && board && (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCorners}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <section className="grid gap-6 lg:grid-cols-5">
              {board.columns.map((column) => (
                <KanbanColumn
                  key={column.id}
                  column={column}
                  cards={column.cardIds.map((cardId) => board.cards[cardId])}
                  onRename={handleRenameColumn}
                  onAddCard={handleAddCard}
                  onDeleteCard={handleDeleteCard}
                />
              ))}
            </section>
            <DragOverlay>
              {activeCard ? (
                <div className="w-[260px]">
                  <KanbanCardPreview card={activeCard} />
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>
        )}
      </main>
    </div>
  );
};
