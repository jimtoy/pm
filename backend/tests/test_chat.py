import json
from contextlib import contextmanager

import httpx
from fastapi.testclient import TestClient
from openai import APIConnectionError

from tests.fakes import FakeClient


@contextmanager
def logged_in_client(monkeypatch, contents=None, error=None):
    """A TestClient with lifespan (DB init + seed) run, logged in, and a fake AI client wired in."""
    from app.main import app

    fake = FakeClient(contents=contents, error=error)
    monkeypatch.setattr("app.chat.get_client", lambda: fake)

    with TestClient(app) as client:
        client.post("/api/login", json={"username": "user", "password": "password"})
        yield client, fake


def _board(client: TestClient) -> dict:
    return client.get("/api/board").json()


def _operation(op: str, **fields) -> dict:
    """One board operation with every schema-required key present, as the model returns them."""
    return {
        "op": op,
        "column_id": None,
        "card_id": None,
        "title": None,
        "details": None,
        "position": None,
        **fields,
    }


def _reply(text: str, operations: list[dict] | None = None) -> str:
    return json.dumps({"reply": text, "board_update": operations})


def test_chat_requires_auth():
    from app.main import app

    with TestClient(app) as client:
        response = client.post("/api/ai/chat", json={"message": "hi"})
        assert response.status_code == 401
        assert client.get("/api/ai/messages").status_code == 401


def test_chat_rejects_empty_message(monkeypatch):
    with logged_in_client(monkeypatch) as (client, _fake):
        response = client.post("/api/ai/chat", json={"message": "   "})
        assert response.status_code == 400


def test_messages_empty_before_any_chat(monkeypatch):
    with logged_in_client(monkeypatch) as (client, _fake):
        assert client.get("/api/ai/messages").json() == []


def test_chat_returns_reply_with_no_board_update(monkeypatch):
    with logged_in_client(monkeypatch, contents=[_reply("Hello there")]) as (client, fake):
        board_before = _board(client)

        response = client.post("/api/ai/chat", json={"message": "hi"})

        assert response.status_code == 200
        assert response.json() == {"reply": "Hello there"}
        assert _board(client) == board_before
        [call] = fake.chat.completions.calls
        assert call["messages"][-1] == {"role": "user", "content": "hi"}
        assert call["messages"][0]["role"] == "system"


def test_chat_applies_move_card_operation(monkeypatch):
    with logged_in_client(monkeypatch) as (client, _fake):
        board = _board(client)
    source_column, dest_column = board["columns"][0], board["columns"][-1]
    card_id = source_column["cardIds"][0]

    operations = [
        _operation("update_card", column_id=dest_column["id"], card_id=card_id, position=0)
    ]
    move_reply = _reply("Moved it to Done", operations)

    with logged_in_client(monkeypatch, contents=[move_reply]) as (client, _fake):
        response = client.post("/api/ai/chat", json={"message": "move that card to Done"})

        assert response.status_code == 200
        assert response.json() == {"reply": "Moved it to Done"}

        updated_board = _board(client)
        updated_dest = next(c for c in updated_board["columns"] if c["id"] == dest_column["id"])
        updated_source = next(
            c for c in updated_board["columns"] if c["id"] == source_column["id"]
        )
        assert card_id in updated_dest["cardIds"]
        assert card_id not in updated_source["cardIds"]


def test_chat_applies_create_card_operation(monkeypatch):
    with logged_in_client(monkeypatch) as (client, _fake):
        board = _board(client)
    column_id = board["columns"][0]["id"]

    operations = [
        _operation(
            "create_card",
            column_id=column_id,
            title="New AI card",
            details="created by the assistant",
        )
    ]

    with logged_in_client(monkeypatch, contents=[_reply("Added it", operations)]) as (
        client,
        _fake,
    ):
        response = client.post("/api/ai/chat", json={"message": "add a card"})

        assert response.status_code == 200
        updated_board = _board(client)
        titles = [
            updated_board["cards"][cid]["title"]
            for cid in updated_board["columns"][0]["cardIds"]
        ]
        assert "New AI card" in titles


