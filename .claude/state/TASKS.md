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

## Done

- [x] Clone repo to `/Users/godwinagbane/Desktop/Election results/`
- [x] Branch `refactor/pan-nigeria` created off `main`
- [x] `.claude/state/` initialized
