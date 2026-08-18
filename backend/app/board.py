import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_auth
from app.db import get_db

router = APIRouter(prefix="/api", tags=["board"], dependencies=[Depends(require_auth)])


class Card(BaseModel):
    id: str
    title: str
    details: str


class Column(BaseModel):
    id: str
    title: str
    cardIds: list[str]


class BoardData(BaseModel):
    columns: list[Column]
    cards: dict[str, Card]


class RenameColumnRequest(BaseModel):
    title: str


class CreateCardRequest(BaseModel):
    column_id: str
    title: str
    details: str = ""


class UpdateCardRequest(BaseModel):
    title: str | None = None
    details: str | None = None
    column_id: str | None = None
    position: int | None = None


def parse_id(raw_id: str) -> int:
    try:
        return int(raw_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")


def get_board_id(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT id FROM boards ORDER BY id LIMIT 1").fetchone()
    if row is None:
        raise HTTPException(status_code=500, detail="No board exists")
    return row["id"]


def _require_column(conn: sqlite3.Connection, column_id: int) -> None:
    row = conn.execute("SELECT 1 FROM board_columns WHERE id = ?", (column_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Column not found")


def _require_card(conn: sqlite3.Connection, card_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return row


def _card_ids_in_column(conn: sqlite3.Connection, column_id: int) -> list[int]:
    return [
        row["id"]
        for row in conn.execute(
            "SELECT id FROM cards WHERE column_id = ? ORDER BY position", (column_id,)
        )
    ]


def _renumber(conn: sqlite3.Connection, column_id: int, ordered_card_ids: list[int]) -> None:
    for position, card_id in enumerate(ordered_card_ids):
        conn.execute(
            "UPDATE cards SET position = ?, column_id = ? WHERE id = ?",
            (position, column_id, card_id),
        )


def _move_card(
    conn: sqlite3.Connection, card_id: int, new_column_id: int, new_position: int | None
) -> None:
    old_column_id = _require_card(conn, card_id)["column_id"]

    source_ids = [cid for cid in _card_ids_in_column(conn, old_column_id) if cid != card_id]
    if new_column_id == old_column_id:
        target_ids = source_ids
    else:
        target_ids = _card_ids_in_column(conn, new_column_id)

    if new_position is None:
        insert_at = len(target_ids)
    else:
        insert_at = max(0, min(new_position, len(target_ids)))
    target_ids.insert(insert_at, card_id)

    if new_column_id != old_column_id:
        _renumber(conn, old_column_id, source_ids)
    _renumber(conn, new_column_id, target_ids)


def get_board(conn: sqlite3.Connection) -> BoardData:
    board_id = get_board_id(conn)
    column_rows = conn.execute(
        "SELECT id, title FROM board_columns WHERE board_id = ? ORDER BY position",
        (board_id,),
    ).fetchall()

    columns: list[Column] = []
    cards: dict[str, Card] = {}
    for column_row in column_rows:
        card_ids: list[str] = []
        for card_row in conn.execute(
            "SELECT id, title, details FROM cards WHERE column_id = ? ORDER BY position",
            (column_row["id"],),
        ).fetchall():
            card = Card(
                id=str(card_row["id"]), title=card_row["title"], details=card_row["details"]
            )
            cards[card.id] = card
            card_ids.append(card.id)
        columns.append(
            Column(id=str(column_row["id"]), title=column_row["title"], cardIds=card_ids)
        )

    return BoardData(columns=columns, cards=cards)


def apply_rename_column(conn: sqlite3.Connection, column_id: int, title: str) -> Column:
    _require_column(conn, column_id)
    conn.execute("UPDATE board_columns SET title = ? WHERE id = ?", (title, column_id))
    card_ids = [str(cid) for cid in _card_ids_in_column(conn, column_id)]
    return Column(id=str(column_id), title=title, cardIds=card_ids)


def apply_create_card(
    conn: sqlite3.Connection, column_id: int, title: str, details: str = ""
) -> Card:
    _require_column(conn, column_id)
    position = len(_card_ids_in_column(conn, column_id))
    cursor = conn.execute(
        "INSERT INTO cards (column_id, title, details, position) VALUES (?, ?, ?, ?)",
        (column_id, title, details, position),
    )
    return Card(id=str(cursor.lastrowid), title=title, details=details)


def apply_update_card(
    conn: sqlite3.Connection,
    card_id: int,
    title: str | None = None,
    details: str | None = None,
    column_id: int | None = None,
    position: int | None = None,
) -> Card:
    row = _require_card(conn, card_id)
    final_title = title if title is not None else row["title"]
    final_details = details if details is not None else row["details"]
    conn.execute(
        "UPDATE cards SET title = ?, details = ? WHERE id = ?",
        (final_title, final_details, card_id),
    )

    if column_id is not None or position is not None:
        target_column_id = column_id if column_id is not None else row["column_id"]
        _require_column(conn, target_column_id)
        _move_card(conn, card_id, target_column_id, position)

    return Card(id=str(card_id), title=final_title, details=final_details)


def apply_delete_card(conn: sqlite3.Connection, card_id: int) -> None:
    column_id = _require_card(conn, card_id)["column_id"]
    conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
    _renumber(conn, column_id, _card_ids_in_column(conn, column_id))


@router.get("/board")
def get_board_route(conn: sqlite3.Connection = Depends(get_db)) -> BoardData:
    return get_board(conn)


@router.patch("/columns/{column_id}")
def rename_column(
    column_id: str, payload: RenameColumnRequest, conn: sqlite3.Connection = Depends(get_db)
) -> Column:
    column = apply_rename_column(conn, parse_id(column_id), payload.title)
    conn.commit()
    return column


@router.post("/cards")
def create_card(
    payload: CreateCardRequest, conn: sqlite3.Connection = Depends(get_db)
) -> Card:
    card = apply_create_card(conn, parse_id(payload.column_id), payload.title, payload.details)
    conn.commit()
    return card


@router.patch("/cards/{card_id}")
def update_card(
    card_id: str, payload: UpdateCardRequest, conn: sqlite3.Connection = Depends(get_db)
) -> Card:
    column_id = parse_id(payload.column_id) if payload.column_id is not None else None
    card = apply_update_card(
        conn,
        parse_id(card_id),
        title=payload.title,
        details=payload.details,
        column_id=column_id,
        position=payload.position,
    )
    conn.commit()
    return card


@router.delete("/cards/{card_id}")
def delete_card(card_id: str, conn: sqlite3.Connection = Depends(get_db)) -> dict[str, bool]:
    apply_delete_card(conn, parse_id(card_id))
    conn.commit()
    return {"deleted": True}
