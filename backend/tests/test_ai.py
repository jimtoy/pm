import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from openai import APIConnectionError

from app.ai import MODEL, ask


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
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._response


class FakeChat:
    def __init__(self, completions):
        self.completions = completions


class FakeClient:
    def __init__(self, response=None, error=None):
        self.chat = FakeChat(FakeCompletions(response=response, error=error))


def _logged_in_client() -> TestClient:
    from app.main import app

    client = TestClient(app)
    client.post("/api/login", json={"username": "user", "password": "password"})
    return client


def test_ask_sends_expected_request_shape():
    fake_client = FakeClient(response=FakeResponse("4"))

    reply = ask(fake_client, "what is 2+2?")

    assert reply == "4"
    [call] = fake_client.chat.completions.calls
    assert call["model"] == MODEL
    assert call["messages"] == [{"role": "user", "content": "what is 2+2?"}]


def test_ask_raises_502_on_api_error():
    fake_client = FakeClient(error=APIConnectionError(request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")))

    with pytest.raises(HTTPException) as exc_info:
        ask(fake_client, "what is 2+2?")

    assert exc_info.value.status_code == 502


def test_ask_raises_502_on_empty_response():
    fake_client = FakeClient(response=FakeResponse(None))

    with pytest.raises(HTTPException) as exc_info:
        ask(fake_client, "what is 2+2?")

    assert exc_info.value.status_code == 502


def test_ping_requires_auth():
    from app.main import app

    client = TestClient(app)
    response = client.get("/api/ai/ping")
    assert response.status_code == 401


def test_ping_returns_500_when_key_missing(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    client = _logged_in_client()

    response = client.get("/api/ai/ping")

    assert response.status_code == 500
    assert "OPENROUTER_API_KEY" in response.json()["detail"]


def test_ping_returns_reply_on_success(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    fake_client = FakeClient(response=FakeResponse("4"))
    monkeypatch.setattr("app.ai.get_client", lambda: fake_client)
    client = _logged_in_client()

    response = client.get("/api/ai/ping")

    assert response.status_code == 200
    assert response.json() == {"reply": "4"}


def test_ping_surfaces_network_failure(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    fake_client = FakeClient(error=APIConnectionError(request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")))
    monkeypatch.setattr("app.ai.get_client", lambda: fake_client)
    client = _logged_in_client()

    response = client.get("/api/ai/ping")

    assert response.status_code == 502
