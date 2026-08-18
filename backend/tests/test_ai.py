import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from openai import APIConnectionError

from app.ai import MODEL, ask
from tests.fakes import FakeClient

CONNECTION_ERROR = APIConnectionError(
    request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
)


def _logged_in_client() -> TestClient:
    from app.main import app

    client = TestClient(app)
    client.post("/api/login", json={"username": "user", "password": "password"})
    return client


def test_ask_sends_expected_request_shape():
    fake_client = FakeClient(contents=["4"])

    reply = ask(fake_client, "what is 2+2?")

    assert reply == "4"
    [call] = fake_client.chat.completions.calls
    assert call["model"] == MODEL
    assert call["messages"] == [{"role": "user", "content": "what is 2+2?"}]


def test_ask_raises_502_on_api_error():
    fake_client = FakeClient(error=CONNECTION_ERROR)

    with pytest.raises(HTTPException) as exc_info:
        ask(fake_client, "what is 2+2?")

    assert exc_info.value.status_code == 502


def test_ask_raises_502_on_empty_response():
    fake_client = FakeClient(contents=[None])

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
    fake_client = FakeClient(contents=["4"])
    monkeypatch.setattr("app.ai.get_client", lambda: fake_client)
    client = _logged_in_client()

    response = client.get("/api/ai/ping")

    assert response.status_code == 200
    assert response.json() == {"reply": "4"}


def test_ping_surfaces_network_failure(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    fake_client = FakeClient(error=CONNECTION_ERROR)
    monkeypatch.setattr("app.ai.get_client", lambda: fake_client)
    client = _logged_in_client()

    response = client.get("/api/ai/ping")

    assert response.status_code == 502
