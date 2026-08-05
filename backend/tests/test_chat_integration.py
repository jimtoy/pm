import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_chat_moves_card_via_real_ai():
    if not os.environ.get("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY not set")

    from app.main import app

    with TestClient(app) as client:
        client.post("/api/login", json={"username": "user", "password": "password"})
        board = client.get("/api/board").json()

        backlog = next(c for c in board["columns"] if c["title"] == "Backlog")
        done = next(c for c in board["columns"] if c["title"] == "Done")
        card_id = next(
            cid
            for cid in backlog["cardIds"]
            if board["cards"][cid]["title"] == "Align roadmap themes"
        )

        response = client.post(
            "/api/ai/chat",
            json={"message": "Move the 'Align roadmap themes' card to the Done column."},
        )
        assert response.status_code == 200
        assert response.json()["reply"]

        updated_board = client.get("/api/board").json()

    updated_backlog = next(c for c in updated_board["columns"] if c["id"] == backlog["id"])
    updated_done = next(c for c in updated_board["columns"] if c["id"] == done["id"])
    assert card_id not in updated_backlog["cardIds"]
    assert card_id in updated_done["cardIds"]
