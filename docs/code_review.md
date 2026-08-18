# Code Review

Date: 2026-08-13
Scope: full repository (`backend/app`, `frontend/src`, Docker/scripts/config), excluding generated
output (`node_modules`, `.venv`, `.next`, `out/`). All findings below were read against the current
source and confirmed accurate, not taken on faith from the review pass that surfaced them.

All automated suites are green at time of review: backend `45/45` (`uv run pytest`), frontend unit
`32/32` (`npm run test:unit`), and the app's Docker start/stop cycle was verified working. This review
did not re-run Playwright e2e.

---

## Findings

### 1. [FIXED] AI chat operations apply without a transaction — a partial `board_update` can commit halfway through

**File:** `backend/app/chat.py:180-201` (`apply_operations`), called from `chat()` at `chat.py:225-226`

Each `apply_*` helper (`apply_rename_column`, `apply_create_card`, `apply_update_card`,
`apply_delete_card`, all in `backend/app/board.py`) calls `conn.commit()` itself. `apply_operations`
loops over the AI's operation list and calls these helpers with no surrounding transaction or
rollback. If operation *N* references a column/card id that doesn't exist, `parse_id`/`_require_column`/
`_require_card` raise `HTTPException(404)`, which propagates straight out of `chat()` — but operations
`1..N-1` already committed.

**Failure scenario:** The model (already documented as violating its own JSON schema ~30-40% of the
time — see `docs/PLAN.md` Part 9) returns three operations; the first two succeed and commit, the third
references a hallucinated id and 404s. The user gets a 502/404 error response, but the board has
already been silently mutated by the first two ops, and — because `_save_message` runs *after*
`apply_operations` (`chat.py:225-228`) — the chat turn that caused this is never persisted to
`chat_messages`. The user has no record of what happened and no way to correlate the board change with
a conversation turn. No test exercises this path; `test_chat.py` only covers all-succeed or
fails-before-any-mutation cases.

**Action:** Wrap `apply_operations` in a single transaction (SQLite: manual `BEGIN`, then either
`COMMIT` once at the end or `ROLLBACK` on any exception), or restructure so all operations are validated
against the current board state before any is applied. Add a test that a mid-batch invalid operation
leaves the board unchanged.

**Fixed:** the `apply_*` helpers in `board.py` no longer commit at all — each caller now owns its
transaction boundary. The HTTP routes commit once per request (behavior there is unchanged), and `chat()`
wraps the whole turn — every `board_update` operation plus both persisted chat messages — in one
`try`/`except` that rolls back on any exception and commits once at the end. Covered by
`test_chat_partial_batch_failure_rolls_back_all_operations` in `backend/tests/test_chat.py`.

---

### 2. [FIXED] `rename_column`/`create_card` silently blank a title instead of rejecting a null one

**File:** `backend/app/chat.py:182-183, 188-190`

```python
apply_rename_column(conn, parse_id(operation.column_id or ""), operation.title or "")
...
operation.title or "",
```

The `RESPONSE_FORMAT` JSON schema (`chat.py:96-101`) requires the `title` *key* to be present but
explicitly allows its value to be `null` (`"type": ["string", "null"]`). The system prompt tells the
model to "set title" for these two ops, but nothing enforces it, and this code coerces a `null`/missing
title into `""` rather than treating it as invalid input.

**Failure scenario:** The model — already shown empirically to omit/misname required fields at a
meaningful rate — returns `{"op": "rename_column", "column_id": "3", "title": null, ...}`. The column's
title is silently overwritten with an empty string. No exception, no log, no way for the user to know a
chat turn just corrupted a real column's title. The same applies to `create_card` (an untitled card is
created).

**Action:** Validate that `title` is non-empty (after `.strip()`) for `rename_column`/`create_card`
before calling into `board.py`, and raise a clear error (visible to the user, not silently swallowed)
rather than defaulting to `""`. Add a test asserting a null-title operation is rejected rather than
silently applied.

