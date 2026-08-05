# Frontend (Kanban Studio)

Next.js 16 / React 19 / TypeScript / Tailwind CSS 4 app. Session-authenticated, backend-persisted Kanban board — data is fetched from and saved to the FastAPI backend (see root `AGENTS.md` for the full MVP spec; AI chat sidebar is still pending, Part 10 of `docs/PLAN.md`).

## Stack

- Next.js 16 (App Router), React 19, TypeScript
- Tailwind CSS 4 (via `@tailwindcss/postcss`), custom CSS vars in `globals.css` for the brand palette
- `@dnd-kit/core` + `@dnd-kit/sortable` for drag-and-drop
- `clsx` for conditional classNames
- Fonts: Space Grotesk (display), Manrope (body), loaded via `next/font/google`

## Structure

- `src/app/layout.tsx` — root layout, loads fonts, sets metadata
- `src/app/page.tsx` — checks the session (`fetchSession`), redirects to `/login` if unauthenticated, otherwise renders `<KanbanBoard />` with `onLogout`/`onSessionExpired` callbacks
- `src/app/login/page.tsx` — login form; redirects to `/` if already authenticated
- `src/components/KanbanBoard.tsx` — top-level stateful component; fetches the board from `/api/board` on mount, owns `BoardData` state, drag sensors, loading/error states, and all mutation handlers (rename column, add/delete card, move card)
- `src/components/KanbanColumn.tsx` — one column: droppable zone, renamable title input (commits on blur/Enter, not per keystroke), card list, `NewCardForm`
- `src/components/KanbanCard.tsx` — one draggable/sortable card with a delete button
- `src/components/KanbanCardPreview.tsx` — static (non-interactive) card render used in `DragOverlay` while dragging
- `src/components/NewCardForm.tsx` — inline expand/collapse form for adding a card to a column; stays open with the user's input if the API call fails
- `src/lib/kanban.ts` — data model (`Card`, `Column`, `BoardData`) and `moveCard`, the pure reducer-style logic for drag-and-drop reordering, reused for the optimistic local update before the server confirms
- `src/lib/auth.ts` — `fetchSession`/`login`/`logout`, calling `/api/session`, `/api/login`, `/api/logout`
- `src/lib/api.ts` — board API client (`fetchBoard`, `renameColumn`, `createCard`, `moveCard`, `deleteCard`); throws `UnauthorizedError` on a 401 response so callers can redirect to login instead of showing an error banner; also prefixes/strips ids at the API boundary (see below)

## Data model

```ts
type Card = { id: string; title: string; details: string };
type Column = { id: string; title: string; cardIds: string[] };
type BoardData = { columns: Column[]; cards: Record<string, Card> };
```

Ids are strings issued by the backend (stringified SQLite row ids), not client-generated — but `board_columns` and `cards` are separate tables that each auto-increment independently, so a raw column id and a raw card id can collide (e.g. both `"3"`). `src/lib/api.ts` prefixes every id crossing the boundary (`col-<id>` / `card-<id>`) and strips the prefix back off before calling the backend, so `id: string` values are always globally unique above that layer — this matters because dnd-kit and `moveCard` require unique ids across the whole board, not just within a column. Never bypass `api.ts` to talk to `/api/board`, `/api/columns`, or `/api/cards` directly, and never assume an id is numeric.

Columns are a fixed, ordered list (Backlog, Discovery, In Progress, Review, Done) — reorderable content, not addable/removable columns. Cards live in a flat `cards` map keyed by id; each column stores an ordered array of card ids. See `docs/schema.json` / `docs/DATABASE.md` for how this maps to the database.

## Mutation strategy

- Rename, move (drag-and-drop), and delete are optimistic: local state updates immediately, the API call fires in the background, and on failure the board reverts to its pre-mutation snapshot plus an error banner.
- Add-card is not optimistic — it awaits the server response before adding the card locally, since the card's id is server-assigned. The form stays open with the user's input on failure so they can retry.
- A 401 from any board API call (session expired mid-use) calls `onSessionExpired`, which redirects to `/login` — it does not surface as an error banner.

## Static export and serving

`next.config.ts` sets `output: "export"`. `npm run build` produces a static `out/` directory (prerendered HTML + client JS bundles, no Node server needed). The root `Dockerfile` builds this in a `node` stage and copies `out/` into the FastAPI image's `static/` directory, where it's served at `/` via `StaticFiles`. There is no `next start`/server-side rendering in this project — everything client-side interactive (drag-and-drop, forms) hydrates from the static HTML.

## Testing

- Unit/component tests: Vitest + Testing Library (`npm run test:unit`) — `KanbanBoard.test.tsx` mocks `src/lib/api.ts` and asserts each action calls the right API function; `kanban.test.ts` tests `moveCard` directly; `api.test.ts` pins the id-prefixing behavior (mocking `fetch`, not the module) against a raw backend response with a deliberate column/card id collision
- E2E: Playwright (`npm run test:e2e`), spec in `tests/kanban.spec.ts`, run via `tests/run-e2e.mjs` (see below) against the real Docker/FastAPI build — there is no separate dev-mode or static-build suite, just this one
- `npm run test:all` runs unit + e2e

### E2E test isolation

E2E runs against the real backend and database, not mocks, using `docker-compose.e2e.yml` (repo root) to override the persistent `app-data` volume with a throwaway anonymous one, so mutations in the "add, rename, move, and delete" test never touch a real dev board and each run starts from a clean seeded DB.

`tests/run-e2e.mjs` (not `playwright test` directly) is what `npm run test:e2e` invokes. It force-clears any existing `app` container *before* starting Playwright, because Playwright's own `reuseExistingServer:false` port-conflict check runs before `globalSetup` would — a `globalSetup`-based cleanup was tried first and proved (by making it throw unconditionally) to run too late to help. Written in Node rather than a shell script since the project targets Mac/Linux/PC.

Because the e2e DB is destroyed and reseeded every run, locate columns by their known seed-data content (`.filter({ hasText: "..." })`) rather than guessing ids — but resolve the concrete `data-testid` once, up front, before any mutation. A locator built purely from a content filter is re-evaluated live, so once a test moves or renames the content it was matching on, the same locator can silently start resolving to a different column.

Use `data-testid` attributes already present (`column-<id>`, `card-<id>`) for e2e/unit selectors rather than adding new query strategies. Prefer `getByLabel` over `getByRole("button", ...)` for the delete button specifically — `useSortable` gives the card's own `<article>` `role="button"` too, and Chromium's accessible-name algorithm folds the nested button's label into the article's computed name, so a role+name query matches both ("strict mode violation").

## Conventions to follow when extending

- Keep `BoardData` normalized (columns reference card ids; don't nest full card objects in columns).
- Keep board mutation logic as pure functions in `src/lib/kanban.ts` where practical (like `moveCard`) — this is what optimistic local updates are built on.
- New board API calls belong in `src/lib/api.ts`, following the existing pattern (throw `UnauthorizedError` on 401, plain `Error` otherwise).
- Match the existing Tailwind CSS-variable-based theming (`var(--navy-dark)`, `var(--primary-blue)`, `var(--secondary-purple)`, `var(--accent-yellow)`, `var(--gray-text)`) rather than hardcoding new colors — these map to the palette in the root `AGENTS.md`.
