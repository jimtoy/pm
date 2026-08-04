import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_auth
from app.db import connect

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


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def _parse_id(raw_id: str) -> int:
    try:
        return int(raw_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")


def _get_board_id(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT id FROM boards ORDER BY id LIMIT 1").fetchone()
    if row is None:
        raise HTTPException(status_code=500, detail="No board exists")
    return row["id"]


def _require_column(conn: sqlite3.Connection, column_id: int) -> None:
    if conn.execute(
        "SELECT 1 FROM board_columns WHERE id = ?", (column_id,)
    ).fetchone() is None:
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

    source_ids = [
        cid for cid in _card_ids_in_column(conn, old_column_id) if cid != card_id
    ]
    target_ids = source_ids if new_column_id == old_column_id else [
        cid for cid in _card_ids_in_column(conn, new_column_id) if cid != card_id
    ]

    insert_at = (
        len(target_ids) if new_position is None else max(0, min(new_position, len(target_ids)))
    )
    target_ids.insert(insert_at, card_id)

    if new_column_id != old_column_id:
        _renumber(conn, old_column_id, source_ids)
    _renumber(conn, new_column_id, target_ids)


def _to_card(row: sqlite3.Row) -> Card:
    return Card(id=str(row["id"]), title=row["title"], details=row["details"])


@router.get("/board")
def get_board(conn: sqlite3.Connection = Depends(get_db)) -> BoardData:
    board_id = _get_board_id(conn)
    columns = conn.execute(
        "SELECT id, title FROM board_columns WHERE board_id = ? ORDER BY position",
        (board_id,),
    ).fetchall()

    result_columns = []
    cards: dict[str, Card] = {}
    for column in columns:
        card_rows = conn.execute(
            "SELECT id, title, details FROM cards WHERE column_id = ? ORDER BY position",
            (column["id"],),
        ).fetchall()
        card_ids = []
        for card_row in card_rows:
            card = _to_card(card_row)
            cards[card.id] = card
            card_ids.append(card.id)
        result_columns.append(
            Column(id=str(column["id"]), title=column["title"], cardIds=card_ids)
        )

    return BoardData(columns=result_columns, cards=cards)


@router.patch("/columns/{column_id}")
def rename_column(
    column_id: str, payload: RenameColumnRequest, conn: sqlite3.Connection = Depends(get_db)
) -> Column:
    parsed_id = _parse_id(column_id)
    _require_column(conn, parsed_id)
    conn.execute(
        "UPDATE board_columns SET title = ? WHERE id = ?", (payload.title, parsed_id)
    )
    conn.commit()
    card_ids = [str(cid) for cid in _card_ids_in_column(conn, parsed_id)]
    return Column(id=column_id, title=payload.title, cardIds=card_ids)


@router.post("/cards")
def create_card(
    payload: CreateCardRequest, conn: sqlite3.Connection = Depends(get_db)
) -> Card:
    column_id = _parse_id(payload.column_id)
    _require_column(conn, column_id)
    position = len(_card_ids_in_column(conn, column_id))
    cursor = conn.execute(
        "INSERT INTO cards (column_id, title, details, position) VALUES (?, ?, ?, ?)",
        (column_id, payload.title, payload.details, position),
    )
    conn.commit()
    return Card(id=str(cursor.lastrowid), title=payload.title, details=payload.details)


@router.patch("/cards/{card_id}")
def update_card(
    card_id: str, payload: UpdateCardRequest, conn: sqlite3.Connection = Depends(get_db)
) -> Card:
    parsed_id = _parse_id(card_id)
    row = _require_card(conn, parsed_id)

    title = payload.title if payload.title is not None else row["title"]
    details = payload.details if payload.details is not None else row["details"]
    conn.execute(
        "UPDATE cards SET title = ?, details = ? WHERE id = ?", (title, details, parsed_id)
    )

    if payload.column_id is not None or payload.position is not None:
        new_column_id = (
            _parse_id(payload.column_id) if payload.column_id is not None else row["column_id"]
        )
        _require_column(conn, new_column_id)
        _move_card(conn, parsed_id, new_column_id, payload.position)

    conn.commit()
    return Card(id=card_id, title=title, details=details)


@router.delete("/cards/{card_id}")
def delete_card(card_id: str, conn: sqlite3.Connection = Depends(get_db)) -> dict[str, bool]:
    parsed_id = _parse_id(card_id)
    row = _require_card(conn, parsed_id)
    column_id = row["column_id"]
    conn.execute("DELETE FROM cards WHERE id = ?", (parsed_id,))
    remaining_ids = [
        cid for cid in _card_ids_in_column(conn, column_id) if cid != parsed_id
    ]
    _renumber(conn, column_id, remaining_ids)
    conn.commit()
    return {"deleted": True}
