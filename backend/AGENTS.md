# Backend

FastAPI app managed with `uv`. Entry point: `app/main.py`.

## Structure

- `pyproject.toml` / `uv.lock` — dependencies (`fastapi`, `uvicorn`; dev: `pytest`, `httpx`)
- `app/main.py` — FastAPI app; lifespan hook initializes the SQLite DB on startup; mounts `static/` at `/` to serve the frontend
- `app/auth.py` — hardcoded-credential login/logout/session routes and the `require_auth` dependency other routers depend on
- `app/db.py` — SQLite schema (`docs/schema.json`), `connect()`/`init_db()`, the `get_db()` request dependency shared by every router, and first-run seed data (mirrors `frontend/src/lib/kanban.ts`'s demo board)
- `app/board.py` — `/api/board`, `/api/columns/{id}`, `/api/cards` CRUD routes, all behind `require_auth`. Route handlers are thin wrappers around plain `apply_*` functions (`apply_rename_column`, `apply_create_card`, `apply_update_card`, `apply_delete_card`) plus `get_board`/`get_board_id`/`parse_id`, all reused by `app/chat.py` so the AI applies board changes through the exact same DB logic as the HTTP routes. The `apply_*` functions never commit — each caller owns its transaction boundary, so a route commits once per request and `chat()` commits once per turn (letting a failed AI operation roll the whole batch back)
- `app/ai.py` — OpenRouter client (`openai` SDK pointed at OpenRouter's base URL, model `openai/gpt-oss-120b`) and `/api/ai/ping`, behind `require_auth`
- `app/chat.py` — `/api/ai/chat` and `/api/ai/messages`, behind `require_auth`. Sends the current board (from `app/board.py`) plus persisted history as context, requests a structured `{reply, board_update}` JSON response, applies any `board_update` operations via `app/board.py`'s `apply_*` functions, and persists both sides of the turn to `chat_messages`
- `static/` — the Next.js static export (see root `Dockerfile`)
- `tests/` — pytest tests using FastAPI's `TestClient`; `conftest.py` has an autouse fixture pointing `DB_PATH` at a per-test temp file, so tests never touch the dev DB. `tests/fakes.py` holds the fake OpenAI client (`FakeClient(contents=[...], error=...)`) shared by `test_ai.py` and `test_chat.py`. `test_ai_integration.py` and `test_chat_integration.py` are marked `integration` and excluded from the default `uv run pytest` run (see `pyproject.toml`'s `addopts`); run them explicitly with `uv run pytest -m integration` (needs a real `OPENROUTER_API_KEY`, costs money/network)

## AI chat structured outputs

`openai/gpt-oss-120b` via OpenRouter does not reliably honor a JSON-schema `response_format`, even with `strict: true` (empirically ~30-40% of calls omit or rename a required field, e.g. `op` -> `operation`). `app/chat.py`'s `ask_structured` retries up to `MAX_STRUCTURED_ATTEMPTS` (3) on a parse/validation failure specifically — not on a genuine `APIError`, which still surfaces immediately as a 502. This was proven empirically (see `docs/PLAN.md` Part 9), not assumed; a single attempt with no retry failed the real integration test outright.

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