**Fixed:** `chat.py` now has `_require_title`, called for `rename_column` and `create_card` operations
before they're applied — a missing/blank title raises `HTTPException(502, ...)` instead of being
coerced to `""`, and (per Finding #1's fix) rolls back any earlier operations in the same batch rather
than leaving them committed. `update_card`'s `title` stays optional (`None` legitimately means "don't
change the title"), so it's intentionally not covered by this check. Covered by
`test_chat_rejects_null_title_for_rename_column` and `test_chat_rejects_empty_title_for_create_card`.

---

### 3. `SESSION_SECRET` has an insecure hardcoded fallback and is undocumented

**File:** `backend/app/main.py:34-38`

```python
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "dev-only-insecure-secret"),
    same_site="lax",
)
```

`SESSION_SECRET` is never set in `.env`, `.env.example`, or `docker-compose.yml`, and isn't mentioned in
any `AGENTS.md`. Every deployment following the documented setup runs with the literal, public string
`"dev-only-insecure-secret"` signing session cookies.

Per `docs/PLAN.md`'s Part 4 follow-up review, this was a known, explicitly-accepted tradeoff for the
MVP: forging a session cookie gains nothing over just logging in, since the credentials are hardcoded
and shown on the login page. That reasoning holds as long as the app only ever runs against the
hardcoded `user`/`password` account on `localhost`. It stops holding the moment this is exposed beyond
localhost or `users.password_hash` starts being checked for real (the column already exists for future
multi-user support) — at that point a known signing secret becomes a real account-takeover vector, not
a curiosity.

**Action:** No urgent fix needed for the current MVP scope, but: (a) document the fallback explicitly in
`.env.example` / `AGENTS.md` so it isn't rediscovered as a surprise, and (b) treat "generate and set a
real `SESSION_SECRET`" as a hard prerequisite before this app is ever deployed anywhere reachable or
before real password checking is wired up.

---

### 4. [FIXED] `get_db()` is duplicated verbatim between `board.py` and `chat.py`

**File:** `backend/app/board.py:46-51` and `backend/app/chat.py:119-124`

```python
def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
```

Identical in both files. The project's stated convention (`backend/AGENTS.md`) is that `chat.py` reuses
`board.py`'s logic specifically to avoid two code paths drifting apart — this dependency is the one
piece that wasn't consolidated.

**Action:** Define `get_db` once (e.g. in `app/db.py`, alongside `connect`/`init_db`) and import it from
both routers. Low risk, but relevant now: fixing Finding #1's transaction handling means this dependency
is about to need real logic (transaction scope), and two copies means two places to get it right.

**Fixed:** `get_db` now lives in `app/db.py` next to `connect`/`init_db`; `board.py` and `chat.py` both
import it.

---

### 5. [FIXED] Column rename input can lose an in-progress edit on a background board refresh

**File:** `frontend/src/components/KanbanColumn.tsx:25-31`

```tsx
const [titleDraft, setTitleDraft] = useState(column.title);
const [lastSyncedTitle, setLastSyncedTitle] = useState(column.title);

if (column.title !== lastSyncedTitle) {
  setLastSyncedTitle(column.title);
  setTitleDraft(column.title);
}
```

This "sync state from props during render" pattern re-derives `titleDraft` any time the `column.title`
prop changes for *any* reason — including a board refetch. `ChatSidebar` triggers exactly such a refetch
via `onBoardChanged` after *every* successful AI reply (`KanbanBoard.tsx:309`, `ChatSidebar.tsx:60`),
regardless of whether that reply's board data differs from the current column's title.

**Failure scenario:** A user clicks into a column's rename input and starts typing a new title but
hasn't blurred/committed it yet. Concurrently (or just before), an AI chat reply resolves and
`onBoardChanged` refetches the board. If the fetched `column.title` differs from `lastSyncedTitle` at
that render — which it will if the AI touched that column, or in principle any time the two diverge —
the effect-during-render overwrites `titleDraft` with the fetched value, discarding the user's
unsaved keystrokes with no warning.

**Action:** Only resync `titleDraft` when the input isn't focused/dirty (e.g. track a `isEditing`
flag set on focus and cleared on blur/commit, and skip the sync while `isEditing` is true), or debounce
board refreshes away from an actively-focused rename input.

**Fixed:** added an `isEditingTitle` flag, set `true` on the input's `onFocus` and cleared in
`commitTitle` (called on blur). The render-time prop sync now only fires when `!isEditingTitle`, so a
background refetch mid-edit no longer overwrites unsaved keystrokes. Covered by two new tests in
`frontend/src/components/KanbanColumn.test.tsx`: one confirming a focused, in-progress edit survives a
prop refresh and still commits correctly on blur, one confirming the prop still syncs normally when the
input isn't focused.

---

## Additional observations (not blocking, no action required)

- **Repo hygiene:** two stray directories exist at the repo root — `./backend;C` and
  `./backend/backend;C` — that don't correspond to anything in the documented structure and are almost
  certainly leftover from a malformed shell command at some point. They're empty/inert but worth
  deleting to avoid confusion; confirm with whoever's working tree this is before removing, since they
  weren't touched by this review.
- **Password comparison** in `backend/app/auth.py:22` (`payload.password != PASSWORD`) isn't
  constant-time, but per the existing Part 4 review in `docs/PLAN.md` this was already judged low-value
  to fix given the credentials are hardcoded and displayed on the login page. Revisit only alongside
  Finding #3 if real auth is ever wired up.
- **Docker build** (`Dockerfile`), **DB layer** (`backend/app/db.py`), and **AI ping route**
  (`backend/app/ai.py`) were reviewed and are sound — no findings. `check_same_thread=False` in
  `db.py:119` is correctly justified by the existing comment (each request gets its own connection).
- Test coverage is otherwise strong for the areas it does cover (id-collision prefixing, optimistic
  revert-on-failure, 401 redirects, structured-output retry logic) — the gaps flagged above (Findings
  #1 and #2) are specifically *because* those scenarios aren't covered yet, not a general coverage
  problem.

---

## Priority summary

| # | Finding | Severity | Effort to fix | Status |
|---|---|---|---|---|
| 1 | No transaction around multi-op AI board updates | High — silent partial data mutation | Medium | Fixed |
| 2 | Null title silently blanks column/card title | Medium — silent data corruption, narrow trigger | Small | Fixed |
| 5 | Rename input can lose unsaved edits on refetch | Medium — user-visible data loss | Small | Fixed |
| 4 | Duplicated `get_db()` | Low — maintenance hazard only | Trivial | Fixed |
| 3 | `SESSION_SECRET` insecure default, undocumented | Low today, high if ever deployed beyond localhost | Small (docs) / Medium (real fix) | Open |
