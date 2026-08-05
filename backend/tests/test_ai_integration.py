import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_ping_returns_real_ai_answer():
    if not os.environ.get("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY not set")

    from app.main import app

    with TestClient(app) as client:
        client.post("/api/login", json={"username": "user", "password": "password"})
        response = client.get("/api/ai/ping")

    assert response.status_code == 200
    assert "4" in response.json()["reply"]
