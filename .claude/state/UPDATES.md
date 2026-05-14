# UPDATES — append-only changelog (newest at top)

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
