# UPDATES — append-only changelog (newest at top)

## 2026-07-18 — open-source hardening — LICENSE, env-driven user seeding, credential rotation
- Repo formally open-sourced (it was already public): MIT `LICENSE`, public-facing `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `backend/.env.example` + `frontend/.env.example`.
- `seed_users.py` no longer carries bcrypt hashes — reads `SEED_USERS` env (JSON array of email/name/role/password_hash), set as an encrypted env on the `seed-users` job. Unset = no-op, so deploys never depend on it.
- The two previously-committed hashes are burned: both dashboard passwords rotated 2026-07-18 via `SEED_USERS` + redeploy. Hashes remain in public git history but no longer match any live credential.
- Data-licensing note added to README (historical CSVs subject to Stears/Dataphyte source terms).

## 2026-05-30 — infra — moved to elections.innoedgetech.com (LIVE)
- App now reachable at **https://elections.innoedgetech.com** (HTTPS 200, serves the Next.js dashboard + `/api/results`, `/api/health`).
- DB: the old managed cluster `unimarket-staging-pg` referenced in `.do/app.yaml` is **gone** from the account, which blocked all spec edits. Repointed the app to a self-contained App Platform dev PG (`databases: [{name: db, engine: PG, production: false}]`, ~$7/mo); the app's own `migrate`/`seed`/`seed-historical` jobs repopulated the 2023 INEC results. No data lost (old cluster's data was already gone).
- Routing: App Platform's edge **could not** route `elections.innoedgetech.com` because the parent apex `innoedgetech.com` is owned by a *different* app (marketing site) and was stuck CONFIGURING. Worked around with a **Caddy reverse-proxy droplet** (`elections-proxy`, 165.227.160.43, fra1, ~$4/mo) + Name.com A-record. See `~/memory/concepts/ms365-tenant-domains.md` for the full root-cause + reusable pattern.
- DNS: `innoedgetech.com` zone moved DO → **Name.com** (registrar-level control); `elections` = A → 165.227.160.43.
- App ID unchanged: `d71eb896-bf3e-4d14-830e-2930ecc48c37`. Proxy is a separate box — if the app's `*.ondigitalocean.app` ingress hostname ever changes, update the Caddyfile on the droplet.

## 2026-05-14T21:15Z — pan-nigeria-refactor — Phase A + B-frontend skeleton complete

Backend (`backend/app/`):
- Flask app factory, env-driven Config, SQLAlchemy + Postgres engine, normalized DATABASE_URL handling
- 9 ORM models (states, lgas, wards, polling_units, parties, elections, candidates, ingestion_sources, election_results, scrape_log, election_calendar)
- Alembic env + initial migration `0001_initial.py`
- Scraper module: IReV HTTP client w/ token bucket + retries, election type registry (CHAIRMAN/COUNCILLOR known, 5 placeholders for Phase B), calendar-driven wake decision (`live` 2-min / `preflight` 5-min / `idle` 24h), discovery + LGA-structure phases, one-shot backfill CLI, daemon entry
- Importer module: Pydantic ResultRow + CandidateRow schemas, party-code normalizers (APC predecessors handled), Click CLI, working `generic_csv` + `excel_candidates` loaders + stubs for Stears/Dataphyte/INEC-PDF/Wikidata
- Analysis module: ENP (Laakso–Taagepera), turnout, margin, swing (LAG-style), competitiveness index — all pure-function and unit-tested
- API blueprints: health, calendar, states, elections (with /standings + stats), candidates, results, analysis (turnout/enp/swing/competitiveness/timeline), scrape (status), methodology, live (SSE), overview
- Seed script: 37 states with codes/zones, 13 default parties, 2027-cycle election_calendar placeholders
- OCR module: facade for EC8A parsing — port from legacy deferred to Phase D
- All 45 Python files parse; pure analysis smoke tests pass (ENP 50/30/20 = 2.6316 — matches academic synthetic)

Frontend (`frontend/src/`):
- `lib/branding.ts` — central title/tagline + scope composition
- `lib/electionTypeConfig.ts` — 7 election types with labels + tier
- `lib/api.ts` — typed API helpers + interfaces
- `context/FilterContext.tsx` — URL-param-backed filter state, Suspense-wrapped in Providers
- New components: ElectionCountdown, StateSelector, CycleSelector, ElectionTypeSelector, EnpBadge, MarginBar, SwingArrow, MethodologyDisclosure, NigeriaChoropleth (state grid; full Leaflet map = Phase B)
- New pages: `/methodology`, `/states/[stateCode]`, `/cycles/[year]`, `/cycles/compare`, `/live`
- Refactored: `Header.tsx` (branding-aware + selectors), `Sidebar.tsx` (new nav: States, Cycles, Live, Methodology), `layout.tsx` (metadata), `Providers.tsx` (FilterProvider + Suspense), `page.tsx` (national overview, replaces FCT-only home)
- `package.json` adds: react-leaflet, leaflet, @types/leaflet, date-fns, eslint-config-next

Deploy + CI:
- `.do/app.yaml`: web (Flask) + worker (scraper) + static_site (Next) + db (managed PG15) + migrate (PRE_DEPLOY) + seed (POST_DEPLOY)
- `.github/workflows/ci.yml`: backend ruff + mypy + pytest; frontend lint + build
- `.gitignore` updated to keep `.claude/state/` committed

Tests (`backend/tests/`):
- `conftest.py` — testcontainers Postgres fixture; Alembic upgrade/downgrade per test
- `test_analysis.py` — 11 pure-function tests inc. ENP(50/30/20) = 2.63
- `test_normalizers.py` — party-code historical mapping invariants
- `test_calendar.py` — wake decision (idle / preflight / live)
- `test_api_health.py` — full Flask + Postgres integration (health, overview, states, calendar/next)
- `test_importer.py` — CSV import end-to-end, including unknown-state rejection

Status: Phase A backend foundation **complete**. Phase B frontend skeleton **complete**. Phases C + D scaffolded with stubs; require historical data ingestion + MV migrations + OCR port to fully ship.

Legacy pages (`/elections`, `/analytics`, `/messaging`) compile but reference legacy `/api/lga-breakdown`, `/api/chairmanship-race`, etc. that the new backend doesn't yet serve. Phase B re-implements them against the new shape.

`election_dashboard.py` (legacy 2441-line monolith) and `election_data.db` (26MB SQLite fixture) intentionally retained in repo until end of Phase B parity verification.

Files: ~100 created/modified across backend + frontend.
Commit: pending.
