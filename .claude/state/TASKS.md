# TASKS — pan-Nigeria election dashboard refactor

Single source of truth for outstanding work. Coordinate across chat threads via OPEN-THREADS.md.

## In progress

- [ ] Phase A — backend package skeleton + Postgres migration + parity tests
- [ ] Phase A — `.do/app.yaml` deployable spec
- [ ] Phase A — port legacy routes to blueprints (incremental)

## Pending — Phase B (pan-Nigeria live skeleton)

- [ ] Generalize scraper to all 37 states (`scraper/daemon.py` state loop)
- [ ] Discover IReV election type IDs for Presidential, Governorship, Senate, House of Reps, State HoA (currently only Chairman/Councillor known). Persist in `scraper/election_types.py`.
- [ ] Seed `election_calendar` with known 2027 cycle dates (Presidential + NASS Feb 2027; off-cycle Gov: Anambra Nov 2025, Ekiti June 2026, Osun July 2026 — verify against INEC notices)
- [ ] Frontend: `<StateSelector>`, `<CycleSelector>`, `<ElectionCountdown>`, `<NigeriaChoropleth>` (state-level GADM GeoJSON)
- [ ] `/states/[stateCode]/page.tsx`, `/methodology/page.tsx` (stub OK at this stage)
- [ ] Replace hardcoded "FCT 2026 Area Council Elections" in `Header.tsx`, `Sidebar.tsx`, `layout.tsx` metadata, `page.tsx` subtitles via `lib/branding.ts`

## Pending — Phase C (historical backfill + importer)

- [ ] `scraper/backfill.py` — one-shot IReV crawl for 2023 + 2020 cycles
- [ ] Importer CLI: `python -m app.importer load --file ... --cycle ... --type ... --source ...`
- [ ] Loaders: `stears.py` (2023 Pres/Gov state), `dataphyte.py` (2019+2023 NASS state), `inec_pdf.py` (2015+2019 Pres/Gov LGA via OCR), `wikidata.py` (sanity check)
- [ ] Frontend: `/cycles/[year]`, `/cycles/compare`
- [ ] Methodology page populated with real sources + ingestion timestamps

## Pending — Phase D (statistical layer + analytics UI)

- [ ] Materialized views: `mv_turnout_by_state_cycle`, `mv_enp`, `mv_swing`, `mv_competitiveness`
- [ ] Optional `mv_moran_i` (spatial autocorrelation)
- [ ] `/analytics/page.tsx` — ENP trend, swing matrix, competitiveness choropleth
- [ ] OCR pipeline ingest 2015 + 2019 Presidential + Gov LGA-level
- [ ] `pytest tests/test_analysis.py::test_enp_synthetic` — synthetic 50/30/20 → 2.63
- [ ] e2e QA pass via `browser-qa` skill, screenshots into `./tmp/qa-phaseD/`

## Cross-cutting

- [ ] Stears licensing outreach (or limit to sanity-check role)
- [ ] LGA GeoJSON delivery decision (ship with static site vs CDN)
- [ ] Custom domain on DO App Platform (deferred to post-launch)
- [ ] Takedown contact on `/methodology` (legal mitigation)

## Audit 2026-07-19 (Open)

From the multi-persona audit — synthesis at `.claude/state/audits/2026-07-19/10-synthesis.md`. Ordered by priority. Effort: S=<1d, M=~3d, L=~1sprint.

