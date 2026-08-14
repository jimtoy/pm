# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Project Management MVP: a session-authenticated, single-board-per-user Kanban app with an AI chat sidebar
that can create/edit/move cards. NextJS static frontend served by a FastAPI backend, packaged as one Docker
container. Full business requirements, technical decisions, and coding standards live in the root `AGENTS.md`
— read it first. Detailed per-area docs live in `backend/AGENTS.md`, `frontend/AGENTS.md`, `scripts/AGENTS.md`,
`docs/DATABASE.md`, and `docs/PLAN.md` (a part-by-part build log with real bugs found and fixed — worth
searching before assuming something is a new bug). Treat all `AGENTS.md` files as authoritative; this file
only summarizes what's needed to get moving.

## Coding standards (from root AGENTS.md)

1. Use latest versions of libraries and idiomatic approaches as of today.
2. Keep it simple — never over-engineer, always simplify, no unnecessary defensive programming, no extra
   features beyond what's asked.
3. Be concise; no emojis ever.
4. When hitting issues, identify root cause before fixing. Do not guess — prove with evidence, then fix the
   root cause. (See `docs/PLAN.md` for examples of this in practice, e.g. the structured-output retry logic
   and the column/card id-collision bug.)

## Commands

### Backend (`backend/`, FastAPI + `uv`)

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload   # run locally
uv run pytest                          # unit tests (integration tests excluded by default)
uv run pytest -m integration           # real OpenRouter calls; needs OPENROUTER_API_KEY, costs money/network
uv run pytest tests/test_board.py -k test_name   # single test
```

### Frontend (`frontend/`, Next.js 16 / React 19 / TypeScript)

```bash
cd frontend
npm run dev            # dev server
npm run build           # static export to out/ (output: "export", no Node server)
npm run lint
npm run test:unit       # Vitest + Testing Library
npm run test:unit:watch
npm run test:e2e        # Playwright, via tests/run-e2e.mjs — builds/runs the real Docker image, do not call `playwright test` directly
npm run test:all        # unit + e2e
```

### Whole app (Docker — normal way to run/verify the app)

```bash
scripts/start.sh   # or start.ps1 on Windows; wraps `docker compose up --build -d`, prints http://localhost:8000
scripts/stop.sh    # or stop.ps1; wraps `docker compose down`
docker compose down -v   # also reset the DB to seed data
```

## Architecture

- **One Docker image**: a `node` build stage produces the Next.js static export (`frontend/out`), copied into
  the final `uv`/Python image's `static/` directory; FastAPI serves it at `/` via `StaticFiles`. There is no
  Next.js server-side rendering — everything interactive hydrates client-side from static HTML.
- **Auth**: hardcoded credentials (`user`/`password`, per MVP scope), a signed session cookie, `require_auth`
  FastAPI dependency protects all `/api/...` routes except login. The frontend's unauthenticated-redirect is
  client-side only (static export, no middleware) — the real security boundary is the API.
- **Database**: SQLite at `backend/data/app.db` (`DB_PATH` env var to override), created/seeded on FastAPI
  startup (`lifespan` hook in `app/main.py`), not per-request. No migrations — schema lives in `docs/schema.json`
  and is edited directly + dev DB deleted when it changes. Persisted via the `app-data` Docker volume so it
  survives `stop`/`start`; e2e tests override that volume with a throwaway one (`docker-compose.e2e.yml`).
- **Board data model**: `board_columns` and `cards` are separate tables, each auto-incrementing independently
  — a column and a card can share a raw numeric id. `frontend/src/lib/api.ts` prefixes every id at the API
  boundary (`col-<id>` / `card-<id>`) so ids are globally unique above that layer; this is required by dnd-kit
  and `moveCard()`. Never call `/api/board`, `/api/columns`, or `/api/cards` directly — always go through
  `api.ts`. Column/card ordering uses an integer `position` field, not an array-of-ids.
- **Backend route/logic split**: route handlers in `app/board.py` are thin wrappers around plain `apply_*`
  functions (`apply_rename_column`, `apply_create_card`, `apply_update_card`, `apply_delete_card`). `app/chat.py`
  calls the exact same `apply_*` functions to execute AI-issued board operations, so the AI and the HTTP API
  share one code path — never duplicate board-mutation logic for the chat feature.
- **AI chat** (`app/chat.py`, `app/ai.py`): OpenRouter (`openai` SDK, model `openai/gpt-oss-120b`) with a
  structured `{reply, board_update: BoardOperation[] | None}` response. This model does not reliably honor
  `response_format` even with `strict: true` (~30-40% of calls violate the schema empirically) — `ask_structured`
  retries up to `MAX_STRUCTURED_ATTEMPTS` (3) on parse/validation failure specifically, not on a genuine
  `APIError` (which still surfaces as a 502 immediately). Conversation history persists in `chat_messages`,
  keyed by `board_id`. Don't "fix" the retry loop without re-reading `docs/PLAN.md` Part 9 — it's load-bearing,
  proven empirically, not defensive-programming cruft.
- **Frontend mutation strategy**: rename/move/delete are optimistic (local update, API call in background,
  revert + error banner on failure); add-card is not optimistic (id is server-assigned). A 401 on any board
  call redirects to `/login` via `onSessionExpired` rather than showing an error banner.
- **Frontend structure**: `KanbanBoard.tsx` is the top-level stateful component (fetches board, owns state,
  drag sensors, mutation handlers). `src/lib/kanban.ts` holds pure logic (`moveCard`) reused for optimistic
  updates. `src/lib/api.ts` / `src/lib/chatApi.ts` are the only places that talk to the backend.

## Testing notes

- Backend tests need `with TestClient(app)` (not a bare `TestClient(app)`) to run lifespan events (DB init).
  `conftest.py`'s autouse fixture points `DB_PATH` at a per-test temp file — tests never touch the dev DB.
- E2E (`frontend/tests/kanban.spec.ts`) runs against the real Docker/FastAPI build, not mocks or dev mode —
  it's the only frontend e2e suite. One test exercises the real OpenRouter backend via chat.
- E2E locators: resolve a column's `data-testid` once, up front, before any mutation — Playwright locators
  built from a content filter (`.filter({ hasText: ... })`) re-evaluate live and can silently re-target after
  a drag/rename changes what they match. Prefer `getByLabel` over `getByRole("button", ...)` for the delete
  button — dnd-kit's `useSortable` puts `role="button"` on the card's own `<article>` too, which Chromium
  folds into the accessible name and causes a strict-mode collision.
