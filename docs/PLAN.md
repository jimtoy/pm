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

- [ ] Configure Next.js for static export (`output: "export"` in `next.config.ts`)
- [ ] Update FastAPI to serve the exported static frontend build (`frontend/out`, copied to `backend`'s static dir at Docker build time) at `/`
- [ ] Update Docker build to be multi-stage: `node` stage builds the Next.js static export, copied into the final `uv`/Python image
- [ ] Start/stop scripts unchanged (still just wrap `docker compose`); no changes needed
- [ ] Confirm the existing Kanban demo (in-memory, no backend calls yet) renders correctly when served this way

**Tests:**
- Existing frontend unit tests (Vitest) and e2e tests (Playwright, dev-mode) continue to pass
- Add e2e test(s) that build and run the real Docker image and assert the Kanban board renders seed data and drag-and-drop works when served by FastAPI
- Backend test for the static-mount mechanism (fixture dir + `STATIC_DIR` env var), decoupled from the real frontend build
- Manually verify via `curl` that a JS chunk referenced by the built page is served correctly through FastAPI, not just the HTML shell

**Success criteria:** `docker compose up` (via `scripts/start.sh`) serves the actual Kanban UI at `/`; drag-and-drop and card editing work (still in-memory only); all frontend and backend test suites pass.

---

## Part 4: Add in a fake user sign in experience

- [ ] Add a login page/form requiring username `user` / password `password` (hardcoded per AGENTS.md)
- [ ] On success, set a session (simple signed cookie or server-side session token — no need for JWT complexity or expiry logic given MVP scope) so refreshing stays logged in
- [ ] Redirect unauthenticated requests for the Kanban view to the login page; redirect authenticated users hitting login to the board
- [ ] Add a logout action that clears the session and redirects to login
- [ ] Backend: add `/api/login`, `/api/logout`, and session-check middleware/dependency protecting Kanban-related routes (routes don't exist yet until Part 6, but the auth dependency should exist now for reuse)

**Tests:**
- Backend unit tests: correct credentials succeed and set a session cookie; incorrect credentials return 401; protected route without session returns 401/redirect; logout clears session
- Frontend/e2e: cannot reach board content without logging in; login with correct credentials shows the board; wrong credentials shows an error; logout returns to login and re-blocks access

**Success criteria:** a fresh browser session is forced to log in before seeing the Kanban board; logout works; all new tests pass alongside existing ones.

---

## Part 5: Database modeling

- [ ] Propose a schema (tables: `users`, `boards`, `columns`, `cards`, with foreign keys and ordering columns for column/card sequence) even though MVP only needs one user and one board — schema should support multiple users/boards for the future per AGENTS.md limitations
- [ ] Save the schema as JSON (e.g. `docs/schema.json`) describing tables, columns, types, and relationships
- [ ] Write `docs/DATABASE.md` documenting the approach: SQLite, file location, migration/creation-on-first-run strategy, how ordering of columns/cards is stored (e.g. integer `position` field vs array-of-ids)
- [ ] Get explicit user sign-off on the schema before implementing it in Part 6

**Tests:** none (design-only part), but schema JSON should be valid JSON (lint-checked).

**Success criteria:** user has reviewed and approved `docs/schema.json` and `docs/DATABASE.md`.

---

## Part 6: Backend

- [ ] Implement SQLite database using the approved schema; create the DB file and tables automatically if the file doesn't exist on startup
- [ ] Add API routes (all behind the auth dependency from Part 4): `GET /api/board` (fetch current user's board with columns+cards), `PATCH /api/columns/{id}` (rename), `POST /api/cards`, `PATCH /api/cards/{id}` (edit/move), `DELETE /api/cards/{id}`
- [ ] Seed the database with the same demo data currently hardcoded in `frontend/src/lib/kanban.ts` on first run, so behavior matches today's demo
- [ ] Backend unit tests using a temporary/in-memory SQLite DB per test (not the real dev DB)

**Tests:**
- CRUD coverage: create card, rename column, move card between columns, move card within a column (reorder), delete card, fetch full board
- Edge cases: fetching board with no data yet (first run auto-seeds), invalid ids return 404, unauthenticated requests return 401
- DB-creation test: deleting the DB file and starting the app recreates it with seed data

**Success criteria:** all backend routes work correctly via `pytest` + `TestClient` against a real (temp) SQLite file, matching the schema from Part 5.

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