### Critical — Sprint 1 (stop-the-bleeding before the next live election)
- [ ] [CRITICAL] F-102/F-404 Add DB unique constraint on vote natural key + upsert-on-conflict + dedupe backfill (M)
- [ ] [CRITICAL] F-201/F-701 Fail-closed `_require_admin` + assert ADMIN_TOKEN at startup + commit as SECRET on web service (S)
- [ ] [CRITICAL] F-101 Stopgap: filter analysis reads to canonical grain + partial unique index blocking mixed grains per election (L, start)
- [ ] [CRITICAL] F-302 Micro-cache pollable read endpoints + instance_count 2 + gthread/gevent workers (M)
- [ ] [CRITICAL] F-301 Replace Python-side row hydration in standings/_votes_by_party/_stats with SQL GROUP BY (M)
- [ ] [CRITICAL] F-703/F-203 Add flask-limiter on /api/auth/login + /api/developer/apply (M)
- [ ] [CRITICAL] F-402 Semantic healthcheck (staleness threshold) + external uptime/staleness probe + alert (M)
- [ ] [CRITICAL] F-601+F-604+F-605 ruff --fix, add frontend/.eslintrc.json, re-enable CI to a green run (S)
- [ ] [CRITICAL] F-903/F-409/F-313/F-111 Cap SQLAlchemy pool + statement_timeout + pool_recycle on shared apcng-db (S)

### Critical — Sprint 2 (integrity depth)
- [ ] [CRITICAL] F-101 Full aggregation-grain redesign: single-source-of-truth grain + derived views (L)
- [ ] [CRITICAL] F-501 (+F-502) Result-status model (Certified/Provisional/Live) + "% reporting" + real "as of" timestamp across public views (L)
- [ ] [CRITICAL] F-403/F-405 Per-election transactions/savepoints + out-of-band audit-log session + dead-letter after N failures (L)

### High
- [ ] [HIGH] F-902 Revert SCRAPER_BURST_FACTOR to 1.0 in committed spec — INEC IP-ban risk (S)
- [ ] [HIGH] F-305 Add indexes ix_results_election_lga_party + ix_results_party CONCURRENTLY (S)
- [ ] [HIGH] F-106 Default geography relationships to lazy="raise"; opt into selectinload() explicitly (S)
- [ ] [HIGH] F-602 Add auth-login tests (200+role, 401 bad pw, 401 inactive, 400 missing) (S)
- [ ] [HIGH] F-603 Add result-integrity validator tests (ResultRow: negative votes, cycle range, grain consistency) (M)
- [ ] [HIGH] F-607 Extract certified-total assertions into a pre-merge integration test (M)
- [ ] [HIGH] F-606 Enable branch protection / required checks on main once green (S)
- [ ] [HIGH] F-406/F-105/F-304/F-309 Fix MV contract: refresh in daemon on cadence + after admin writes; point turnout/competitiveness at MVs; debounce (M)
- [ ] [HIGH] F-104 Claim-based scraper work distribution (FOR UPDATE SKIP LOCKED / per-state lease) for horizontal scale (L)
- [ ] [HIGH] F-303 Kill N+1 fan-out in enp/competitiveness/winners; serve margins from MVs (M)
- [ ] [HIGH] F-202/F-705 SSRF allow-list + private-IP block + redirect/size caps + generic errors on /api/admin/ocr; move /api/admin off public route (M)
- [ ] [HIGH] F-702/F-206 Verify password rotation durably deployed; strong-password policy; MFA/IP-allowlist on /admin (M)
- [ ] [HIGH] F-503 Keyboard/screen-reader map equivalents (national + StateDrillMap) (L)
- [ ] [HIGH] F-504 aria-live/role=status/role=alert regions on the live surface (M)
- [ ] [HIGH] F-505 Wire the existing skeleton components on all async views (M)
- [ ] [HIGH] F-506 Non-color party encoding + colorblind-safe palette (PDP-red vs LP-green) (M)
- [ ] [HIGH] F-507 Raise --text-dim + ad-hoc white-opacity text to WCAG AA contrast (M)
- [ ] [HIGH] F-801/F-802/F-805/F-107 Delete stale CONTEXT.md, dead root monolith, committed 26MB .db, fix Procfile (S)

## Done

- [x] Clone repo to `/Users/godwinagbane/Desktop/Election results/`
- [x] Branch `refactor/pan-nigeria` created off `main`
- [x] `.claude/state/` initialized
- [x] Multi-persona code audit 2026-07-19 (9 personas + synthesis) — see `.claude/state/audits/2026-07-19/`
