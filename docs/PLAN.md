# High level steps for project

See root `AGENTS.md` for business requirements, technical decisions, and coding standards. This document breaks the work into parts, each with a checklist, tests, and success criteria. Work proceeds part by part; each part should be complete (tests passing) before starting the next, unless the user directs otherwise.

---

## Part 1: Plan

- [x] Enrich this document with substeps, tests, and success criteria per part
- [x] Create `frontend/AGENTS.md` describing the existing frontend code
- [ ] User checks and approves the plan

**Success criteria:** user has explicitly signed off on this document before Part 2 begins.

---

## Part 2: Scaffolding

- [x] Create `backend/` FastAPI app skeleton using `uv` for dependency management (`pyproject.toml`, `uv.lock`)
- [x] Add a single `GET /api/hello` route returning a small JSON payload (e.g. `{"message": "Hello from FastAPI"}`)
- [x] Serve a static `index.html` (placeholder, not yet the real frontend) from FastAPI at `/`, which calls `/api/hello` via fetch on load and displays the result
- [x] Write a `Dockerfile` (single-stage for now; build context is the repo root so `frontend/` can be added in Part 3) and `docker-compose.yml` that runs the FastAPI app
- [x] Write `scripts/start.sh` / `stop.sh` (Mac/Linux) and `scripts/start.ps1` / `stop.ps1` (PC), wrapping `docker compose up`/`down`
- [x] Update `backend/AGENTS.md` and `scripts/AGENTS.md` with real descriptions replacing the placeholder text
- [x] Add root `.env.example` documenting `OPENROUTER_API_KEY` — note: no `.env` file actually exists in the repo yet (despite root `AGENTS.md` assuming one); `docker-compose.yml` treats it as optional (`required: false`) so `docker compose up` works until Part 8 needs the real key

**Tests:**
- Backend: a `pytest` test hitting `/api/hello` with FastAPI's `TestClient`, asserting 200 and expected JSON shape
- Manual/script-level: starting the container and curling `/` and `/api/hello` returns expected results

**Success criteria:** running the start script boots a Docker container; visiting `http://localhost:<port>/` in a browser shows the placeholder page successfully displaying data fetched from the API; stop script cleanly stops the container; `pytest` passes.

---

## Part 3: Add in Frontend

