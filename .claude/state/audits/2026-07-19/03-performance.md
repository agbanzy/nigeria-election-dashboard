# Audit — Performance — Nigeria Election Dashboard — 2026-07-19

**Persona**: Performance Engineer
**Scope**: latency, DB query patterns, memory, MV refresh, frontend bundle/render, scraper client.
**Method**: static read of `backend/app/api/*`, `models.py`, `migrations/*`, `analysis/*`, `db.py`, `scraper/*`, `ocr/*`, `frontend/src/*`, `.do/app.yaml`. No production access — metrics are estimated from code + schema + measured asset sizes, and every estimate is paired with a target.

---

## Exec summary

The read APIs are correct but architecturally under-provisioned for election-day load, and two problems compound into a single failure mode:

1. **The whole public API runs on 2 synchronous gunicorn workers on one `basic-xxs` (512 MB) instance** (`.do/app.yaml`) — total in-flight concurrency of **2 requests**.
2. **Several hot endpoints aggregate in Python by streaming full ORM rows** instead of a SQL `GROUP BY`, and several fan out N+1 queries per election.

At state/LGA granularity (today's data) this is merely slow. The moment the scraper drains **PU-level rows** (`sync.py:464` writes `aggregation="pu"`; ~176k PUs × ~18 parties ≈ **3M+ rows per presidential election**), `GET /api/elections/<id>/standings` and the `_votes_by_party`/`_stats` helpers try to hydrate millions of ORM objects into a 512 MB process — **OOM / 120 s timeout**. Two such requests saturate all workers and the dashboard goes dark for everyone.

The good news: the fix pattern already exists in this codebase (`_votes_for` at `analysis.py:510`, `standings_by_lga` at `elections.py:152` both do SQL-side `func.sum … GROUP BY`), and 4 materialized views are already built (`0003_materialized_views.py`) — most endpoints just don't read them yet. This is mostly consolidation, not new engineering.

The SSE reconnect-storm risk is **already mitigated** — `SSE_URL` ships empty (`constants.ts:44`), so `useSSE` never opens a socket; SWR polling (15–30 s) is the live-update path.

### Severity table

| ID | Title | Severity | Surface | Effort |
|----|-------|----------|---------|--------|
| F-301 | `standings` + analysis helpers hydrate full ElectionResult rows into Python (OOM at PU scale) | Critical | backend | M |
| F-302 | Entire public API = 2 sync gunicorn workers on 1×basic-xxs; heavy reads polled every 30 s | Critical | infra | M |
| F-303 | N+1 query fan-out across `enp`, `competitiveness`, `winners` (incl. the "fast" MV path) | High | backend | M |
| F-304 | Live-aggregation endpoints ignore the materialized views that already exist | High | backend | M |
| F-305 | Missing indexes on `election_results` hot columns (`lga_id`, `party_id`) | High | backend | S |
| F-306 | Synchronous 30 s image fetch + Tesseract OCR on a request thread | Medium | backend | M |
| F-307 | 344 KB national geojson + up to 512 KB per-state ward geojson shipped unsimplified | Medium | web | M |
| F-308 | recharts v3 statically imported on 3 routes — not code-split | Medium | web | S |
| F-309 | MV `REFRESH` scans all aggregation levels ×4 views sequentially after every load | Medium | backend | M |
| F-310 | API gate does a row `UPDATE` on every authenticated request | Low | backend | S |
| F-311 | `/api/results` allows limit=5000 over a 4-way join, serialized per-row, no cursor | Low | backend | S |
| F-312 | SSE generator `while True: sleep(15)` pins a sync worker per connection if ever enabled | Low | backend | S |
| F-313 | Default pool (5+10) on shared `apcng-db`, no `pool_recycle` — instrument | Low | infra | S |

---

## Findings

### F-301: `standings` and analysis helpers aggregate by streaming full ORM rows into Python
- **Severity**: Critical
- **Persona**: Performance
- **Surface**: backend
- **Files**: `backend/app/api/elections.py:61-68`, `backend/app/api/analysis.py:490-507` (`_votes_by_party`, `_stats`)
- **Problem**: `get_standings` runs `session.scalars(select(ElectionResult).where(election_id == X))` and sums `votes`/`accredited`/`registered` in a Python loop. `_votes_by_party` and `_stats` do the same. This hydrates one full ORM entity **per result row** (every mapped column, including the `raw_json` JSONB) and does the aggregation client-side, when a single `SELECT party_id, SUM(votes) … GROUP BY party_id` returns ≤ ~20 rows.
- **Impact**: Blast radius = every election-detail page + ENP + competitiveness. At state/LGA granularity a presidential election is ~37–800 rows: fine. At **PU granularity** (`sync.py:464` writes `aggregation="pu"`; historical seed supports `pu` too) it is ~176,846 PUs × up to 18 parties ≈ **3.2M rows**. Hydrating 3.2M ORM objects ≈ **2–4 GB of Python heap** on a **512 MB** `basic-xxs` instance → OOM kill, or, before OOM, tens of seconds → the `--timeout 120` guillotine. `raw_json` is null on scraped PU rows (`sync.py:459-468`) but a loader that populates it turns this into a 10 GB+ event.
- **Repro / Evidence**:
  ```python
  # elections.py:61 — full-entity stream, Python-side sum
  for r in session.scalars(select(ElectionResult).where(ElectionResult.election_id == election_id)):
      votes_by_party[r.party_id] += r.votes
  ```
  Contrast the correct pattern already in the same files: `analysis.py:510 _votes_for` → `select(ElectionResult.party_id, func.sum(...)).group_by(...)`, and `elections.py:152 standings_by_lga` → SQL `GROUP BY`.
- **Current metric**: est. 3–4 GB heap / 8–30 s wall for a PU-level presidential election (not measured — recommend `EXPLAIN ANALYZE` + memory profile once PU data lands).
- **Target metric**: single `GROUP BY` returning ≤ 20 rows, < 50 ms, < 5 MB, backed by `ix_results_election_party`.
- **Recommended fix**: Replace the three streams with `SELECT party_id, SUM(votes), SUM(accredited_voters), SUM(registered_voters) … WHERE election_id=:id GROUP BY party_id`. Reuse the `_votes_for` shape. Zero response-shape change.
- **Effort**: M
- **Tags**: n+1, oom, quick-win, hot-path

### F-302: Entire public API is 2 synchronous gunicorn workers on a single basic-xxs instance
- **Severity**: Critical
- **Persona**: Performance
- **Surface**: infra
- **Files**: `.do/app.yaml` (`run_command: gunicorn -w 2 … --timeout 120`, `instance_size_slug: basic-xxs`, `instance_count: 1`), `backend/Procfile:1`
- **Problem**: Sync workers serve exactly **one request each**. Total API concurrency is **2**. There is no horizontal replica and no CDN/edge cache in front of the read endpoints. Meanwhile the landing page polls `/api/analysis/winners` every 30 s (`NigeriaChoropleth.tsx:79-82`) plus `/api/scrape/status` every 30 s, and every viewer's SWR refreshes on a 15 s default (`constants.ts:31`).
- **Impact**: Dashboard-wide. Throughput ≈ `2 / mean_latency`. If `winners`/`competitiveness` average ~300 ms under the N+1 pattern (F-303), sustained capacity ≈ **~6 req/s**. A live governorship with **~500 concurrent tabs** polling winners every 30 s ≈ **16–17 req/s** of winners alone — ~3× over capacity. Excess requests queue behind `--timeout 120`; a single F-301 request pins 50 % of the API for its whole duration. This is the election-day brownout.
- **Repro / Evidence**: `gunicorn -w 2 … --timeout 120` + `instance_count: 1`, no async worker class, no `Cache-Control` on any `/api/analysis/*` response (grep: none set).
- **Current metric**: 2 concurrent requests; est. ~6 req/s sustained heavy-read capacity.
- **Target metric**: For a read-mostly civic surface with spiky traffic: micro-cache read endpoints (`Cache-Control: public, s-maxage=15–30, stale-while-revalidate`) at the Caddy proxy/CDN so N viewers collapse to ~1 origin hit per 15–30 s; and move to `gevent`/`gthread` workers (hundreds of concurrent connections) or ≥ 2 replicas of a larger slug. Target sustained ≥ 200 req/s effective with cache, origin < 10 req/s.
- **Recommended fix**: (1) Add HTTP caching headers on the pollable read endpoints and enable proxy/edge caching — biggest lever, near-zero cost. (2) `--worker-class gthread --threads 4` or gevent for I/O-bound reads. (3) Bump `instance_count` to 2 for election windows. Do (1) first.
- **Effort**: M
- **Tags**: capacity, caching, election-day, cost-aware

### F-303: N+1 query fan-out across enp / competitiveness / winners — including the "fast" MV path
- **Severity**: High
- **Persona**: Performance
- **Surface**: backend
- **Files**: `backend/app/api/analysis.py:78-114` (`enp_by_election`, incl. `_margin_for` at :88/:117), `:170-193` (`competitiveness`), `:260-320` (`winners_per_state`)
- **Problem**: Each endpoint loops elections and issues per-election queries. `enp_by_election`'s MV branch reads `mv_enp` in one shot (good) but then calls `_margin_for(session, r[0])` **per row** (`:88`) → `_votes_by_party` → a full ElectionResult scan **per election**, so the MV optimization is cancelled out. `competitiveness` calls `_votes_by_party` **and** `_stats` per election (2 full scans each). `winners_per_state` runs a `GROUP BY` **plus** a `Candidate` scalar per election.
- **Impact**: `?type=governorship` spans ~37 state elections → `competitiveness` = **~74 full-table aggregations per request**; `winners` = ~74 queries; `enp` (even MV path) = ~37 extra full scans. Compounds directly with F-301 (each scan is the heavy pattern) and F-302 (each request holds a scarce worker longer). Analytics page mounts turnout+enp+competitiveness together (`analytics/page.tsx:58-61`); insights mounts zone+trajectory+biggest-swings (`insights/page.tsx:69-77`) — 3 heavy multi-query endpoints per page load.
- **Repro / Evidence**:
  ```python
  # analysis.py:88 — per-MV-row margin recompute defeats the MV
  "margin": _margin_for(session, r[0]),   # → _votes_by_party → full scan per election
  # analysis.py:178-179 — two full scans per election
  votes = _votes_by_party(session, e.election_id)
  stats = _stats(session, e.election_id)
  ```
- **Current metric**: O(N elections) queries per request; ~37–74 round-trips for a governorship cycle.
- **Target metric**: O(1) — a single grouped query (or MV read) returning all elections' aggregates at once; ≤ 2 queries per endpoint.
- **Recommended fix**: Compute margin/ENP/competitiveness set-based in one `GROUP BY election_id` (the MVs already do exactly this — `mv_competitiveness` even includes margin+turnout+enp). Serve `competitiveness`/`winners` margin from the MV; batch the winners candidate lookup with a single `WHERE election_id IN (…)` keyed dict.
- **Effort**: M
- **Tags**: n+1, hot-path

### F-304: Live-aggregation endpoints ignore the materialized views that already exist
- **Severity**: High
- **Persona**: Performance
- **Surface**: backend
- **Files**: `backend/app/api/analysis.py:25-56` (`turnout_by_state` recomputes), `:166-193` (`competitiveness` recomputes), `:196-247` (`party_totals`), `:250-320` (`winners`), `:323-355` (`zone_summary`), `:358-391` (`party_trajectory`), `:394-463` (`biggest_swings`); MVs defined in `backend/migrations/versions/0003_materialized_views.py`
- **Problem**: Only `enp_by_election` reads an MV. `mv_turnout_by_state_cycle` and `mv_competitiveness` exist and are refreshed after loads (`refresh.py`), yet `turnout_by_state` and `competitiveness` still aggregate `election_results` live on every request. The high-traffic endpoints (`winners`, `party_totals`, `zone_summary`, `party_trajectory`, `biggest_swings`) have **no MV at all** and always full-scan.
- **Impact**: Every analytics/insights/landing request pays full aggregation cost over a table that grows to millions of PU rows, instead of hitting a pre-aggregated view with ≤ few-thousand rows. This is the root cause that makes F-302's worker scarcity bite.
- **Repro / Evidence**: `turnout_by_state` (`:30-44`) issues `SUM(accredited)/SUM(registered) … GROUP BY state` live; identical logic is frozen in `mv_turnout_by_state_cycle` (`0003:31-47`) and goes unused.
- **Current metric**: full base-table scan per request (grows with ingest).
- **Target metric**: MV read bounded by result cardinality (states×cycles×types ≈ low thousands), < 20 ms.
- **Recommended fix**: Point `turnout`/`competitiveness` at their MVs (mirror the enp try-MV-then-fallback pattern at `:64-94`). Add `mv_winner_by_state`, `mv_party_totals`, `mv_zone_summary` (per cycle×type) for the choropleth/insights hot paths, refreshed by the same `refresh_materialized_views()` hook.
- **Effort**: M
- **Tags**: materialized-view, hot-path, election-day

### F-305: Missing indexes on `election_results` hot filter / FK columns
- **Severity**: High
- **Persona**: Performance
- **Surface**: backend
- **Files**: `backend/app/models.py:255-259`, `backend/migrations/versions/0001_initial.py:168-172`
- **Problem**: `election_results` indexes only `(election_id, party_id)`, `(state_id)`, `(aggregation)`. Postgres does **not** auto-index FK columns, so `lga_id` and standalone `party_id` are unindexed. `standings_by_lga` (`elections.py:152-158`) filters `election_id AND lga_id IS NOT NULL GROUP BY lga_id, party_id`, and party-grouped analytics (`party_totals`, `party_trajectory`) group/join on `party_id` across all elections.
- **Impact**: The `(election_id, party_id)` composite covers the election-scoped queries, so `by-lga` is partially covered — but any query filtering by `lga_id` or grouping globally by `party_id` degrades to a sequential scan as the table grows to millions of rows. Sequential scan of a 3M-row table ≈ hundreds of ms–seconds, multiplied by F-302's worker scarcity.
- **Repro / Evidence**: `__table_args__` lists exactly 3 indexes; no `lga_id` index despite the FK at `models.py:236-238` and the `by-lga` GROUP BY.
- **Current metric**: seq scan on `lga_id`/`party_id` predicates; not measured — recommend `EXPLAIN (ANALYZE, BUFFERS)` on `/elections/<id>/by-lga` and `/analysis/party-totals`.
- **Target metric**: index scan; add composite `(election_id, lga_id, party_id)` for by-lga and `(party_id)` (or `(party_id, election_id)`) for global party rollups. Target < 30 ms.
- **Recommended fix**: New migration adding `ix_results_election_lga_party` and `ix_results_party`. Create with `CONCURRENTLY` to avoid locking during election windows.
- **Effort**: S
- **Tags**: index, migration-required, quick-win

### F-306: Synchronous 30 s image fetch + Tesseract OCR on the request thread
- **Severity**: Medium
- **Persona**: Performance
- **Surface**: backend
- **Files**: `backend/app/api/admin.py:204-245`, `backend/app/ocr/ec8a.py:53-94`
- **Problem**: `POST /api/admin/ocr` does `requests.get(url, timeout=30)` (up to 30 s) then `parse_ec8a_image` → `pytesseract.image_to_string` (CPU-bound, ~1–5 s per scan) **inline in the Flask worker**. This shares the same 2-worker pool (F-302) that serves the public dashboard.
- **Impact**: Each admin OCR call ties up **50 % of total API capacity** for the full fetch+OCR duration (5–35 s). OCR happens exactly during live ingestion, precisely when public traffic peaks — admins transcribing forms directly starve viewers.
- **Repro / Evidence**: `admin.py:222` `requests.get(str(url), timeout=30)` then `:227` `parse_ec8a_image(resp.content …)` → `ec8a.py:86` `pytesseract.image_to_string(proc, lang="eng")`, all synchronous.
- **Current metric**: 5–35 s of worker occupancy per OCR call, on a 2-worker pool.
- **Target metric**: OCR off the request path; request returns < 100 ms with a job id, result polled/pushed. Worker never blocks on Tesseract.
- **Recommended fix**: Offload OCR to the existing `scraper` worker (or a small task queue) and return a job handle; or at minimum run OCR on a dedicated thread-pool worker class and cap concurrency so it can't consume both request slots. Bound the image fetch to a few seconds.
- **Effort**: M
- **Tags**: blocking-io, admin, election-day

### F-307: Large unsimplified geojson shipped to the client
- **Severity**: Medium
- **Persona**: Performance
- **Surface**: web
- **Files**: `frontend/public/ng-states.geojson` (344 KB), `frontend/public/maps/kn-wards.geojson` (512 KB), `ke-wards.geojson` (302 KB), and siblings; loaded in `NigeriaLeafletMap.tsx:113-118`, `StateDrillMap.tsx:83-96`
- **Problem**: The national choropleth fetches a **344 KB** full-resolution GADM 4.1 polygon file client-side; state drill pages fetch per-state LGA+ward files up to **512 KB**. These are full-precision geometries rendered as Leaflet vector paths — far more coordinate detail than a 520 px-tall map can show.
- **Impact**: ~344 KB (≈ 90–120 KB gzipped) added to the landing map's time-to-interactive; up to ~640 KB (LGAs+wards) on a state page. On mid-range mobile over 3G/4G this is 1–3 s of extra fetch + parse, plus Leaflet path-tessellation cost for thousands of vertices. Map is `dynamic()`-imported behind a "Loading map…" state so it doesn't block LCP, but it delays interactivity and burns mobile data.
- **Repro / Evidence**: measured `ls -lh`: `ng-states.geojson` 344 KB; `kn-wards.geojson` 512 KB. Fetched raw via `fetch("/ng-states.geojson")`.
- **Current metric**: 344 KB national / up to 512 KB per state ward layer, full precision.
- **Target metric**: simplify with mapshaper (`-simplify 5-10% visvalingam`) to < 60 KB national / < 120 KB per state; serve pre-compressed (`.geojson.br`), long immutable cache. Optionally topojson to shave another ~40 %.
- **Recommended fix**: Add a build step simplifying the geojson to display resolution; verify boundaries still read correctly at zoom 6–11. Static assets already cache well under Next `public/`; add Brotli.
- **Effort**: M
- **Tags**: bundle, mobile, quick-win

### F-308: recharts v3 statically imported on insights / analytics / dashboard routes
- **Severity**: Medium
- **Persona**: Performance
- **Surface**: web
- **Files**: `frontend/src/app/insights/page.tsx:17`, `frontend/src/app/analytics/page.tsx:18`, `frontend/src/app/dashboard/page.tsx:9`; `frontend/package.json:26` (`recharts ^3.7.0`)
- **Problem**: recharts (and its d3-scale/shape/array transitive deps) is `import`-ed statically into three route bundles. recharts 3 is a large charting lib (~250–400 KB min, ~90–130 KB gzipped depending on tree-shaking). The Leaflet maps are correctly `dynamic()`-split (`NigeriaChoropleth.tsx:17`, `states/[stateCode]/page.tsx:17`), but the charts are not.
- **Impact**: Each of those three routes ships recharts in its first-load JS, inflating TTI on the analytics-heavy pages by an estimated 90–130 KB gzip / ~200–400 ms parse-eval on mid mobile.
- **Repro / Evidence**: `insights/page.tsx:17 } from "recharts";` (static). No `next/dynamic` wrapper around chart components; no `optimizePackageImports` for recharts in `next.config.mjs` (config is minimal, `next.config.mjs:1-27`).
- **Current metric**: recharts in 3 route bundles, static.
- **Target metric**: charts behind `next/dynamic(..., { ssr: false })` (they're client-only anyway) and/or `experimental.optimizePackageImports: ['recharts']`; recharts out of the initial route chunk.
- **Recommended fix**: Wrap chart-heavy sections in `dynamic()` like the maps already are; add `optimizePackageImports`. Low effort, isolated.
- **Effort**: S
- **Tags**: bundle, code-split, quick-win

### F-309: Materialized-view REFRESH scans all aggregation levels across 4 views, sequentially, after every load
- **Severity**: Medium
- **Persona**: Performance
- **Surface**: backend
- **Files**: `backend/app/analysis/refresh.py:30-57`, `backend/app/importer/loaders/generic_csv.py:159-163`, `backend/migrations/versions/0003_materialized_views.py`
- **Problem**: `refresh_materialized_views()` refreshes all 4 MVs **sequentially**, and it's called **after each importer load** (`generic_csv.py:161`). `mv_enp` (`0003:53-93`) and `mv_competitiveness` (`0003:138-188`) aggregate over `election_results` including `aggregation IN ('pu',…)` — i.e. they scan the **entire PU-level table** each refresh. `REFRESH … CONCURRENTLY` additionally rebuilds into a second copy (2× disk/CPU) and diff-swaps. `mv_competitiveness` depends on `mv_enp`, so serial order matters and each is a fresh full scan.
- **Impact**: During historical backfill / batched loads, every batch triggers 4 full-table MV rebuilds = a refresh storm; CPU/IO on the shared `apcng-db` cluster spikes and competes with live read traffic. Separately, admin manual/import writes (`admin.py:112-314`) do **not** call refresh → `enp` MV goes stale after manual entry while the live endpoints (which don't use MVs, F-304) diverge from it.
- **Repro / Evidence**: `refresh.py:37-39` loops `EXPECTED_MVS` one at a time; `generic_csv.py:161` calls it per load; MV bodies scan all aggregation levels.
- **Current metric**: 4 sequential full-table MV rebuilds per load; unmeasured wall time (grows with PU volume).
- **Target metric**: debounce/coalesce refreshes (once per batch, not per file), refresh concurrently where safe, and scope MVs to the aggregation levels each actually needs. Trigger refresh after admin writes too.
- **Recommended fix**: Move refresh to a single post-batch call (or a periodic daemon tick), not per-load; parallelize independent MVs; add a refresh call after `/api/admin/results` and `/api/admin/import`.
- **Effort**: M
- **Tags**: materialized-view, refresh-storm, staleness

### F-310: API gate issues a row UPDATE on every authenticated request
- **Severity**: Low
- **Persona**: Performance
- **Surface**: backend
- **Files**: `backend/app/api_gate.py:47-59`
- **Problem**: `_check_key` sets `last_used_at = now()` and `request_count += 1` on **every** valid-key request, inside the `before_request` hook, committed via `session_scope`. Every programmatic GET becomes a read + write transaction and a heap update on `api_clients`.
- **Impact**: Low today (key traffic is small vs. same-origin dashboard traffic, which skips this path at `api_gate.py:72`). But it serializes writes on a single row per key and adds WAL/commit cost to what should be cache-friendly reads; a heavy API consumer hammers one row.
- **Repro / Evidence**: `api_gate.py:56-58` mutates and relies on `session_scope` commit for every keyed request.
- **Current metric**: 1 UPDATE + commit per authenticated API call.
- **Target metric**: batch/async usage accounting — increment in memory and flush every N seconds, or `last_used_at` at coarse (e.g. per-minute) granularity. < 1 write per key per minute.
- **Recommended fix**: Debounce the counter (in-process aggregate flushed periodically) or update `last_used_at` only when stale by > 60 s.
- **Effort**: S
- **Tags**: write-amplification, api-gate

### F-311: `/api/results` permits limit=5000 over a 4-way join, serialized per-row, no cursor pagination
- **Severity**: Low
- **Persona**: Performance
- **Surface**: backend
- **Files**: `backend/app/api/results.py:14-58`
- **Problem**: `list_results` joins `ElectionResult`→`Party`→`State`→`IngestionSource` and returns up to **5000** rows (`:19`), built one dict at a time in Python (`:40-57`). No `OFFSET`/keyset pagination; `aggregation` filter is optional, so an unfiltered PU query can select 5000 of millions of rows.
- **Impact**: A 4-join × 5000-row response is ~1–3 MB JSON and meaningful serialize time on a 2-worker pool; an unindexed-filter variant (F-305) makes the underlying scan worse. Not catastrophic (capped at 5000) but a cheap way for a keyed client to tie up a worker.
- **Repro / Evidence**: `results.py:19` `min(limit, 5000)`; `:40` per-row Python dict build; no cursor.
- **Current metric**: up to 5000 joined rows / request, ~1–3 MB.
- **Target metric**: keyset pagination (`result_id > :cursor`), default 200 / hard cap ~1000, require `election` or `state` filter for PU-granularity pulls.
- **Recommended fix**: Add cursor pagination + a mandatory scope filter when `aggregation='pu'`.
- **Effort**: S
- **Tags**: pagination, api

### F-312: SSE generator pins a sync worker per connection if re-enabled
- **Severity**: Low
- **Persona**: Performance
- **Surface**: backend
- **Files**: `backend/app/api/live.py:22-30`, `frontend/src/lib/constants.ts:44-45`, `frontend/src/hooks/useSSE.ts`
- **Problem**: `/api/live/events` is an infinite `while True: time.sleep(15)` generator. Under sync gunicorn each open EventSource holds a worker **for the life of the connection**. It is currently dormant — `SSE_URL` is the empty string (`constants.ts:44`), so `useSSE` returns early (`useSSE.ts:18`) and never connects.
- **Impact**: Latent. If anyone sets `NEXT_PUBLIC_SSE_URL="/api/live/events"` without first moving to async workers, the **2nd** viewer permanently consumes worker #1, the **3rd** consumes worker #2, and the API is dead for everyone else. The disabling comment (`constants.ts:37-43`) documents this, which is good — but it's one env var away from an outage.
- **Repro / Evidence**: `live.py:26-28` unbounded loop; `constants.ts:44` `SSE_URL = … || ""`.
- **Current metric**: 0 (disabled). If enabled on sync workers: capacity = 2 concurrent viewers, total.
- **Target metric**: SSE only under gevent/async workers with per-connection limits, or push live updates via the CDN-cached polling that already works.
- **Recommended fix**: Keep disabled until F-302's async worker class lands; gate re-enable on that. Consider a hard connection cap on the endpoint.
- **Effort**: S
- **Tags**: sse, latent, election-day

### F-313: Default connection pool on a shared cluster, no pool_recycle
- **Severity**: Low
- **Persona**: Performance
- **Surface**: infra
- **Files**: `backend/app/db.py:36-57`
- **Problem**: `create_engine(url, pool_pre_ping=True, future=True)` uses SQLAlchemy defaults (`pool_size=5`, `max_overflow=10` → up to 15 conns/process) with no `pool_recycle`/`pool_timeout`. The DB is the **shared** `apcng-db` managed Postgres cluster (`.do/app.yaml`), so this app competes for a shared `max_connections` (small managed tiers cap ~22–25) against every other app on the cluster.
- **Impact**: With only 2 sync workers (F-302) this app can't actually open 30 conns concurrently, so it's not today's bottleneck — but the pool is oversized relative to worker count and undersized-safe relative to the shared cap. No `pool_recycle` risks stale connections through managed-DB idle timeouts (mitigated by `pool_pre_ping`). Worth instrumenting before scaling workers, since raising worker/replica count (the F-302 fix) multiplies pool demand against the shared cap.
- **Repro / Evidence**: `db.py:39` no pool sizing args; `SCHEMA_NAME` search-path listener is per-connect but cheap.
- **Current metric**: up to 15 conns/process (5+10); effective use ≤ 2 (worker-bound). Not measured against cluster `max_connections`.
- **Target metric**: pool sized to `threads_per_worker × workers` with headroom under the shared cap; add `pool_recycle=1800`. When scaling workers, front the DB with a pooler (PgBouncer / DO connection pool) rather than raising per-process pools.
- **Recommended fix**: Set explicit `pool_size`/`max_overflow`/`pool_recycle`; measure `apcng-db` connection headroom before the F-302 scale-up; adopt a pooler for the scaled topology.
- **Effort**: S
- **Tags**: pool, shared-cluster, instrument-first

---

## Performance verdict

**At current trajectory the user-visible breaking point is a single live governorship or presidential day with a few hundred concurrent viewers.** Two forces collide: a **2-request-wide** API (F-302) and **Python-side aggregation that scales with ingested row count** (F-301, F-303, F-304). While data stays at state/LGA granularity the site is merely sluggish. The instant the scraper drains **PU-level rows** (it is coded to — `sync.py:464`), `GET /api/elections/<id>/standings` tries to hydrate ~3M ORM objects into a 512 MB process and **OOMs or hits the 120 s timeout**; two such requests saturate both workers and the dashboard browns out for everyone — exactly when civic trust needs it up.

**The reassuring part**: none of this needs new infrastructure. The SQL `GROUP BY` pattern (F-301/F-303) and the four materialized views (F-304) already exist in-repo and just need to be used consistently; HTTP micro-caching on the pollable read endpoints (F-302) collapses N viewers to ~1 origin hit per interval for near-zero cost; the two missing indexes (F-305) are a one-migration fix. Do **F-302 caching + F-301 GROUP BY + F-305 indexes** before the next live election — that trio alone moves the breaking point from "hundreds of viewers" to "comfortably into the thousands." Instrument (`pg_stat_statements`, memory profile, `EXPLAIN ANALYZE`) to replace these estimates with measured numbers, then decide on worker class and replicas.
