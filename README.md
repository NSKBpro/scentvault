# ScentVault

Your fragrance collection, with a memory. ScentVault tracks the bottles you own, what you wear each day, what things cost, and uses embeddings + an optional local LLM to recommend what to wear today and what to try next.

| App | Stack | Where |
| --- | --- | --- |
| **API** | FastAPI · SQLAlchemy 2 (async) · Postgres 16 + pgvector · arq/Redis · sentence-transformers · Ollama (optional) | `apps/api` |
| **Mobile** | Expo 54 · React Native 0.81 · React Navigation 7 · Zustand · SQLite offline cache | `apps/mobile` |
| **Admin** | React 19 · Vite 7 · TanStack Query · Tailwind | `apps/admin` |
| **API types** | TypeScript generated from the API's OpenAPI schema, shared by both clients | `packages/api-types` |

## What it does

- **Collection** — owned / wishlist / tried / finished / sold / gifted; full bottles, decants, samples, testers; several sizes of the same fragrance; price in any currency, purchase date, notes, favourites. Works offline and syncs later (no duplicates on replay).
- **Diary (wear log)** — one tap "wearing this today", sprays lower the bottle level, month calendar, most worn, *shelf time* (unworn 60+ days), rotation spread, real cost per wear.
- **Today's pick** — top 3 from your shelf scored on weather (Open-Meteo, no key), occasion, season, rating, and how recently you wore each — never yesterday's bottle. Every pick explains itself with reason chips.
- **Discover** — natural-language search ("warm vanilla for winter evenings under 150, no patchouli"): results in well under a second, the advisor's explanation streams in after. Recommendations from bottles you rated 4★+, with the shared notes spelled out.
- **Deals** — price drops per bottle size, cheaper alternatives compared *per ml*, and wishlist **price alerts** with push notifications (plus running-low and neglected-bottle nudges).
- **Admin** — catalog CRUD with a split fragrance form and live embedding-text preview, real pagination, a work-queue dashboard (missing notes/images/prices/embeddings, stale prices), embeddings coverage + regenerate, price logger, CSV import with preview and export.

## Quick start (Windows / PowerShell)

Prerequisites: Docker Desktop, Python 3.12+, Node 22+.

```powershell
git clone https://github.com/<you>/scentvault.git; cd scentvault
./tasks.ps1 setup                      # venv + npm installs, creates .env from .env.example
# edit .env: set POSTGRES_PASSWORD and JWT_SECRET (python -c "import secrets; print(secrets.token_hex(32))")
./tasks.ps1 up                         # Postgres (pgvector) + Redis
./tasks.ps1 migrate                    # baseline schema
./tasks.ps1 demo                       # reference data + ~24 demo fragrances  (or: ./tasks.ps1 seed)
./tasks.ps1 admin-user -AdminEmail you@example.com -AdminPassword "something-long"
./tasks.ps1 api                        # http://localhost:8004/api/docs
./tasks.ps1 worker                     # background jobs (optional: without Redis/worker, jobs run inside the API)
./tasks.ps1 admin                      # http://localhost:5173
```

macOS / Linux / WSL: the same targets exist in the `Makefile` (`make setup up migrate demo api …`).

### Mobile

```powershell
cd apps/mobile
copy .env.example .env                 # EXPO_PUBLIC_API_URL=http://<your PC's LAN IP>:8004
npx expo start                         # scan the QR code with Expo Go (same Wi-Fi)
```

Push notifications need a development build with an EAS project id (`eas init`); in Expo Go everything else works and notifications still show in the Deals tab.

### AI pieces (all optional, everything degrades gracefully)

- **Embeddings**: `pip install -e ".[ml]"` installs sentence-transformers (all-MiniLM-L6-v2). Without it the API uses a deterministic hashing embedder — fine for trying things out, weaker similarity. After installing, run *Admin → Embeddings → Regenerate all*.
- **LLM**: install [Ollama](https://ollama.com) and `ollama pull llama3.2`. Used to parse search queries and phrase explanations; rule-based fallbacks cover everything when it's off.

## Upgrading from the pre-2.0 version (one time)

Your old database lives in the same Docker volume, so the new compose file picks it up. Keep `POSTGRES_PASSWORD` in `.env` equal to the password that volume was created with (it was `password`), then:

```powershell
./tasks.ps1 upgrade-v1
```

It backs the database up to `backups/`, renames it to `scentvault_legacy`, creates a fresh `scentvault` at the 2.0 schema, seeds reference data and copies everything across (`scripts/migrate_legacy.py`): brands, notes, families (with a radar axis), accords, occasions, fragrances and their relations, prices, price logs, embeddings made by the same model, users (passwords keep working) and collections. Duplicates are merged and reported. Drop `scentvault_legacy` once you're happy.

## Development

```text
scentvault/
├─ apps/
│  ├─ api/              FastAPI — app/{api,services,repositories,models,schemas,core,workers}, alembic/, seeds/, scripts/, tests/
│  ├─ admin/            Vite + React admin panel
│  └─ mobile/           Expo app
├─ packages/api-types/  generated TS types (do not edit — run `./tasks.ps1 types`)
├─ docker-compose.yml   db + redis (+ `--profile app` for api/worker, `--profile ollama`)
├─ tasks.ps1 / Makefile
└─ docs/
```

**API layering.** Routers only do HTTP; services hold the rules and get their session and resources through constructors; repositories hold the queries (raw SQL only for pgvector, in `repositories/vectors.py`). Long-lived clients (embedding model, Ollama, weather, push, job queue) are built once in the FastAPI lifespan (`app/resources.py`) and injected via `Depends`.

**Background jobs.** `JOB_QUEUE=auto` sends jobs to Redis/arq when it's reachable and otherwise runs them inside the API process, so a bare `uvicorn` works too. The worker also runs a daily job (06:15 UTC): re-check price alerts, neglected-bottle nudges, embed anything missing.

**After changing the API** run `./tasks.ps1 types` — CI fails if `packages/api-types` is stale.

**Tests** run against a real Postgres with pgvector (the baseline migration builds the schema):

```powershell
docker exec scentvault_db psql -U scentvault -c "CREATE DATABASE scentvault_test"
$env:TEST_DATABASE_URL="postgresql+asyncpg://scentvault:<password>@localhost:5432/scentvault_test"
./tasks.ps1 test
```

**Configuration** is all in `.env` (see `.env.example`); `JWT_SECRET` is required and placeholder values are rejected at startup. Daily-pick weights are tunable with `PICK_WEIGHT_*` variables.

See [`docs/CHANGES-2.0.md`](docs/CHANGES-2.0.md) for everything that changed in 2.0, item by item against the October 2026 review.
