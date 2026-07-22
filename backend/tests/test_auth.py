from fastapi.testclient import TestClient

from app.main import app


def _client() -> TestClient:
    return TestClient(app)


def test_session_starts_unauthenticated():
    client = _client()
    response = client.get("/api/session")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False}


def test_login_success_sets_session():
    client = _client()
    response = client.post(
        "/api/login", json={"username": "user", "password": "password"}
    )
    assert response.status_code == 200
    assert response.json() == {"authenticated": True}
    assert client.get("/api/session").json() == {"authenticated": True}


def test_login_failure_returns_401():
    client = _client()
    response = client.post(
        "/api/login", json={"username": "user", "password": "wrong"}
    )
    assert response.status_code == 401


def test_me_requires_authentication():
    client = _client()
    response = client.get("/api/me")
    assert response.status_code == 401


def test_me_returns_username_after_login():
    client = _client()
    client.post("/api/login", json={"username": "user", "password": "password"})
    response = client.get("/api/me")
    assert response.status_code == 200
    assert response.json() == {"username": "user"}


def test_logout_clears_session():
    client = _client()
    client.post("/api/login", json={"username": "user", "password": "password"})
    client.post("/api/logout")
    response = client.get("/api/me")
    assert response.status_code == 401
