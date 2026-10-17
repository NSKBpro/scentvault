# ScentVault 2.0 — what changed

Mapped against the October 2026 review (broken flows, security, architecture, data model, UX, new features). "✅" = done and covered by a test or a build check.

## Broken flows (all 12)

| # | Was | Now |
| --- | --- | --- |
| 1 | Mobile search → "No fragrances found" (API returned a bare nested list) | `GET /catalog/fragrances` returns `Page<FragranceListItem>` with `brand_name`, sizes, min price, families; search matches fragrance **or brand**; real `page`/`size`/`sort` ✅ |
| 2 | Deals and export queried `price_entries` (table gone) | Deals and export use `price_logs`; drops are compared **per (fragrance, size)** against the previous five logs or the reference price ✅ |
| 3 | Embedding background task crashed on an ImportError | Embeddings go through a job queue (arq/Redis, or in-process when Redis is down); model encoding runs off the event loop ✅ |
| 4 | Price history called an admin-only endpoint → 403 | Public `GET /fragrances/{id}/price-history`, one series per size ✅ |
| 5 | Admin notes create/edit/delete hit missing endpoints | Full CRUD for notes (and every lookup) ✅ |
| 6–7 | Admin pickers empty; fake pagination | Fixed by #1; light list rows; `size` up to 500 for pickers ✅ |
| 8 | Dashboard downloaded the whole catalog to count | `GET /admin/stats` with counts and **work queues** ✅ |
| 9 | Scent DNA missed Fougère/Leather (keyword matching) | `families.axis` column; DNA is a join ✅ |
| 10 | Opening Collection online wiped unsynced offline adds | Outbox replays first; refresh never deletes unsynced rows; adds carry `client_ref` so replays can't duplicate ✅ |
| 11 | One bad import row aborted the rest; prominence written as 50 | One savepoint per row; single 1–5 prominence scale ✅ |
| 12 | Seed script crashed; `crud/` dead code | New idempotent seeds (incl. the 157-note CSV, families with axes, accords, occasions, retailers, optional demo catalog); dead code removed ✅ |

## Security

- Export requires admin; JWT secret is required (placeholders rejected); CORS from settings, `*` refused; admin login refuses non-admins; mobile/admin URLs from env; no secrets in the repo (`.env.example` only) ✅
- Rotating refresh tokens stored hashed, reuse detection revokes the family; logout revokes ✅
- Rate limits on login/register/refresh and the AI endpoints; AI search requires auth ✅
- One admin dependency; no f-string SQL outside the whitelisted vector filters ✅

## Architecture

- Monorepo: `apps/api`, `apps/admin`, `apps/mobile`, `packages/api-types` (generated from OpenAPI; CI fails if stale).
- API layered as routers → services → repositories; typed request/response schema for every endpoint (no bare dicts); all config via `get_settings()`; lifespan builds the embedding model, Ollama/weather/push clients and the job queue once and closes them on shutdown.
- One baseline Alembic migration (`0001_baseline`) matching the models: VARCHAR + CHECK instead of PG enums, `timestamptz` everywhere, CASCADE on child tables (RESTRICT brand → fragrance), pgvector HNSW and trigram indexes. `alembic check` runs in CI.
- Tests: 45 API tests against real Postgres + pgvector (auth, catalog, collection, similarity/dupes, AI search, wear log, daily pick incl. weather, prices/alerts/push, admin, import/export, and the legacy migration on a replica of the old schema). ruff + mypy clean.
- `scripts/migrate_legacy.py` + `./tasks.ps1 upgrade-v1` move the pre-2.0 database across.

## Mobile UX

- Fifth tab **Diary**; **Profile & settings** from the Home avatar (name, password, currency, city, gender preference, notification toggles, sync status, sign out).
- **Your bottles** on the detail screen: every entry for that fragrance, each editable in a bottle sheet (status, bottle type, size, price + currency, purchase date, rating with half stars, remaining, notes, favourite, finish, sold/gifted, remove).
- Collection: status chips with counts (Owned / Wishlist / Tried / Archive), family chips, sort incl. "longest unworn", one-tap wear, decant/sample badges, sync indicators.
- Bottle images with initial fallback everywhere; skeleton loaders; a mounted toaster; distinct offline / error / empty states; onboarding checklist for new users; radar hidden until it has data.
- "Spent" counts what you paid for bottles you own(ed), converted to your currency; cost per wear from real wears (estimate labelled as such until there are five).
- Discover returns results immediately and fetches the explanation afterwards; blind-buy card uses real shared notes.
- Readability/accessibility: tab labels 11 px, muted text ≥ 4.5:1 contrast, visible card borders, labels on every icon-only control and star.

## Admin UX

Work-queue dashboard, real server pagination and sorting, split fragrance form with note search and live embedding-text preview, embeddings page (coverage, stale/other-model counts, regenerate missing/all with progress), notes CRUD + CSV import, price logger and history, retailers, users, CSV import (preview → confirm) and ZIP export (including a round-trippable `catalog.csv`).

## New features

1. **Full bottle editing** — statuses `own / wishlist / tried / finished / sold / gifted`, bottle types, multiple sizes, `PATCH`, `/finish`, `/sell`.
2. **Wear log** — `POST/GET/DELETE /wears`, `GET /wears/stats` (most/least worn, shelf time, per month, rotation spread, compliments, real cost per wear); offline-queued.
3. **Wishlist price alerts** — `/alerts` CRUD, notification inbox, Expo push, checked on every new price log and daily, 7-day cooldown; plus running-low (≤ 15 %) and neglected (60 days) nudges, each switchable.
4. **Smarter daily pick** — weather (Open-Meteo) + occasion + season + rating + rotation scoring with tunable weights, top 3 with reason chips, never yesterday's bottle, LLM only phrases one sentence (name-checked), `pick_shown` / `pick_accepted` logged for later tuning.

## Not done / next

- Bottle photos taken by the user (needs file storage).
- Exchange rates are static (configurable in `.env`).
- Push in Expo Go is limited; use an EAS development build for real pushes.
