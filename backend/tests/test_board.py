import pytest
from fastapi.testclient import TestClient

from app.main import app

CREDENTIALS = {"username": "user", "password": "password"}


@pytest.fixture
def client():
    # `with` runs the lifespan hook, which is what creates and seeds the DB.
    with TestClient(app) as test_client:
        test_client.post("/api/login", json=CREDENTIALS)
        yield test_client


PROTECTED_ROUTES = [
    ("get", "/api/board", None),
    ("patch", "/api/columns/1", {"title": "hacked"}),
    ("post", "/api/cards", {"column_id": "1", "title": "hacked"}),
    ("patch", "/api/cards/1", {"title": "hacked"}),
    ("delete", "/api/cards/1", None),
]


@pytest.mark.parametrize("method,path,body", PROTECTED_ROUTES)
def test_board_routes_require_auth(method, path, body):
    """Every board route rejects unauthenticated callers, not just GET /api/board."""
    with TestClient(app) as test_client:
        response = test_client.request(method, path, json=body)
        assert response.status_code == 401


def test_rejected_requests_do_not_mutate_the_board():
    with TestClient(app) as anon:
        for method, path, body in PROTECTED_ROUTES:
            anon.request(method, path, json=body)

    with TestClient(app) as test_client:
        test_client.post("/api/login", json=CREDENTIALS)
        board = test_client.get("/api/board").json()

    assert board["columns"][0]["title"] == "Backlog"
    assert len(board["cards"]) == 8


def test_get_board_returns_seeded_data(client: TestClient):
    response = client.get("/api/board")
    assert response.status_code == 200
    data = response.json()
    assert len(data["columns"]) == 5
    assert data["columns"][0]["title"] == "Backlog"
    first_card_id = data["columns"][0]["cardIds"][0]
    assert data["cards"][first_card_id]["title"] == "Align roadmap themes"


def test_db_file_created_and_seeded_on_startup(db_path):
    """Deleting the DB file and starting the app recreates it with seed data."""
    assert not db_path.exists()

    with TestClient(app) as test_client:
        assert db_path.exists()
        test_client.post("/api/login", json=CREDENTIALS)
        response = test_client.get("/api/board")

    assert response.status_code == 200
    assert len(response.json()["columns"]) == 5


def test_startup_does_not_reseed_existing_db(db_path):
    """A second startup against an existing DB preserves edits instead of re-seeding."""
    with TestClient(app) as test_client:
        test_client.post("/api/login", json=CREDENTIALS)
        column_id = test_client.get("/api/board").json()["columns"][0]["id"]
        test_client.patch(f"/api/columns/{column_id}", json={"title": "Renamed"})

    with TestClient(app) as test_client:
        test_client.post("/api/login", json=CREDENTIALS)
        board = test_client.get("/api/board").json()

    assert board["columns"][0]["title"] == "Renamed"
    assert len(board["columns"]) == 5


def test_rename_column(client: TestClient):
    board = client.get("/api/board").json()
    column_id = board["columns"][0]["id"]
    response = client.patch(f"/api/columns/{column_id}", json={"title": "Renamed"})
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed"
    assert client.get("/api/board").json()["columns"][0]["title"] == "Renamed"


def test_rename_missing_column_returns_404(client: TestClient):
    response = client.patch("/api/columns/9999", json={"title": "Nope"})
    assert response.status_code == 404


def test_create_card(client: TestClient):
    board = client.get("/api/board").json()
    column_id = board["columns"][0]["id"]
    response = client.post(
        "/api/cards",
        json={"column_id": column_id, "title": "New card", "details": "Some details"},
    )
    assert response.status_code == 200
    card = response.json()
    assert card["title"] == "New card"

    updated_board = client.get("/api/board").json()
    assert card["id"] in updated_board["columns"][0]["cardIds"]
    assert updated_board["columns"][0]["cardIds"][-1] == card["id"]


def test_create_card_invalid_column_returns_404(client: TestClient):
    response = client.post(
        "/api/cards", json={"column_id": "9999", "title": "x", "details": ""}
    )
    assert response.status_code == 404


def test_edit_card_fields(client: TestClient):
    board = client.get("/api/board").json()
    card_id = board["columns"][0]["cardIds"][0]
    response = client.patch(
        f"/api/cards/{card_id}", json={"title": "Edited title", "details": "Edited"}
    )
    assert response.status_code == 200
    assert response.json() == {"id": card_id, "title": "Edited title", "details": "Edited"}


def test_move_card_between_columns(client: TestClient):
    board = client.get("/api/board").json()
    source_column, dest_column = board["columns"][0], board["columns"][1]
    card_id = source_column["cardIds"][0]

    response = client.patch(
        f"/api/cards/{card_id}", json={"column_id": dest_column["id"], "position": 0}
    )
    assert response.status_code == 200

    updated_board = client.get("/api/board").json()
    updated_source = next(c for c in updated_board["columns"] if c["id"] == source_column["id"])
    updated_dest = next(c for c in updated_board["columns"] if c["id"] == dest_column["id"])
    assert card_id not in updated_source["cardIds"]
    assert updated_dest["cardIds"][0] == card_id


def test_reorder_card_within_column(client: TestClient):
    board = client.get("/api/board").json()
    column = board["columns"][2]
    first_card, second_card = column["cardIds"][0], column["cardIds"][1]

    response = client.patch(
        f"/api/cards/{first_card}", json={"column_id": column["id"], "position": 1}
    )
    assert response.status_code == 200

    updated_column = next(
        c for c in client.get("/api/board").json()["columns"] if c["id"] == column["id"]
    )
    assert updated_column["cardIds"] == [second_card, first_card]


def test_update_missing_card_returns_404(client: TestClient):
    response = client.patch("/api/cards/9999", json={"title": "x"})
    assert response.status_code == 404


def test_delete_card(client: TestClient):
    board = client.get("/api/board").json()
    column = board["columns"][0]
    card_id = column["cardIds"][0]

    response = client.delete(f"/api/cards/{card_id}")
    assert response.status_code == 200
    assert response.json() == {"deleted": True}

    updated_column = next(
        c for c in client.get("/api/board").json()["columns"] if c["id"] == column["id"]
    )
    assert card_id not in updated_column["cardIds"]


def test_delete_missing_card_returns_404(client: TestClient):
    response = client.delete("/api/cards/9999")
    assert response.status_code == 404
