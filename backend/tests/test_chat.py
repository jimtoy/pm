import json
from contextlib import contextmanager

from fastapi.testclient import TestClient
from openai import APIConnectionError


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)] if content is not None else []


class FakeCompletions:
    def __init__(self, contents=None, error=None):
        self._contents = list(contents) if contents is not None else None
        self._error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return FakeResponse(self._contents.pop(0))


class FakeChat:
    def __init__(self, completions):
        self.completions = completions


class FakeClient:
    def __init__(self, contents=None, error=None):
        self.chat = FakeChat(FakeCompletions(contents=contents, error=error))


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
    reply_json = json.dumps({"reply": "Hello there", "board_update": None})
    with logged_in_client(monkeypatch, contents=[reply_json]) as (client, fake):
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
        {
            "op": "update_card",
            "column_id": dest_column["id"],
            "card_id": card_id,
            "title": None,
            "details": None,
            "position": 0,
        }
    ]
    move_reply = json.dumps({"reply": "Moved it to Done", "board_update": operations})

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
        {
            "op": "create_card",
            "column_id": column_id,
            "card_id": None,
            "title": "New AI card",
            "details": "created by the assistant",
            "position": None,
        }
    ]
    reply_json = json.dumps({"reply": "Added it", "board_update": operations})

    with logged_in_client(monkeypatch, contents=[reply_json]) as (client, _fake):
        response = client.post("/api/ai/chat", json={"message": "add a card"})

        assert response.status_code == 200
        updated_board = _board(client)
        titles = [
            updated_board["cards"][cid]["title"]
            for cid in updated_board["columns"][0]["cardIds"]
        ]
        assert "New AI card" in titles


def test_chat_persists_conversation_history(monkeypatch):
    first_reply = json.dumps({"reply": "First reply", "board_update": None})
    second_reply = json.dumps({"reply": "Second reply", "board_update": None})

    with logged_in_client(monkeypatch, contents=[first_reply, second_reply]) as (client, fake):
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
    good_reply = json.dumps({"reply": "Recovered", "board_update": None})
    with logged_in_client(monkeypatch, contents=["not json", "still not json", good_reply]) as (
        client,
        fake,
    ):
        response = client.post("/api/ai/chat", json={"message": "hi"})

        assert response.status_code == 200
        assert response.json() == {"reply": "Recovered"}
        assert len(fake.chat.completions.calls) == 3


def test_chat_surfaces_api_error(monkeypatch):
    import httpx

    error = APIConnectionError(
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    )
    with logged_in_client(monkeypatch, error=error) as (client, _fake):
        response = client.post("/api/ai/chat", json={"message": "hi"})

        assert response.status_code == 502
