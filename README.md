# Nigeria Election Dashboard

**Live at [elections.innoedgetech.com](https://elections.innoedgetech.com)**

Pan-Nigeria, multi-cycle election results + statistical analysis. Covers
Presidential, Governorship, Senate, House of Reps, State Assembly, and
LG / Area Council races from 2015 to present — live INEC IReV scraping on
election day, curated historical results in between. Started as an
FCT-2026-only dashboard and pivoted to national coverage in 2026-05.

## Architecture

```
   INEC IReV ──► [worker: scraper]   ┐
                                     ▼
   CSV/PDF ────► [job: importer] ──► [managed Postgres]
                                     │
   Browser ◄──── [web: Flask API] ◄──┤
                                     │
   Browser ◄──── [static: Next.js] ◄─┘
```

Backend: Python 3.11 + Flask + SQLAlchemy 2 + Alembic.
Frontend: Next.js 14 (App Router) + Tailwind + recharts + SWR + react-leaflet.
Data: managed Postgres (DigitalOcean App Platform).

## Local dev

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# Start Postgres locally (or set DATABASE_URL to a hosted one)
docker run --rm -d --name elec-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:15
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/postgres

alembic upgrade head
python -m app.seed
gunicorn -w 2 -b 0.0.0.0:8080 app.wsgi:app

# In another terminal
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8080 npm run dev
```

Full env-var reference: [`backend/.env.example`](backend/.env.example) and
[`frontend/.env.example`](frontend/.env.example) — every backend var is
declared in `app/config.py`.

### Admin users (auth)

The dashboard itself is public — only `/admin` (results ingestion) requires
a signed-in admin. Create a local admin either way:

```bash
# Interactive CLI
FLASK_APP=app.wsgi flask auth create-user you@example.com "Your Name" --role admin

# Or via the SEED_USERS env var (JSON array; bcrypt hashes, never plaintext)
export SEED_USERS='[{"email":"you@example.com","name":"Your Name","role":"admin","password_hash":"$2b$12$..."}]'
python -m app.seed_users
```

No credentials — hashed or otherwise — live in this repo. In production
`SEED_USERS` is an encrypted App Platform env var consumed by the
`seed-users` POST_DEPLOY job.

## Tests

```bash
cd backend
pytest                    # everything (testcontainers boots Postgres)
pytest -k "not integration"   # pure-function only, no Docker required
```

CI (`.github/workflows/ci.yml`) runs ruff + mypy + pytest on the backend and
lint + build on the frontend.

## Deploy to DO App Platform

```bash
doctl apps create --spec .do/app.yaml
# Set the secret env vars (NEXTAUTH_SECRET, ADMIN_TOKEN, SEED_USERS)
doctl apps update <app-id> --spec .do/app.yaml
# Trigger a fresh deploy
doctl apps create-deployment <app-id>
```

The `migrate` PRE_DEPLOY job runs Alembic; POST_DEPLOY jobs populate
states / parties / election calendar (`seed`), historical results
(`seed-historical`), and dashboard users (`seed-users`).

## Historical importer

```bash
python -m app.importer.cli load \
  --file data/historical/2023_presidential_state.csv \
  --cycle 2023 --type presidential --aggregation state \
  --source stears_2023 --license proprietary \
  --url https://stears.co/elections/2023
```

Schema: every row must conform to `app.importer.schemas.ResultRow`. Unmapped
party codes abort the import — extend `app.importer.normalizers.HISTORICAL_MAPPING`
and re-run.

## Statistical metrics

| Metric | Formula | Source |
|---|---|---|
| Turnout | accredited / registered | computed on the fly |
| Margin | (winner − runner-up) / total | computed on the fly |
| ENP (Laakso–Taagepera) | 1 / Σ(share²) | `mv_enp` (Phase D) |
| Swing | Δ share between cycles | `mv_swing` (Phase D) |
| Competitiveness | (1 − margin) × turnout × min(ENP/3, 1) | `mv_competitiveness` (Phase D) |

See `/api/methodology` and the on-site `/methodology` page for definitions and
ingestion provenance.

## Data sources & licensing

- INEC IReV (live + 2023 backfill) via the dolphin-app proxy
- Stears, Dataphyte for 2019 + 2023 at state level
- INEC archived PDFs (2015 + 2019) via OCR
- Wikidata for top-of-ticket sanity checks

The **code** in this repo is MIT-licensed (see [LICENSE](LICENSE)). The
**datasets** under `backend/data/historical/` are election-result facts
compiled from the sources above and remain subject to those sources' own
terms — verify before redistributing them outside this project. Known gaps
and provenance are documented on `/methodology`; takedown contact is listed
there.

## Contributing & security

See [CONTRIBUTING.md](CONTRIBUTING.md). Report vulnerabilities privately per
[SECURITY.md](SECURITY.md) — not via public issues.
