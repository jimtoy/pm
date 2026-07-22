# Backend

FastAPI app managed with `uv`. Entry point: `app/main.py`.

## Structure

- `pyproject.toml` / `uv.lock` — dependencies (`fastapi`, `uvicorn`; dev: `pytest`, `httpx`)
- `app/main.py` — FastAPI app; `GET /api/hello` route; mounts `static/` at `/` to serve the frontend
- `static/` — currently a placeholder `index.html`; from Part 3 onward this holds the Next.js static export
- `tests/` — pytest tests using FastAPI's `TestClient`

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