- [x] Configure Next.js for static export (`output: "export"` in `next.config.ts`)
- [x] Update FastAPI to serve the exported static frontend build (`frontend/out`, copied to `backend`'s static dir at Docker build time) at `/` — `STATIC_DIR` is now configurable via env var
- [x] Update Docker build to be multi-stage: `node` stage builds the Next.js static export, copied into the final `uv`/Python image
- [x] Start/stop scripts unchanged (still just wrap `docker compose`); no changes needed
- [x] Confirmed the existing Kanban demo (in-memory, no backend calls yet) renders correctly when served this way

**Tests:**
- [x] Existing frontend unit tests (Vitest) and e2e tests (Playwright, dev-mode) continue to pass — verified: 6/6 unit, 3/3 e2e
- [x] Added e2e tests (`tests/kanban.spec.ts`, run via `npm run test:e2e`), which build and run the real Docker image and assert the Kanban board renders seed data and drag-and-drop works when served by FastAPI — verified: 3/3 passing
- [x] Backend test decoupled from the real frontend build (tests the static-mount mechanism generically via a fixture dir + `STATIC_DIR` env var, rather than depending on frontend content) — verified: 2/2 passing
- [x] Manually verified via `curl` that a JS chunk referenced by the built page (`/_next/static/chunks/...`) is served correctly (200) through FastAPI, not just the HTML shell

**Success criteria:** met. `docker compose up` (via `scripts/start.sh`) serves the actual Kanban UI at `/`; drag-and-drop and card editing work (still in-memory only); all frontend and backend test suites pass.

**Note:** couldn't do a live interactive browser check (Claude-in-Chrome extension not connected in this session) — verification relied on Playwright automation against the real Docker container plus manual curl checks instead.

---

## Part 4: Add in a fake user sign in experience

- [x] Add a login page/form requiring username `user` / password `password` (hardcoded per AGENTS.md)
- [x] On success, set a session (simple signed cookie or server-side session token — no need for JWT complexity or expiry logic given MVP scope) so refreshing stays logged in
- [x] Redirect unauthenticated requests for the Kanban view to the login page; redirect authenticated users hitting login to the board
- [x] Add a logout action that clears the session and redirects to login
- [x] Backend: add `/api/login`, `/api/logout`, and session-check middleware/dependency protecting Kanban-related routes (routes don't exist yet until Part 6, but the auth dependency should exist now for reuse)

**Tests:**
- [x] Backend unit tests: correct credentials succeed and set a session cookie; incorrect credentials return 401; protected route without session returns 401/redirect; logout clears session — verified: 8/8 passing (`backend/tests/test_auth.py` + `test_hello.py`)
- [x] Frontend/e2e: cannot reach board content without logging in; login with correct credentials shows the board; wrong credentials shows an error; logout returns to login and re-blocks access — verified: 8/8 Playwright e2e passing against the real Docker build; 11/11 Vitest unit tests passing

**Success criteria:** met. A fresh browser session is forced to log in before seeing the Kanban board; logout works; all new tests pass alongside existing ones.

**Note:** manual live-browser click-through was attempted via the Claude-in-Chrome extension but blocked by a password-manager autofill popup stealing tab focus (unrelated to the app). Verification instead relied on the full automated suite above plus a partial manual check (fresh-tab unauthenticated redirect to `/login`, and logout redirecting back to `/login`), both confirmed working.

**Follow-up review (after Part 6).** Re-verified against the running Docker build; no regressions (11/11 Vitest, 8/8 Playwright, backend green). Findings:

- *Test gap closed.* Auth was only *proven* for `GET /api/board` — the other four board routes relied on the router-level `dependencies=[Depends(require_auth)]` with nothing asserting it, so the protection could be silently lost. Added parametrized coverage for all five routes plus a test that rejected requests leave the board unmutated. Confirmed load-bearing: removing the dependency fails exactly those 6 tests.
- *Auth itself is sound.* Manually probed every route unauthenticated (all 401, nothing mutated). Session cookie is signed, `httponly`, `samesite=lax`, and correctly expired on logout.
- *Redirect is client-side by design.* Because the frontend is a static export, Next.js middleware does not run and `GET /` returns 200 with the HTML shell to anonymous users — the only "Kanban Studio" text in it is the `<title>` tag, not board content, so the e2e assertion is valid. The real security boundary is the API, which is correctly enforced. Worth stating plainly so "cannot reach board content without logging in" is not read as server-side route protection.
- *Seed data is currently public.* The demo cards are compiled into a JS chunk that anyone can fetch without a session. This is inherent to Part 4's in-memory demo and resolves itself in Part 7, when board data moves behind `GET /api/board`.
- *`SESSION_SECRET` is unset in Docker*, so the hardcoded default is used. Not worth fixing for this MVP: the credentials are themselves hardcoded and displayed on the login page, so forging a cookie gains nothing over logging in.

---

## Part 5: Database modeling

- [x] Propose a schema (tables: `users`, `boards`, `columns`, `cards`, with foreign keys and ordering columns for column/card sequence) even though MVP only needs one user and one board — schema should support multiple users/boards for the future per AGENTS.md limitations
- [x] Save the schema as JSON (e.g. `docs/schema.json`) describing tables, columns, types, and relationships
- [x] Write `docs/DATABASE.md` documenting the approach: SQLite, file location, migration/creation-on-first-run strategy, how ordering of columns/cards is stored (e.g. integer `position` field vs array-of-ids)
- [x] Get explicit user sign-off on the schema before implementing it in Part 6

**Tests:** none (design-only part), but schema JSON should be valid JSON (lint-checked).

**Success criteria:** user has reviewed and approved `docs/schema.json` and `docs/DATABASE.md`.

---

## Part 6: Backend

- [x] Implement SQLite database using the approved schema; create the DB file and tables automatically if the file doesn't exist on startup
- [x] Add API routes (all behind the auth dependency from Part 4): `GET /api/board` (fetch current user's board with columns+cards), `PATCH /api/columns/{id}` (rename), `POST /api/cards`, `PATCH /api/cards/{id}` (edit/move), `DELETE /api/cards/{id}`
- [x] Seed the database with the same demo data currently hardcoded in `frontend/src/lib/kanban.ts` on first run, so behavior matches today's demo
- [x] Backend unit tests using a temporary/in-memory SQLite DB per test (not the real dev DB)

**Tests:**
- [x] CRUD coverage: create card, rename column, move card between columns, move card within a column (reorder), delete card, fetch full board — verified: `backend/tests/test_board.py`
- [x] Edge cases: fetching board with no data yet (first run auto-seeds), invalid ids return 404, unauthenticated requests return 401
- [x] DB-creation test: deleting the DB file and starting the app recreates it with seed data; a second startup against an existing DB does not re-seed over edits
- [x] Full suite: 22/22 passing (`uv run pytest`)
- [x] Schema conformance: `docs/schema.json` diffed programmatically against the SQLite tables the code actually creates — all tables, column types, nullability, primary keys, foreign keys, and the `users.username` unique index match

**Success criteria:** met. All backend routes work correctly via `pytest` + `TestClient` against a real (temp) SQLite file, matching the schema from Part 5. Also verified against the real Docker build: renamed a column and added a card, ran `scripts/stop.sh` + `scripts/start.sh`, and confirmed both changes persisted; `docker compose down -v` resets to seed data.

**Two issues found in a follow-up review and fixed:**
1. *Data loss across restarts.* `docker-compose.yml` had no volume for `/app/data`, so the SQLite file lived in the container's writable layer and was destroyed by `stop.sh` (`docker compose down`) — every stop/start silently reset the board. Fixed with an `app-data` named volume; verified by round-tripping real edits through a full stop/start cycle.
2. *Untested startup path + per-request waste.* `init_db()` was being called from the per-request `get_db()` dependency, so the schema script ran on every API request, and the documented "created on startup" path was never exercised by tests (a bare `TestClient(app)` does not run lifespan events, which was masking this). Removed the per-request call; tests now use `with TestClient(app)` so they cover the real production path, plus a `conftest.py` autouse fixture guarantees no test can touch the dev DB.

**Note:** the local `uv` CLI wasn't on PATH in this environment, so tests were run inside a throwaway `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` container (`docker run -v backend:/app ... uv run pytest`) rather than natively; a stale `.venv` left over from a previous container build (broken interpreter symlink) was removed and resynced first.

---

## Part 7: Frontend + Backend

- [ ] Replace in-memory `useState`/`initialData` in `KanbanBoard.tsx` with data fetched from `/api/board` on load
- [ ] Wire `onRename`, `onAddCard`, `onDeleteCard`, and drag-and-drop move handlers to call the corresponding API routes, updating local state optimistically or after response
- [ ] Handle loading and error states (e.g. API unreachable, session expired mid-use redirects to login)
- [ ] Keep `src/lib/kanban.ts`'s pure logic (like `moveCard`) reusable for optimistic local updates before/independent of server confirmation

**Tests:**
- Frontend unit tests: components correctly call the API client functions on each action (mock fetch/API layer)
- E2E (Playwright): full flow — log in, add a card, rename a column, drag a card to another column, delete a card, reload the page, and confirm all changes persisted (i.e. came from the backend, not just local state)
- Backend tests from Part 6 still passing

**Success criteria:** reloading the browser preserves all board changes; e2e test suite exercises the full persistent loop end-to-end against the real backend (not mocks) using a test DB.

**Carried over from the Part 4/6 review — handle in this part:**
- E2E tests now run against a *persistent* `app-data` volume. Today that is harmless (the board is in-memory, so e2e mutations touch nothing), but once the board is server-backed, tests like "adds a card" will mutate real state and leak between runs, making the suite order-dependent. Point the e2e container at a throwaway DB (override `DB_PATH` or use a disposable volume) as part of wiring the frontend up.
- The existing e2e tests address cards/columns by the frontend's hardcoded ids (`card-card-1`, `column-col-review`). The backend issues integer ids (`"1"`, `"2"`), so these selectors must be updated when the board starts loading from `/api/board`.

---

## Part 8: AI connectivity

- [ ] Add OpenRouter client setup in the backend (reading `OPENROUTER_API_KEY` from `.env`), using `openai/gpt-oss-120b`
- [ ] Add a minimal `/api/ai/ping` (or similar) route that sends a "what is 2+2?" prompt and returns the model's response, to prove connectivity end-to-end
- [ ] Handle and surface API errors (missing key, network failure, bad response) clearly rather than silently failing

**Tests:**
- Backend test that calls the real OpenRouter API (may be a manual/integration test rather than part of the default fast test suite, since it costs money/network) and asserts a sane response containing "4"
- Unit test with a mocked OpenRouter client verifying request shape (model name, prompt) and error handling paths

**Success criteria:** hitting the ping route returns a real AI-generated answer confirming "4" (or similar), proving the OpenRouter integration is correctly configured.

---

## Part 9: Structured AI chat with Kanban context

- [ ] Extend the AI route to accept a user message + conversation history, and always include the current board's JSON as context in the prompt/system message
- [ ] Use Structured Outputs (OpenRouter/OpenAI-compatible `response_format` with a JSON schema) so the model returns `{ reply: string, board_update: <optional patch/replacement> | null }`
- [ ] Define the `board_update` schema (decide during implementation: full board replace vs. targeted operations like "move card X to column Y" — favor the simplest approach that keeps the model's job easy and validates cleanly against the DB schema)
- [ ] If `board_update` is present, apply it to the database using the same logic/routes as Part 6 (reuse, don't duplicate)
- [ ] Persist conversation history (in DB or in-memory per session — decide based on simplicity; DB preferred for consistency with "survives refresh" expectations)

**Tests:**
- Unit tests with a mocked AI client: given a canned structured response, confirm the board is updated correctly in the DB and the reply text is returned to the caller
- Integration test (real API call, manual/tagged as slow): ask the AI to "move the card about X to Done" against a known seeded board and confirm the resulting DB state
- Validation test: malformed/unexpected structured output from the model is handled gracefully (no crash, clear error)

**Success criteria:** sending a natural-language instruction that implies a board change results in the correct DB update and a sensible chat reply, verified by both a mocked unit test and at least one real end-to-end call.

---

## Part 10: AI chat sidebar UI

- [ ] Add a sidebar component with a chat interface (message list + input) styled per the brand palette in root `AGENTS.md`
- [ ] Wire it to the Part 9 chat route, sending user messages and conversation history, displaying the AI's reply
- [ ] When a response includes a board update, refresh the Kanban board view automatically (refetch from `/api/board` or apply the returned patch directly) without a full page reload
- [ ] Handle loading/error states in the chat UI (e.g. "thinking...", API failure message)

**Tests:**
- Frontend unit tests: chat component sends correct payload, renders messages, triggers board refresh callback when a board update is present
- E2E (Playwright): send a chat message that requests a card move via the real (or a test-mode) AI backend, confirm the chat shows a reply and the Kanban board visibly updates without manual refresh

**Success criteria:** user can ask the AI in the sidebar to make a change to the Kanban board, see a conversational reply, and see the board update live in the UI — completing the full MVP described in root `AGENTS.md`.
