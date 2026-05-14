# Nigeria Election Dashboard

Pan-Nigeria, multi-cycle election results + statistical analysis.
Started as `agbanzy/fct-election-dashboard` (FCT 2026 Area Council only) — pivoted
in 2026-05 to cover Presidential, Governorship, Senate, House of Reps, State HoA,
and LG / Area Council races from 2015 to present, deployed on DigitalOcean App
Platform.

## Architecture

```
   INEC IReV ──► [worker: scraper]   ┐
                                     ▼
   CSV/PDF ────► [job: importer] ──► [managed Postgres 15]
                                     │
   Browser ◄──── [web: Flask API] ◄──┤
                                     │
   Browser ◄──── [static: Next.js] ◄─┘
```

Backend: Python 3.11 + Flask + SQLAlchemy 2 + Alembic.
Frontend: Next.js 14 (App Router) + Tailwind + recharts + SWR + react-leaflet.
Data: managed Postgres on DO App Platform.

See [the design plan](/Users/godwinagbane/.claude/plans/logical-giggling-puzzle.md)
for the full architecture and migration phases. Project-local coordination state
in [`.claude/state/`](.claude/state/).

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

## Tests

```bash
cd backend
pytest                    # everything (testcontainers boots Postgres)
pytest -k "not integration"   # pure-function only, no Docker required
```

## Deploy to DO App Platform

```bash
doctl apps create --spec .do/app.yaml
# Set the secret env vars
doctl apps update <app-id> --spec .do/app.yaml
# Trigger a fresh deploy
doctl apps create-deployment <app-id>
```

The `migrate` PRE_DEPLOY job runs Alembic; the `seed` POST_DEPLOY job populates
states / parties / known election calendar.

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

## Data sources

- INEC IReV (live + 2023 backfill) via the dolphin-app proxy
- Stears, Dataphyte for 2019 + 2023 at state level
- INEC archived PDFs (2015 + 2019) via OCR
- Wikidata for top-of-ticket sanity checks

Known gaps documented on `/methodology`. Takedown contact: see methodology page.
