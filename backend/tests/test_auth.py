import pytest
from fastapi.testclient import TestClient

from app.main import app

CREDENTIALS = {"username": "user", "password": "password"}


@pytest.fixture
def client():
    return TestClient(app)


def test_session_starts_unauthenticated(client: TestClient):
    response = client.get("/api/session")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False}


def test_login_success_sets_session(client: TestClient):
    response = client.post("/api/login", json=CREDENTIALS)
    assert response.status_code == 200
    assert response.json() == {"authenticated": True}
    assert client.get("/api/session").json() == {"authenticated": True}


def test_login_failure_returns_401(client: TestClient):
    response = client.post("/api/login", json={"username": "user", "password": "wrong"})
    assert response.status_code == 401


def test_me_requires_authentication(client: TestClient):
    response = client.get("/api/me")
    assert response.status_code == 401


def test_me_returns_username_after_login(client: TestClient):
    client.post("/api/login", json=CREDENTIALS)
    response = client.get("/api/me")
    assert response.status_code == 200
    assert response.json() == {"username": "user"}


def test_logout_clears_session(client: TestClient):
    client.post("/api/login", json=CREDENTIALS)
    client.post("/api/logout")
    response = client.get("/api/me")
    assert response.status_code == 401
