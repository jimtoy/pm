export type Card = {
  id: string;
  title: string;
  details: string;
};

export type Column = {
  id: string;
  title: string;
  cardIds: string[];
};

export type BoardData = {
  columns: Column[];
  cards: Record<string, Card>;
};

// `overId` is either a card id (drop onto a specific card) or a column id
// (drop onto empty space in a column, which appends to the end).
export const moveCard = (
  columns: Column[],
  activeId: string,
  overId: string
): Column[] => {
  const activeColumn = columns.find((column) => column.cardIds.includes(activeId));
  const overColumn = columns.find(
    (column) => column.id === overId || column.cardIds.includes(overId)
  );

  if (!activeColumn || !overColumn) {
    return columns;
  }

  const fromIndex = activeColumn.cardIds.indexOf(activeId);
  const toIndex =
    overColumn.id === overId
      ? overColumn.cardIds.length
      : overColumn.cardIds.indexOf(overId);

  if (activeColumn.id === overColumn.id) {
    if (fromIndex === toIndex) {
      return columns;
    }
    const cardIds = [...activeColumn.cardIds];
    cardIds.splice(fromIndex, 1);
    cardIds.splice(toIndex, 0, activeId);
    return columns.map((column) =>
      column.id === activeColumn.id ? { ...column, cardIds } : column
    );
  }

  const nextActiveCardIds = activeColumn.cardIds.filter((id) => id !== activeId);
  const nextOverCardIds = [...overColumn.cardIds];
  nextOverCardIds.splice(toIndex, 0, activeId);

  return columns.map((column) => {
    if (column.id === activeColumn.id) {
      return { ...column, cardIds: nextActiveCardIds };
    }
    if (column.id === overColumn.id) {
      return { ...column, cardIds: nextOverCardIds };
    }
    return column;
  });
};
