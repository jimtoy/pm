import json
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from openai import APIError, OpenAI
from pydantic import BaseModel, ValidationError

from app.ai import MODEL, get_client
from app.auth import require_auth
from app.board import (
    BoardData,
    apply_create_card,
    apply_delete_card,
    apply_rename_column,
    apply_update_card,
    get_board,
    get_board_id,
    parse_id,
)
from app.db import connect

router = APIRouter(prefix="/api/ai", tags=["chat"], dependencies=[Depends(require_auth)])

SYSTEM_PROMPT_TEMPLATE = """You are an assistant embedded in a Kanban board app. Reply \
conversationally in `reply`. If the user's message implies a change to the board, describe \
it as a list of operations in `board_update`; otherwise set `board_update` to null.

Valid operations:
- rename_column: set column_id and title
- create_card: set column_id, title, and optionally details
- update_card: set card_id, and only the fields being changed (title, details, column_id \
to move it, position to reorder within its column)
- delete_card: set card_id

Always use the exact ids from the board data below; never invent ids.

Current board:
{board_json}"""


class BoardOperation(BaseModel):
    op: Literal["rename_column", "create_card", "update_card", "delete_card"]
    column_id: str | None = None
    card_id: str | None = None
    title: str | None = None
    details: str | None = None
    position: int | None = None


class StructuredReply(BaseModel):
    reply: str
    board_update: list[BoardOperation] | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "board_chat_response",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "reply": {"type": "string"},
                "board_update": {
                    "type": ["array", "null"],
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "op": {
                                "type": "string",
                                "enum": [
                                    "rename_column",
                                    "create_card",
                                    "update_card",
                                    "delete_card",
                                ],
                            },
                            "column_id": {"type": ["string", "null"]},
                            "card_id": {"type": ["string", "null"]},
                            "title": {"type": ["string", "null"]},
                            "details": {"type": ["string", "null"]},
                            "position": {"type": ["integer", "null"]},
                        },
                        "required": [
                            "op",
                            "column_id",
                            "card_id",
                            "title",
                            "details",
                            "position",
                        ],
                    },
                },
            },
            "required": ["reply", "board_update"],
        },
    },
}


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def _system_prompt(board: BoardData) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(board_json=board.model_dump_json())


def _load_history(conn: sqlite3.Connection, board_id: int) -> list[ChatMessage]:
    rows = conn.execute(
        "SELECT role, content FROM chat_messages WHERE board_id = ? ORDER BY id",
        (board_id,),
    ).fetchall()
    return [ChatMessage(role=row["role"], content=row["content"]) for row in rows]


def _save_message(conn: sqlite3.Connection, board_id: int, role: str, content: str) -> None:
    conn.execute(
        "INSERT INTO chat_messages (board_id, role, content) VALUES (?, ?, ?)",
        (board_id, role, content),
    )
    conn.commit()


# openai/gpt-oss-120b via OpenRouter doesn't reliably honor the JSON schema even with
# strict mode - empirically ~30-40% of calls omit/rename a required field. A few retries
# on a malformed response (not on APIError, which should surface immediately) brings the
# effective success rate close to 100% without the complexity of a real backoff scheme.
MAX_STRUCTURED_ATTEMPTS = 3


def ask_structured(client: OpenAI, messages: list[dict[str, str]]) -> StructuredReply:
    last_error: Exception | None = None
    for _attempt in range(MAX_STRUCTURED_ATTEMPTS):
        try:
            response = client.chat.completions.create(
                model=MODEL, messages=messages, response_format=RESPONSE_FORMAT
            )
        except APIError as exc:
            raise HTTPException(
                status_code=502, detail=f"OpenRouter request failed: {exc}"
            ) from exc

        if not response.choices or not response.choices[0].message.content:
            raise HTTPException(status_code=502, detail="OpenRouter returned an empty response")

        content = response.choices[0].message.content
        try:
            return StructuredReply.model_validate(json.loads(content))
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc

    raise HTTPException(
        status_code=502, detail="OpenRouter returned an unexpected response format"
    ) from last_error


def apply_operations(conn: sqlite3.Connection, operations: list[BoardOperation]) -> None:
    for operation in operations:
        if operation.op == "rename_column":
            apply_rename_column(conn, parse_id(operation.column_id or ""), operation.title or "")
        elif operation.op == "create_card":
            apply_create_card(
                conn,
                parse_id(operation.column_id or ""),
                operation.title or "",
                operation.details or "",
            )
        elif operation.op == "update_card":
            apply_update_card(
                conn,
                parse_id(operation.card_id or ""),
                title=operation.title,
                details=operation.details,
                column_id=parse_id(operation.column_id) if operation.column_id else None,
                position=operation.position,
            )
        elif operation.op == "delete_card":
            apply_delete_card(conn, parse_id(operation.card_id or ""))


@router.get("/messages")
def list_messages(conn: sqlite3.Connection = Depends(get_db)) -> list[ChatMessage]:
    return _load_history(conn, get_board_id(conn))


@router.post("/chat")
def chat(payload: ChatRequest, conn: sqlite3.Connection = Depends(get_db)) -> ChatResponse:
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    board_id = get_board_id(conn)
    history = _load_history(conn, board_id)
    board = get_board(conn)

    client = get_client()
    messages = [{"role": "system", "content": _system_prompt(board)}]
    messages += [{"role": m.role, "content": m.content} for m in history]
    messages.append({"role": "user", "content": payload.message})

    structured = ask_structured(client, messages)

    if structured.board_update:
        apply_operations(conn, structured.board_update)

    _save_message(conn, board_id, "user", payload.message)
    _save_message(conn, board_id, "assistant", structured.reply)

    return ChatResponse(reply=structured.reply)
