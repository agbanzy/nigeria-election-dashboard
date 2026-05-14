# DECISIONS — ADR-lite log

## 2026-05-14 — Pivot scope: FCT-only → pan-Nigeria, multi-cycle, with statistical analysis

Context: original repo tracked FCT 2026 Area Council elections only. Owner wants a national, multi-cycle (2015→present) dashboard with descriptive + comparative + statistical analysis, deployed on DigitalOcean App Platform.

Decision: full pivot in 4 phases — Foundation (Postgres + package split + DO deploy) → Pan-Nigeria live skeleton → Historical backfill + importer → Statistical layer + 2015/2019 ingest.

Consequences:
- Schema rewrite (SQLite → Postgres, unified across cycles)
- New worker component (scraper isolated from web)
- Historical data plane is first-class (importer CLI + provenance)
- Election calendar drives scraper wake + UI countdown
- ~70% of frontend components reusable; layout/branding refactored

Thread: pan-nigeria-refactor

## 2026-05-14 — Keep legacy `election_dashboard.py` during Phase A

Context: 2441-line monolith with ~30 routes. Full port in one phase is unrealistic and high-risk.

Decision: leave `election_dashboard.py` in repo unchanged during Phase A. New `backend/app/*` package serves the new routes. Legacy file deleted only when every route has a verified parity replacement (end of Phase B).

Consequences:
- Both apps coexist briefly
- Deploy spec runs only the new app (`gunicorn app.wsgi:app`)
- Parity tests compare new `/api/overview` etc. against fixtures captured from the legacy file's responses

Thread: pan-nigeria-refactor

## 2026-05-14 — Working folder on `~/Desktop/Election results/` (not `~/Innoedge/`)

Context: original plan said `~/Innoedge/fct-election-dashboard`. Owner redirected to `~/Desktop/Election results/`.

Decision: clone to `~/Desktop/Election results/`. Repo remote unchanged.

Consequences: working folder name no longer matches GitHub repo name. Future clones elsewhere are still `fct-election-dashboard`. Innoedge-folder workspace consolidation deferred.

Thread: pan-nigeria-refactor

## 2026-05-14 — Scraper wake policy: calendar-driven

Context: outside live election windows, year-round 2-min scraping wastes IReV proxy quota and our worker compute. Owner wants countdown UX + auto-wake at election time.

Decision: `scraper/daemon.py` reads `election_calendar` each loop iteration. Modes: 2-min cycle when any election `status='live'`; 5-min cycle within 6h of a scheduled election; 24h idle otherwise.

Consequences:
- Worker stays online but quiet
- Need to seed `election_calendar` with INEC's published schedule (Phase B)
- `/api/calendar/next` drives the homepage countdown component

Thread: pan-nigeria-refactor

## 2026-05-14 — Party-code normalization across cycles

Context: APC didn't exist before 2013 (merged from CPC + ACN + ANPP + part of APGA). Party acronyms have been reused (e.g. AD, ADC). Cross-cycle vote-share comparison requires a stable mapping.

Decision: `parties` table has `(code, active_from, active_to)` triple unique. `normalizers.party_code(raw, cycle)` resolves a raw code+cycle to a `party_id`. Imports flag any unmapped (raw, cycle) combinations and abort with a list; the operator updates the mapping file before re-running.

Consequences:
- Audited mapping is explicit and committed (data/party_mapping.csv)
- Pre-2013 results may need a "legacy_apc_predecessor" virtual party for visual continuity — TBD

Thread: pan-nigeria-refactor
