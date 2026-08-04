# Database

## Engine and file location

SQLite, via a single file at `backend/data/app.db`, overridable with the `DB_PATH` env var (mirroring the `STATIC_DIR` pattern already used for the frontend static mount). The `data/` directory is created if missing and is not committed (it is in `.gitignore`).

Inside Docker that path is `/app/data/app.db`, backed by the `app-data` named volume declared in `docker-compose.yml`. The volume is what makes the board survive `scripts/stop.sh` + `scripts/start.sh`: without it the DB would live in the container's writable layer and be destroyed by `docker compose down`. To reset the board to seed data, run `docker compose down -v` (the `-v` removes the volume).

Tests never touch this file — `backend/tests/conftest.py` has an autouse fixture pointing `DB_PATH` at a per-test temp file.

## Creation strategy

No migration framework. On FastAPI startup (the `lifespan` hook in `app/main.py`), run `CREATE TABLE IF NOT EXISTS` for each table in `docs/schema.json`. If the `users` table is empty, seed it with the hardcoded `user`/`password` account, create one board for that user, and seed the board's columns/cards from the same demo data currently hardcoded in `frontend/src/lib/kanban.ts`. This keeps first-run behavior identical to today's in-memory demo, and deleting `app.db` fully resets the app on next start.

Initialization happens only at startup, not per request. Tests that need the DB therefore construct the client as `with TestClient(app)`, since a bare `TestClient(app)` does not run lifespan events.

Since this is MVP-only with no schema history to preserve, later schema changes can just edit the `CREATE TABLE` statements and delete the dev `app.db` rather than writing migrations.

## Ordering strategy

Both column order (within a board) and card order (within a column) use an integer `position` field (0-based), rather than an array-of-ids on the parent row. Reasons:
- Reordering/moving a card is a single-row `UPDATE` (and a small renumber of siblings), not a read-modify-write of a parent's array.
- It matches ordinary SQL querying (`ORDER BY position`) and keeps foreign keys pointing one direction (child -> parent), avoiding the two-way sync an array-of-ids would need.

When a card moves, the backend renumbers `position` for affected rows in the source and/or destination column (same approach the frontend's existing `moveCard` already does conceptually with array indices).

## IDs across the API boundary

DB primary keys are auto-incrementing integers. The API serializes them as strings (e.g. `"1"`) so the frontend's existing `Card`/`Column` types (which use `id: string`) don't need to change in Part 7 — only where those ids come from changes (server-generated instead of `createId()`).

## Users and auth

The `users` table exists so the schema supports multiple accounts later, but Part 6 does not change the Part 4 login flow: credentials stay hardcoded (`user`/`password`) and are not checked against `password_hash`. The single seeded `users` row exists only so `boards.user_id` has a valid foreign key to point at. Wiring real per-user auth against this table is out of scope for the MVP.
