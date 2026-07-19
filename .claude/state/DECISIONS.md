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

## 2026-07-19 — Audit synthesis: adopt 4-sprint remediation roadmap

**Context**: Multi-persona code audit (9 personas + Chief Auditor) run by the `audit-2026-07-19` thread. Full report set at `.claude/state/audits/2026-07-19/`; synthesis at `audits/2026-07-19/10-synthesis.md`. 108 findings: 18 Critical, 28 High, 36 Medium, 26 Low.

**Decision**: Adopt the 4-sprint roadmap with the top-10 findings prioritised by Severity × Likelihood × Ease-to-fix. Sprint 1 = stop-the-bleeding before the next live election (vote-table integrity backstop, fail-closed admin, rate limiting, read-caching + capacity, restored CI). Verified ground truth overrides individual persona ratings where noted.

**Top conclusions**:
- The bones are good (clean app-factory, disciplined migrations, well-tested analytics math) but published vote totals are not yet trustworthy — result integrity has **no automated backstop at any layer** (schema, aggregation grain, ingestion auth, MV refresh, UI provenance). This is the crown-jewel cluster (F-101, F-102/F-404, F-402/F-406, F-501, F-201/F-701, F-301).
- **Production is up and not actively breached.** The live `web` service currently sets `ADMIN_TOKEN`, so fail-open admin (F-201/F-701) is mitigated *today* — but it is a **latent Critical**: fail-open by default, and the committed `.do/app.yaml` omits the token, so one spec-based redeploy re-opens unauthenticated result falsification. Fix = fail closed + assert at startup + commit the SECRET on the web service.
- Other latent Criticals: election-day capacity wall (2 sync workers / 1×basic-xxs / no read cache / no rate limiting — F-302/F-703/F-203), PU-scale OOM on the aggregation read path (F-301), silent scraper wedge with a lying healthcheck (F-403/F-402), and shared `apcng-db` with no compute isolation (F-903).
- **CI is `disabled_manually`, not merely red** — no run since 2026-05-16; every commit since ships unvalidated. Re-enable after `ruff --fix` + adding the Next ESLint config.

**Consequences**:
- Sprint 1 quick wins land immediately: delete dead root monolith + committed 26 MB `.db` + stale `CONTEXT.md`; add the vote unique constraint + two indexes; fail-closed admin; revert `SCRAPER_BURST_FACTOR` to 1.0; cap the DB pool + `statement_timeout`.
- Deferred to strategic investment: full aggregation-grain redesign (F-101), async worker model + scraper sharding (F-103/F-104/F-302), dedicated DB cluster before the next major election (F-903), end-to-end result-status/provenance model (F-501).
- **Accepted (not fixing), with reversal triggers**: (1) the API-gate `Sec-Fetch-Site` "bypass" — F-704 down-rated to Low, it only gates already-free data; revisit only if rate-limiting/quota is layered on the gate. (2) always-on scraper worker (F-907) — $5/mo buys live-tick responsiveness. (3) non-static frontend (F-908) — NextAuth + admin proxy require a Node server. (4) English-only UI (F-517). Git-history hash scrub (F-702) accepted as not-done provided rotation is verified.

**Thread**: audit-2026-07-19