def test_chat_persists_conversation_history(monkeypatch):
    contents = [_reply("First reply"), _reply("Second reply")]

    with logged_in_client(monkeypatch, contents=contents) as (client, fake):
        client.post("/api/ai/chat", json={"message": "first message"})
        client.post("/api/ai/chat", json={"message": "second message"})

        messages = client.get("/api/ai/messages").json()
        assert [m["content"] for m in messages] == [
            "first message",
            "First reply",
            "second message",
            "Second reply",
        ]
        assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]

        second_call_messages = fake.chat.completions.calls[1]["messages"]
        assert {"role": "user", "content": "first message"} in second_call_messages
        assert {"role": "assistant", "content": "First reply"} in second_call_messages


def test_chat_malformed_json_returns_502_and_does_not_persist(monkeypatch):
    # ask_structured retries on malformed output (see MAX_STRUCTURED_ATTEMPTS), so the fake
    # must exhaust every attempt with bad content to prove the final-failure path works.
    with logged_in_client(monkeypatch, contents=["not json"] * 3) as (client, fake):
        response = client.post("/api/ai/chat", json={"message": "hi"})

        assert response.status_code == 502
        assert client.get("/api/ai/messages").json() == []
        assert len(fake.chat.completions.calls) == 3


def test_chat_schema_violation_returns_502(monkeypatch):
    bad_json = json.dumps({"board_update": None})  # missing required "reply"
    with logged_in_client(monkeypatch, contents=[bad_json] * 3) as (client, _fake):
        response = client.post("/api/ai/chat", json={"message": "hi"})

        assert response.status_code == 502
        assert client.get("/api/ai/messages").json() == []


def test_chat_retries_and_succeeds_after_malformed_response(monkeypatch):
    contents = ["not json", "still not json", _reply("Recovered")]
    with logged_in_client(monkeypatch, contents=contents) as (client, fake):
        response = client.post("/api/ai/chat", json={"message": "hi"})

        assert response.status_code == 200
        assert response.json() == {"reply": "Recovered"}
        assert len(fake.chat.completions.calls) == 3


def test_chat_rejects_null_title_for_rename_column(monkeypatch):
    with logged_in_client(monkeypatch) as (client, _fake):
        board = _board(client)
    column_id = board["columns"][0]["id"]
    original_title = board["columns"][0]["title"]

    operations = [_operation("rename_column", column_id=column_id, title=None)]

    with logged_in_client(monkeypatch, contents=[_reply("Renamed it", operations)]) as (
        client,
        _fake,
    ):
        response = client.post("/api/ai/chat", json={"message": "rename the first column"})

        assert response.status_code == 502
        updated_board = _board(client)
        assert updated_board["columns"][0]["title"] == original_title
        # A failed turn persists neither side, matching other failure-path behavior.
        assert client.get("/api/ai/messages").json() == []


def test_chat_rejects_empty_title_for_create_card(monkeypatch):
    with logged_in_client(monkeypatch) as (client, _fake):
        board = _board(client)
    column_id = board["columns"][0]["id"]
    cards_before = len(board["cards"])

    operations = [_operation("create_card", column_id=column_id, title="   ")]

    with logged_in_client(monkeypatch, contents=[_reply("Added it", operations)]) as (
        client,
        _fake,
    ):
        response = client.post("/api/ai/chat", json={"message": "add an untitled card"})

        assert response.status_code == 502
        assert len(_board(client)["cards"]) == cards_before


def test_chat_partial_batch_failure_rolls_back_all_operations(monkeypatch):
    with logged_in_client(monkeypatch) as (client, _fake):
        board_before = _board(client)
    column_id = board_before["columns"][0]["id"]

    # First operation is valid and would succeed on its own; second references a
    # card id that doesn't exist. The whole batch must roll back, not just fail
    # partway through with the first operation's mutation left committed.
    operations = [
        _operation("rename_column", column_id=column_id, title="Renamed by AI"),
        _operation("delete_card", card_id="999999"),
    ]

    with logged_in_client(monkeypatch, contents=[_reply("Doing both", operations)]) as (
        client,
        _fake,
    ):
        response = client.post("/api/ai/chat", json={"message": "rename and delete"})

        assert response.status_code == 404
        updated_board = _board(client)
        assert updated_board["columns"][0]["title"] == board_before["columns"][0]["title"]
        assert client.get("/api/ai/messages").json() == []


def test_chat_surfaces_api_error(monkeypatch):
    error = APIConnectionError(
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    )
    with logged_in_client(monkeypatch, error=error) as (client, _fake):
        response = client.post("/api/ai/chat", json={"message": "hi"})

        assert response.status_code == 502
