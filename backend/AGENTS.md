# Backend

FastAPI app managed with `uv`. Entry point: `app/main.py`.

## Structure

- `pyproject.toml` / `uv.lock` — dependencies (`fastapi`, `uvicorn`; dev: `pytest`, `httpx`)
- `app/main.py` — FastAPI app; lifespan hook initializes the SQLite DB on startup; mounts `static/` at `/` to serve the frontend
- `app/auth.py` — hardcoded-credential login/logout/session routes and the `require_auth` dependency other routers depend on
- `app/db.py` — SQLite schema (`docs/schema.json`), `connect()`/`init_db()`, and first-run seed data (mirrors `frontend/src/lib/kanban.ts`'s demo board)
- `app/board.py` — `/api/board`, `/api/columns/{id}`, `/api/cards` CRUD routes, all behind `require_auth`
- `static/` — the Next.js static export (see root `Dockerfile`)
- `tests/` — pytest tests using FastAPI's `TestClient`; `conftest.py` has an autouse fixture pointing `DB_PATH` at a per-test temp file, so tests never touch the dev DB

## Database

SQLite file at `backend/data/app.db` by default (override with `DB_PATH` env var; not committed). Under Docker it lives on the `app-data` named volume so it survives stop/start; `docker compose down -v` resets it. See `docs/DATABASE.md` for the design rationale.

Tables are created and seeded once, in the `lifespan` hook in `app/main.py` — not per request. Tests that need the DB must use `with TestClient(app)`, because a bare `TestClient(app)` does not run lifespan events.

## Running locally (without Docker)

Requires `uv` installed locally:

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
uv run pytest
```

Normal development/running is via Docker (see root `scripts/`), which bundles `uv` in the image — installing `uv` locally is optional, only needed for editor tooling or running tests outside the container.

## Conventions

- Add new routes under `/api/...`; keep `/` reserved for the static frontend mount.
- Keep route handlers thin; push logic that needs unit testing into plain functions/modules under `app/`.
