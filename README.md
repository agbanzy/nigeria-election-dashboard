<div align="center">

# 🇳🇬 Nigeria Election Dashboard

**Live, open electoral data for Nigeria — every race, every cycle, one dashboard.**

[![CI](https://github.com/agbanzy/nigeria-election-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/agbanzy/nigeria-election-dashboard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-00a651.svg)](LICENSE)
[![Live](https://img.shields.io/badge/live-elections.innoedgetech.com-008751)](https://elections.innoedgetech.com)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-00a651.svg)](CONTRIBUTING.md)
[![Buy Me A Coffee](https://img.shields.io/badge/☕-Buy%20me%20a%20coffee-ffdd00)](https://buymeacoffee.com/agbanzy)

[**Open the dashboard**](https://elections.innoedgetech.com) · [**Public API**](docs/API.md) · [Report a bug](https://github.com/agbanzy/nigeria-election-dashboard/issues)

</div>

---

Election results in Nigeria are scattered across PDFs, press conferences, and
paywalled trackers. This project puts them in one free, open place: live INEC
IReV scraping on election day, curated historical results back to 2015, and
the statistical lenses (turnout, swing, competitiveness) that make the numbers
mean something — Presidential down to Area Council, national down to ward.

## Features

- **Live on election day** — a polite, rate-limited scraper follows INEC IReV
  and streams updates over SSE
- **Deep history** — INEC-certified results from 2015 to present, importable
  from CSV/PDF with full provenance tracking
- **Real analysis** — turnout, margin, ENP (Laakso–Taagepera), swing, and a
  competitiveness index, not just bar charts
- **Maps all the way down** — interactive choropleths from national → state →
  LGA → ward
- **Free public API** — every number on the dashboard is one `curl` away.
  Free keys, by application → [apply here](https://elections.innoedgetech.com/api-access) ·
  [docs/API.md](docs/API.md)
- **Open methodology** — sources, formulas, and known gaps documented
  [on-site](https://elections.innoedgetech.com/methodology)

## Public API

The dashboard is free for everyone with no account. The API is free too —
[apply for a key](https://elections.innoedgetech.com/api-access) (name, email,
what you're building), get approved, and go:

```bash
curl -H "X-API-Key: ned_..." "https://elections.innoedgetech.com/api/analysis/winners?cycle=2023&type=presidential"
curl -N -H "X-API-Key: ned_..." https://elections.innoedgetech.com/api/live/events   # SSE during live elections
```

Full endpoint reference: **[docs/API.md](docs/API.md)**.

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

## Quick start

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

Env-var reference: [`backend/.env.example`](backend/.env.example) and
[`frontend/.env.example`](frontend/.env.example) — every backend var is
declared in `app/config.py`.

### Admin users (auth)

The dashboard and API are public — only `/admin` (results ingestion: manual
entry, OCR-assist, bulk import) requires a signed-in admin:

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

## Deploy (DigitalOcean App Platform)

```bash
doctl apps create --spec .do/app.yaml
# Set the secret env vars (NEXTAUTH_SECRET, ADMIN_TOKEN, SEED_USERS)
doctl apps update <app-id> --spec .do/app.yaml
doctl apps create-deployment <app-id>
```

The `migrate` PRE_DEPLOY job runs Alembic; POST_DEPLOY jobs populate
states / parties / calendar (`seed`), historical results (`seed-historical`),
and admin users (`seed-users`).

## Historical importer

```bash
python -m app.importer.cli load \
  --file data/historical/2023_presidential_state.csv \
  --cycle 2023 --type presidential --aggregation state \
  --source stears_2023 --license proprietary \
  --url https://stears.co/elections/2023
```

Every row must conform to `app.importer.schemas.ResultRow`. Unmapped party
codes abort the import — extend `app.importer.normalizers.HISTORICAL_MAPPING`
and re-run.

## Statistical metrics

| Metric | Formula |
|---|---|
| Turnout | accredited / registered |
| Margin | (winner − runner-up) / total |
| ENP (Laakso–Taagepera) | 1 / Σ(share²) |
| Swing | Δ share between cycles |
| Competitiveness | (1 − margin) × turnout × min(ENP/3, 1) |

Definitions and provenance: `/api/methodology` and the on-site
[methodology page](https://elections.innoedgetech.com/methodology).

## Data sources & licensing

- INEC IReV (live + 2023 backfill)
- Stears and Dataphyte (2019 + 2023, state level)
- INEC archived PDFs (2015 + 2019) via OCR
- Wikidata (top-of-ticket sanity checks)

The **code** is MIT-licensed ([LICENSE](LICENSE)). The **datasets** under
`backend/data/historical/` are election-result facts compiled from the sources
above and remain subject to those sources' own terms — verify before
redistributing them outside this project. Takedown contact: methodology page.

## Contributing & collaboration

PRs, issues, and data corrections are welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md). Security reports go through
[SECURITY.md](SECURITY.md), not public issues.

Beyond this repo: I'm **open to collaborating on vital open-source projects
for good** — election transparency, civic data, identity, payments
infrastructure for Africa. Reach out: **godwin@innoedgetech.com** ·
[agbanegodwin.me](https://agbanegodwin.me).

## Support

If this project saves you a scrape, a subscription, or a press-conference
transcription session:

<a href="https://buymeacoffee.com/agbanzy"><img src="https://img.shields.io/badge/☕-Buy%20me%20a%20coffee-ffdd00?style=for-the-badge" alt="Buy Me A Coffee"></a>

## License

[MIT](LICENSE) © 2026 [Innoedge Technologies Ltd](https://innoedgetech.com)
