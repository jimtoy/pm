# Frontend (Kanban Studio)

Next.js 16 / React 19 / TypeScript / Tailwind CSS 4 app. Currently a frontend-only demo with in-memory state (no backend, no persistence, no auth) — this is the starting point for the full project described in the root `AGENTS.md`.

## Stack

- Next.js 16 (App Router), React 19, TypeScript
- Tailwind CSS 4 (via `@tailwindcss/postcss`), custom CSS vars in `globals.css` for the brand palette
- `@dnd-kit/core` + `@dnd-kit/sortable` for drag-and-drop
- `clsx` for conditional classNames
- Fonts: Space Grotesk (display), Manrope (body), loaded via `next/font/google`

## Structure

- `src/app/layout.tsx` — root layout, loads fonts, sets metadata
- `src/app/page.tsx` — renders `<KanbanBoard />` at `/`
- `src/components/KanbanBoard.tsx` — top-level stateful component; owns `BoardData` state, drag sensors, and all mutation handlers (rename column, add/delete card, move card)
- `src/components/KanbanColumn.tsx` — one column: droppable zone, renamable title input, card list, `NewCardForm`
- `src/components/KanbanCard.tsx` — one draggable/sortable card with a delete button
- `src/components/KanbanCardPreview.tsx` — static (non-interactive) card render used in `DragOverlay` while dragging
- `src/components/NewCardForm.tsx` — inline expand/collapse form for adding a card to a column
- `src/lib/kanban.ts` — data model (`Card`, `Column`, `BoardData`), `initialData` seed, `moveCard` (pure reducer-style logic for drag-and-drop reordering across/within columns), `createId` helper

## Data model (current, in-memory only)

```ts
type Card = { id: string; title: string; details: string };
type Column = { id: string; title: string; cardIds: string[] };
type BoardData = { columns: Column[]; cards: Record<string, Card> };
```

Columns are a fixed, ordered list (Backlog, Discovery, In Progress, Review, Done) — reorderable content, not addable/removable columns. Cards live in a flat `cards` map keyed by id; each column stores an ordered array of card ids. This normalized shape is intentional and should be preserved/reused as the API contract when the backend is introduced.

## Known gaps vs. the full MVP spec (expected — not bugs)

- No authentication/session handling.
- No backend calls; all state is local `useState`, lost on refresh.
- No AI chat sidebar.

## Static export and serving

`next.config.ts` sets `output: "export"`. `npm run build` produces a static `out/` directory (prerendered HTML + client JS bundles, no Node server needed). The root `Dockerfile` builds this in a `node` stage and copies `out/` into the FastAPI image's `static/` directory, where it's served at `/` via `StaticFiles`. There is no `next start`/server-side rendering in this project — everything client-side interactive (drag-and-drop, forms) hydrates from the static HTML.

## Testing

- Unit/component tests: Vitest + Testing Library (`npm run test:unit`), e.g. `KanbanBoard.test.tsx`, `kanban.test.ts` (tests `moveCard` logic directly)
- E2E against `next dev`: Playwright (`npm run test:e2e`), spec in `tests/kanban.spec.ts`
- E2E against the real Docker/FastAPI-served static build: `npm run test:e2e:static` (uses `playwright.static.config.ts`, spec in `tests/static-build.spec.ts`) — this runs `docker compose up --build` as its web server, so it needs Docker running and takes longer than the dev-mode suite
- `npm run test:all` runs unit + dev-mode e2e (not the static/Docker suite, which is separate due to cost)

Use `data-testid` attributes already present (`column-<id>`, `card-<id>`) for e2e/unit selectors rather than adding new query strategies.

## Conventions to follow when extending

- Keep `BoardData` normalized (columns reference card ids; don't nest full card objects in columns).
- Keep board mutation logic as pure functions in `src/lib/kanban.ts` where practical (like `moveCard`), called from the stateful component — makes it easy to unit test and later replace local `useState` with API-backed state/fetch calls.
- Match the existing Tailwind CSS-variable-based theming (`var(--navy-dark)`, `var(--primary-blue)`, `var(--secondary-purple)`, `var(--accent-yellow)`, `var(--gray-text)`) rather than hardcoding new colors — these map to the palette in the root `AGENTS.md`.
