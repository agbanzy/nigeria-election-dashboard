# Audit — Reliability (SRE lens) — Nigeria Election Dashboard — 2026-07-19

## Executive summary

The system is built to *survive* individual scraper hiccups (per-phase try/except, IReV retries,
token bucket, `pool_pre_ping`) but it is **blind to the failures that actually matter** and has two
undiscovered single points of failure that take the whole public product down.

Three things stand out for an election-integrity project whose paramount property is "no stale or
corrupted results served as live":

1. **The API wedges under trivial load.** The live SSE endpoint is a blocking `while True` generator
   running on **2 synchronous Gunicorn workers with no async worker class**. Two people on the /live
   page (or one person plus reconnect churn) occupy both workers and the entire `/api/*` surface stops
   responding. This is a civic dashboard whose busiest moment is election night.
2. **The healthcheck lies.** `/api/health` returns `200 ok` as long as `SELECT 1` works. The scraper
   worker has **no healthcheck at all** (DO workers get none), and staleness is never evaluated. A dead
   or wedged scraper during a live election keeps serving hours-old data as "live" with **zero detection
   and zero alerting**.
3. **A single bad IReV response can wedge the scraper permanently, silently.** A flush error inside a
   PU walk is caught but the session is left in a rollback-required state, cascading the rest of the tick
   to fail and rolling back the whole tick. The offending live election is re-selected first on every
   subsequent tick → an infinite zero-progress loop while the process looks perfectly healthy.

None of these page anyone. The scraper's own error trail (`ScrapeLog`) is written inside the same
transaction that rolls back, so the catastrophic failures erase their own evidence.

## Severity table

| ID | Severity | Title | Surface |
|----|----------|-------|---------|
| F-401 | Critical | Blocking SSE on 2 sync Gunicorn workers → whole-API DoS with 2 viewers | infra/backend |
| F-402 | Critical | Healthcheck lies: 200 OK while scraper is dead/stale; no worker check, no staleness gate | backend/infra |
| F-403 | Critical | Poison-pill tick: caught flush error poisons the session → infinite zero-progress loop, no alert | backend |
| F-404 | High | `ElectionResult` has no unique key; PU vote dedup is a count-guard only → silent partial data / double-count | backend |
| F-405 | High | Whole tick is one transaction; error `ScrapeLog` rows erased by the rollback that records them | backend |
| F-406 | High | Analysis materialized views never refreshed by the scraper; refresh failures swallowed → stale-as-live | backend |
| F-407 | Medium | Every POST_DEPLOY job re-runs and marks deploy failed on error; `discover-headers` couples deploys to INEC uptime | infra |
| F-408 | Medium | Single-instance web + frontend (`instance_count: 1`) → any restart = full public outage | infra |
| F-409 | Medium | DB engine: no `pool_recycle`, no `statement_timeout`, no pool sizing on the shared `apcng-db` cluster | backend |
| F-410 | Medium | Nested `session_scope` inside `IrevClient._maybe_cache` → 2 connection checkouts per API call | backend |
| F-411 | Medium | `--timeout 120` reaps the long-lived SSE worker every 120s, killing co-scheduled in-flight requests | infra |
| F-412 | Low | SSE sets no `Cache-Control`/`X-Accel-Buffering`; heartbeat-only stream can't detect half-open TCP server-side | backend |
| F-413 | Low | No structured logging / request IDs / error surfacing (Sentry) / RED metrics; daemon swallows every iteration error | backend |
| F-414 | Low | `scrape_log` is unbounded (no retention) and never read by any health/alert path | backend |
| F-415 | Low | IReV worst-case call latency ≈ 8–9 min (5×90s + backoff); no per-tick deadline can starve a live budget | backend |

---

## Findings

### F-401: Blocking SSE on 2 synchronous Gunicorn workers → whole-API DoS with 2 concurrent viewers
- **Severity**: Critical
- **Persona**: Reliability
- **Surface**: infra
- **Files**: `backend/app/api/live.py:22-30`, `.do/app.yaml:12`, `frontend/src/hooks/useSSE.ts:26`, `backend/requirements.txt` (no gevent/eventlet/gthread)
- **Problem**: The live stream handler is an infinite blocking generator (`while True: time.sleep(15)`). The web service runs `gunicorn -w 2` with **no `--worker-class`**, i.e. default *synchronous* workers, and `requirements.txt` pulls no async worker (no gevent/eventlet). Each held SSE connection occupies one worker for the life of the connection. The frontend opens an `EventSource` to `/api/live/events` for every browser tab on the live page. With only 2 sync workers, **two concurrent live-page visitors occupy both workers** and every other `/api/*` request (overview, results, analysis, health) blocks until a worker frees. On election night this is guaranteed.
- **Impact**: Full public API + healthcheck outage under trivial, expected load. The healthcheck itself (`/api/health`) can't be served, so DO may then mark the web service unhealthy and restart it, dropping the remaining connections. This is the single most likely total-outage path and it fires exactly when traffic is highest.
- **Repro / Evidence**: `live.py:24` `def gen(): ... while True: time.sleep(15); yield ...`; `.do/app.yaml:12` `run_command: gunicorn -w 2 -b 0.0.0.0:8080 app.wsgi:app --timeout 120`. Open 2 tabs on /live → 3rd API call hangs.
- **Recommended fix**: Serve SSE on an async worker class (`--worker-class gevent` + `gevent` dep, or move SSE to an ASGI/`hypercorn` sidecar), or drop SSE entirely and let the frontend poll `/api/sync/status` (it already fetches on an interval elsewhere). At minimum raise `-w`/`--threads` and cap concurrent SSE connections. Do not run blocking long-lived generators on sync workers.
- **Effort**: M
- **Tags**: spof, sse, quick-win, live-election

### F-402: Healthcheck lies — returns 200 OK while the scraper is dead or serving stale data; no worker healthcheck, no staleness gate
- **Severity**: Critical
- **Persona**: Reliability
- **Surface**: backend / infra
- **Files**: `backend/app/api/health.py:16-51`, `.do/app.yaml:16-17` (web `health_check` only), `.do/app.yaml:76-108` (worker has no health check)
- **Problem**: `/api/health` returns `status: ok / 200` whenever `SELECT 1` succeeds. It reads `scraper_last_run` (latest `ScrapeLog.created_at`) but **never compares it to a threshold** — it's returned as decoration, not evaluated. The DO `health_check` is configured only on the **web** service; the **scraper worker** has no HTTP health check (DO App Platform workers don't get one). So the failure that matters most for this project — the scraper stops (crash-looped by top-level except, wedged on a poison pill per F-403, or IReV outage) during a live election while the dashboard keeps serving hours-old data as "live" — produces a **green healthcheck and no alert**.
- **Impact**: Silent stale-as-live on a civic election dashboard: the exact highest-impact failure named in the brief, with no automatic detection. Human intervention only begins when a user notices numbers are frozen. On election night that is a credibility incident.
- **Repro / Evidence**: `health.py:41-51` returns 200 with `scraper_last_run` regardless of its age; there is no `if now - last > threshold: return 503`. Kill the worker → `/api/health` stays 200.
- **Recommended fix**: Make health *semantic*: 503 (or a distinct `degraded` field the alerting watches) when `now - scraper_last_run` exceeds a mode-aware threshold (e.g. 5 min in live/preflight, 24h idle). Add an external uptime/staleness probe against `/api/sync/status` (`queue.pending_total`, `cache.last_fetched_at`) and wire an alert (even a free Uptime-Kuma / cron-curl to a webhook). Emit a scraper liveness heartbeat row and alert on its absence.
- **Effort**: M
- **Tags**: observability, healthcheck, alerting, stale-as-live, live-election

### F-403: Poison-pill tick — a caught flush error leaves the session unusable, cascading the whole tick to roll back and re-select the same election forever
- **Severity**: Critical
- **Persona**: Reliability
- **Surface**: backend
- **Files**: `backend/app/scraper/sync.py:390-412`, `backend/app/scraper/sync.py:456-472`, `backend/app/db.py:72-82`, `backend/app/scraper/daemon.py:108-127`, `backend/app/scraper/sync.py:274-291`
- **Problem**: `sync_election_pus` wraps both the IReV call *and* `_persist_ward_pu_results` (which does `session.add(...)` + `session.flush()` at `sync.py:472`) in a `try/except ... continue`. If the flush raises (e.g. `resolve_party(autocreate=True)` violating `uq_party_code_from` at `models.py:133`, or any constraint/serialization error on the shared cluster), the exception is caught but **the SQLAlchemy session is left in a rollback-required state**. The loop then continues to the next ward and calls `session.scalar(...)` (the `already` count at `sync.py:380`), which raises `PendingRollbackError`. That propagates out of `tick()`, the daemon's top-level `except` logs it (`daemon.py:68`), and the outer `session_scope` rolls back the **entire tick**. Because `select_next_targets` orders by `sync_priority ASC, results_synced_at ASC NULLS FIRST` (`sync.py:282-289`) and the rollback undid the `results_synced_at` update, the **same poison election is re-selected first on every subsequent tick** → an infinite zero-progress loop.
- **Impact**: Unrecoverable scraper wedge with no alert (compounds F-402). During a live election the priority-1 row is exactly the one that gets stuck, so the live dashboard silently freezes while the process stays "up" and logs happily. This is the archetypal 3 AM page that never pages.
- **Repro / Evidence**: `sync.py:402` `except Exception as exc: ... log_phase(...); processed += 1` — no `session.rollback()` and it keeps using the poisoned session; next iteration's `session.scalar` at `sync.py:380` raises `PendingRollbackError`.
- **Recommended fix**: Give each election (and ideally each ward) its own transaction/savepoint so a poison row is isolated — commit per election in the daemon loop instead of one `session_scope` around the whole `tick`, or wrap per-ward work in `with session.begin_nested()`. On a caught persistence error, `session.rollback()` before continuing, and record a durable failure counter that skips or quarantines an election after N consecutive failures (dead-letter) so one bad row can't starve the queue.
- **Effort**: L
- **Tags**: poison-pill, transactions, scraper-wedge, live-election

### F-404: `ElectionResult` has no unique constraint; PU vote de-duplication is a count-guard only → silent partial data or double-counted votes
- **Severity**: High
- **Persona**: Reliability
- **Surface**: backend
- **Files**: `backend/app/models.py` (`ElectionResult.__table_args__` — three non-unique `Index`es, no `UniqueConstraint`), `backend/app/scraper/sync.py:380-389`, `backend/app/scraper/sync.py:456-472`
- **Problem**: `_persist_ward_pu_results` inserts vote rows with a bare `session.add(ElectionResult(...))` — no `ON CONFLICT`, no upsert. The **only** thing preventing duplicate vote rows is the count-based guard in `sync_election_pus` (`if already > 0: continue`, `sync.py:388`). There is no DB-level uniqueness on `(election_id, pu_id, party_id, aggregation)` to back it up. Two failure modes follow: (a) if a ward is **partially** persisted — some PUs flushed, then an error — `already` becomes `> 0`, so the ward is **permanently skipped** on every retry, leaving silent partial results that never complete; (b) if the guard ever misfires (query counts a different aggregation, re-run after a manual delete, future concurrency), votes are **inserted twice with no backstop**, inflating totals.
- **Impact**: Direct integrity risk on the project's paramount property. Partial-ward skips understate turnout silently; double-counts overstate a party's votes. Neither is caught by any constraint or reconciliation.
- **Repro / Evidence**: `models.py` `__table_args__ = (Index("ix_results_election_party", ...), Index("ix_results_state", ...), Index("ix_results_aggregation", ...))` — all non-unique. `sync.py:459-470` inserts without conflict handling.
- **Recommended fix**: Add a partial `UniqueConstraint`/unique index on `(election_id, pu_id, party_id)` where `aggregation='pu'` (mirroring the candidate loader's migration-0004 pattern) and switch the insert to `insert(...).on_conflict_do_update`. Make the guard advisory, not load-bearing. Add a per-ward completeness marker (expected vs inserted PUs) so partial wards are re-tried rather than assumed done.
- **Effort**: M
- **Tags**: idempotency, data-integrity, migration-required

### F-405: Whole tick is a single transaction; the error `ScrapeLog` rows are erased by the same rollback that records them
- **Severity**: High
- **Persona**: Reliability
- **Surface**: backend
- **Files**: `backend/app/scraper/daemon.py:108-127`, `backend/app/db.py:72-82`, `backend/app/scraper/phases.py:148-167`, `backend/app/scraper/sync.py:203-215,402-411`
- **Problem**: The daemon calls `sync.tick(session, ...)` inside one `session_scope`, which commits once at the end (`db.py:77`). `log_phase` writes `ScrapeLog` rows on that **same** session (`phases.py:158`). So when a tick fails with an unhandled error (F-403) the outer `session_scope` rolls back — deleting not just the tick's data progress but also **every error `ScrapeLog` row written during that tick**. The one durable audit trail you have is wiped precisely in the catastrophic case, and there's no incremental commit, so a crash/OOM/SIGKILL mid-tick loses all of that tick's work.
- **Impact**: You are blind to exactly the failures that matter (compounds F-402/F-403): the DB shows no error rows, `scraper_last_run` may even look recent from an earlier successful tick, and operators have nothing to diagnose from. Silent loss of both progress and evidence.
- **Repro / Evidence**: `phases.py:158` `session.add(ScrapeLog(...))` on the shared session; `db.py:78-80` `except: session.rollback(); raise`. Any exception out of `tick` rolls back the `ScrapeLog` inserts made earlier in the same tick.
- **Recommended fix**: Write `ScrapeLog`/audit rows on a **separate short-lived session** that commits immediately (so failure records survive a data rollback), or use an autonomous-transaction pattern. Commit per election so partial progress and its logs persist. Consider logging errors to stdout *and* a durable store that is not on the transactional path.
- **Effort**: M
- **Tags**: observability, transactions, audit-trail

### F-406: Analysis materialized views are never refreshed by the scraper; refresh failures are swallowed with a misleading log → stale-as-live analytics
- **Severity**: High
- **Persona**: Reliability
- **Surface**: backend
- **Files**: `backend/app/analysis/refresh.py:42-57`, `backend/app/importer/loaders/generic_csv.py:157-163`, `backend/app/scraper/daemon.py` (no `refresh_materialized_views` call anywhere in the scraper/sync path)
- **Problem**: The ENP/swing/competitiveness/turnout materialized views (`refresh.py:22-27`) are refreshed **only** by the CSV importer after a manual load (`generic_csv.py:161`). The docstring claims "and by the daemon nightly," but there is **no refresh call in `daemon.py` or `sync.py`** — the daemon never refreshes. So PU/vote data streamed in during live scraping never propagates to the analysis surface until someone manually loads a CSV. Worse, when a refresh does run and fails, `_refresh_one` swallows it and returns `"skipped: <reason>"`, and the importer logs the misleading `"MV refresh skipped (likely Phase A/B, no MVs yet)"` (`generic_csv.py:163`) — masking a *real* lock/error as an expected no-op.
- **Impact**: Analytics endpoints serve stale (or empty) stats while raw results advance — stale-as-live on the stats surface. A genuine refresh failure (lock contention on the shared cluster, missing unique index) is indistinguishable from "not set up yet," so it's never investigated.
- **Repro / Evidence**: `grep refresh_materialized_views backend/app/scraper` → no hits; `refresh.py:52-56` returns `"skipped: {exc}"` on any exception; `generic_csv.py:162-163` logs the swallow as a Phase A/B no-op.
- **Recommended fix**: Refresh the MVs on a cadence in the daemon (nightly + after any live tick that inserted rows), and distinguish "MV does not exist" from "refresh failed" — surface the latter as an error the healthcheck/alerting can see. Don't log real failures with a reassuring message.
- **Effort**: M
- **Tags**: stale-as-live, silent-failure, materialized-views

### F-407: Every POST_DEPLOY job re-runs on each deploy and marks the deployment failed on error; `discover-headers` couples deploy success to INEC's uptime
- **Severity**: Medium
- **Persona**: Reliability
- **Surface**: infra
- **Files**: `.do/app.yaml:121-191`
- **Problem**: `seed`, `seed-historical`, `discover-headers`, and `seed-users` are all `POST_DEPLOY` jobs that re-run on every push-to-main deploy. `discover-headers` (`app.yaml:147-161`) makes live IReV calls during the deploy. A `POST_DEPLOY` job that exits non-zero marks the whole deployment as failed on DO — even though POST_DEPLOY runs *after* the new version is already serving traffic, so the app stays up but the deployment is flagged Error. If INEC's IReV is down or slow during a deploy, `discover-headers` fails and the deploy is marked failed; the seed jobs are idempotent but still add deploy latency and failure surface on every push.
- **Impact**: Deploy reliability is coupled to a third party you don't control (INEC), producing spurious failed-deploy signals and, depending on rollback config, risking confusion or automatic rollback of an otherwise-healthy release. (Note: `migrate` as `PRE_DEPLOY` is correct — a failed migration blocks the new version while the old one keeps serving.)
- **Repro / Evidence**: `app.yaml:146-161` `discover-headers` kind `POST_DEPLOY`, `run_command: python -m app.scraper.backfill` (hits IReV). Any IReV 5xx/timeout during deploy → job fails → deployment Error.
- **Recommended fix**: Move IReV-dependent discovery off the deploy path — let the always-running scraper daemon own header discovery (it already runs it every 24h, `daemon.py:80`). Make seed jobs tolerant/exit-0 on "already seeded." Keep only fast, deterministic, IReV-free jobs (migrate, seed) tied to deploys.
- **Effort**: S
- **Tags**: deploy, third-party-coupling, quick-win

### F-408: Single-instance web and frontend → any restart, crash, or deploy is a full public outage
- **Severity**: Medium
- **Persona**: Reliability
- **Surface**: infra
- **Files**: `.do/app.yaml:14` (web `instance_count: 1`), `.do/app.yaml:49-50` (frontend `instance_count: 1`)
- **Problem**: Web and frontend both run `instance_count: 1` on `basic-xxs`. There is no redundant instance to absorb a crash, an OOM, a deploy restart, or the F-401 worker-exhaustion restart. DO App Platform single-instance deploys generally incur a brief serving gap on redeploy/restart. During a live election, a single web crash or a routine push-to-main (`deploy_on_push: true`) takes the entire public dashboard offline until the instance is back. (The scraper worker being single-instance is *correct* — running two scrapers would double-write given F-404's missing unique constraint — so this finding is scoped to web/frontend.)
- **Impact**: No availability headroom on the two public-facing tiers; every deploy and every crash is user-visible downtime, worst-case during peak election-night traffic.
- **Repro / Evidence**: `app.yaml:14,50` `instance_count: 1`; `deploy_on_push: true` (`app.yaml:9,45`) means routine merges restart the single instance.
- **Recommended fix**: Set `instance_count: 2` for web and frontend so restarts/deploys are rolling with retained capacity; keep the scraper at 1 (or add a leader-lock before ever scaling it). Cost delta is one extra `basic-xxs` per tier — cheap insurance for election-day availability.
- **Effort**: S
- **Tags**: spof, availability, quick-win, live-election

### F-409: DB engine has no `pool_recycle`, no `statement_timeout`, and no pool sizing on the shared `apcng-db` cluster
- **Severity**: Medium
- **Persona**: Reliability
- **Surface**: backend
- **Files**: `backend/app/db.py:36-57`
- **Problem**: `create_engine(url, echo=echo, pool_pre_ping=True, future=True)` sets `pool_pre_ping` (good — catches dropped connections on the shared cluster) but leaves everything else default: no `pool_recycle` (idle connections reaped server-side by DO/pgbouncer are only caught reactively by pre-ping, adding latency), no `pool_size`/`max_overflow` tuning, and — critically — **no `statement_timeout`** via `connect_args`. A runaway query (the `/api/sync/coverage` endpoint fires ~15 aggregate + `distinct`-join queries over `election_results`, `overview` counts everything) can hold a connection indefinitely with no server-side cap, and on the **shared** `apcng-db` cluster that contends with apcng's own workload.
- **Impact**: Latency cliffs and connection starvation under load; a single slow analytical query can pin a connection with no automatic kill, degrading both this app and the co-tenant apcng service on the same cluster.
- **Repro / Evidence**: `db.py:39` — only `pool_pre_ping=True`; no `connect_args={"options": "-c statement_timeout=..."}`, no `pool_recycle`.
- **Recommended fix**: Add `pool_recycle=300`, an explicit `pool_size`/`max_overflow` sized to the DO connection cap shared with apcng, and a `statement_timeout` (and `idle_in_transaction_session_timeout`) via `connect_args` so no query can pin a shared-cluster connection forever.
- **Effort**: S
- **Tags**: database, timeouts, shared-cluster, quick-win

### F-410: Nested `session_scope` inside `IrevClient._maybe_cache` → two connection checkouts per API call
- **Severity**: Medium
- **Persona**: Reliability
- **Surface**: backend
- **Files**: `backend/app/scraper/irev_client.py:113-157`, `backend/app/scraper/daemon.py:108-127`
- **Problem**: Each successful IReV `get()` calls `_maybe_cache`, which opens **its own** `session_scope` (`irev_client.py:141`) to upsert into `irev_raw_cache`. During a tick the daemon already holds an open session for the whole tick (`daemon.py:110-112`), so every API call transiently checks out a **second** connection from the same pool for caching. Under the live burst budget (up to `30 × burst` calls/tick) this doubles connection pressure on the default-sized pool, on the shared cluster.
- **Impact**: Connection amplification / pool-exhaustion risk on a small shared Postgres; the cache write (an optimization) competes for connections with the primary transaction it's nested inside. If the pool is exhausted, `_maybe_cache` blocks on `pool_timeout` (30s default) per call, silently slowing the tick (the write is wrapped in `try/except: pass` at `irev_client.py:117`, so failures are invisible).
- **Repro / Evidence**: `irev_client.py:141` `with session_scope() as session:` opened while the caller's tick session is live; the whole thing is swallowed by `except Exception: pass` at `irev_client.py:117-118`.
- **Recommended fix**: Pass the caller's session into the cache write (or make caching an explicit, batched step outside the per-call hot path). Bound the pool explicitly (F-409). Keep the swallow but at least count/log cache-write failures so silent pool starvation is visible.
- **Effort**: S
- **Tags**: database, connection-pool, silent-failure

### F-411: `--timeout 120` reaps the long-lived SSE worker every 120s, killing co-scheduled in-flight requests
- **Severity**: Medium
- **Persona**: Reliability
- **Surface**: infra
- **Files**: `.do/app.yaml:12`, `backend/app/api/live.py:22-30`
- **Problem**: Gunicorn's `--timeout 120` kills any worker that hasn't returned to the arbiter within 120s. A sync worker serving the blocking SSE generator (F-401) is busy the whole time, so it is **force-killed every ~120s** and restarted. On a sync worker, killing it also drops whatever the arbiter had — and combined with only 2 workers, the churn means SSE connections die on a 2-minute cycle (the client then reconnect-storms via `useSSE.ts` backoff) and any request unlucky enough to share that worker dies with it.
- **Impact**: Periodic dropped connections and request failures tied to the SSE cycle; constant worker restart churn; amplifies F-401.
- **Repro / Evidence**: `app.yaml:12` `--timeout 120` with no async worker; `live.py:26-28` blocks in-worker for the connection's life. `useSSE.ts:47-59` reconnects with backoff after each kill.
- **Recommended fix**: Resolved largely by fixing F-401 (async worker or drop SSE). If SSE stays, run it on a worker class where long-lived connections don't count against the sync request timeout, and set a sane SSE idle policy instead of relying on the arbiter's kill.
- **Effort**: S
- **Tags**: sse, gunicorn, depends-on-F-401

### F-412: SSE stream sets no anti-buffering headers and can't detect a half-open connection server-side
- **Severity**: Low
- **Persona**: Reliability
- **Surface**: backend
- **Files**: `backend/app/api/live.py:22-30`
- **Problem**: The `Response(gen(), mimetype="text/event-stream")` sets no `Cache-Control: no-cache`, no `X-Accel-Buffering: no`, no `Connection: keep-alive`. The dedicated Caddy reverse-proxy droplet (or any intermediary) may buffer the stream, delaying or batching heartbeats. Server-side, a heartbeat-only generator with no write-error handling can't tell a half-open TCP connection is dead — the generator keeps `yield`ing into the void until the OS/Gunicorn tears it down, holding the worker (see F-401).
- **Impact**: Buffered/delayed live updates behind the proxy; workers held on already-dead client connections. Low on its own, contributes to F-401's worker pressure.
- **Repro / Evidence**: `live.py:30` returns the `Response` with no streaming headers; no `GeneratorExit`/broken-pipe handling in `gen()`.
- **Recommended fix**: Set `Cache-Control: no-cache`, `X-Accel-Buffering: no`; handle `GeneratorExit`/write failures to release the worker promptly; verify the Caddy site config disables buffering for `text/event-stream`.
- **Effort**: S
- **Tags**: sse, proxy-buffering

### F-413: No structured logging, request IDs, error surfacing, or RED metrics; daemon swallows every iteration error and never crashes
- **Severity**: Low
- **Persona**: Reliability
- **Surface**: backend
- **Files**: `backend/app/scraper/daemon.py:44-48,64-72`, `backend/app/__init__.py:18-21`, (no Sentry/OTel/metrics anywhere in `backend/`)
- **Problem**: Logging is plain text via `logging.basicConfig` (`daemon.py:45`, `__init__.py:18`) with no JSON structure, no `request_id`/`operation`/`duration_ms` fields, no error-monitoring sink (no Sentry/OTel/Datadog), and no RED metrics on routes or external calls. The daemon's main loop wraps each iteration in `except Exception: log.exception(...)` (`daemon.py:66-69`) so it **never crashes** — which is good for uptime but means a wedged daemon (F-403) looks identical to a working one: process up, logs flowing, no signal distinguishing "syncing" from "spinning on a poison pill."
- **Impact**: Operators can't detect or diagnose degradation without SSHing logs; the swallow-and-continue design hides persistent failure behind a healthy-looking process. Ties directly to why F-402/F-403 go unnoticed.
- **Repro / Evidence**: `daemon.py:68` `except Exception: log.exception("scraper loop iteration failed")` then sleep-and-retry forever; no metrics emitted; `grep -ri sentry backend` → none.
- **Recommended fix**: Add JSON structured logging with consistent fields, a lightweight error sink (Sentry free tier), and a progress metric (elections advanced per tick, `queue.pending_total` trend) that alerting can watch — so "up but making no progress" is a detectable, alertable state.
- **Effort**: M
- **Tags**: observability, logging, metrics

### F-414: `scrape_log` is unbounded (no retention) and never read by any health or alert path
- **Severity**: Low
- **Persona**: Reliability
- **Surface**: backend
- **Files**: `backend/app/models.py` (`ScrapeLog`), `backend/app/scraper/phases.py:148-167`, `backend/app/api/health.py:24-27`, `backend/app/api/scrape.py:33-35`
- **Problem**: Every phase writes a `ScrapeLog` row (`phases.py:158`) with no retention/rotation policy — the table grows unbounded on the shared `apcng-db` cluster. Meanwhile the only consumers just read the single latest row for display (`health.py:26`, `scrape.py:33`); nothing evaluates it for staleness or error-rate, and nothing prunes it.
- **Impact**: Slow unbounded storage growth on a shared cluster; the richest durable operational signal you have is collected but never used for detection (see F-402). Low urgency, but it's dead weight that also masks its own value.
- **Repro / Evidence**: `phases.py:158` unconditional insert; no `DELETE`/partition/retention anywhere; `health.py`/`scrape.py` only `ORDER BY created_at DESC LIMIT 1`.
- **Recommended fix**: Add a retention job (drop rows older than N days, or partition by day) and actually use recent `ScrapeLog` error rates in the healthcheck/alerting.
- **Effort**: S
- **Tags**: retention, observability, shared-cluster

### F-415: IReV client worst-case call latency ≈ 8–9 minutes; no per-tick deadline can starve a live budget
- **Severity**: Low
- **Persona**: Reliability
- **Surface**: backend
- **Files**: `backend/app/scraper/irev_client.py:87-108`
- **Problem**: The client sets `Retry(total=4, backoff_factor=5, status_forcelist=[429,500,502,503,504])` and a per-request `timeout=90`. A single persistently-hanging or 5xx-looping endpoint can therefore consume up to ~5 attempts × 90s + backoff (≈5+10+20+40s) ≈ **8–9 minutes for one call**, all inside a live tick that itself runs on a `120s` live interval (`config.py:51`). There is no overall per-tick deadline or per-call circuit breaker, so a few slow endpoints can blow the entire live-tick budget and stall progress on the live election.
- **Impact**: Bounded (won't hang forever — that's the good part) but a degraded-but-up IReV can starve the live tick, delaying live updates well past the 120s cadence. No circuit breaker to shed a repeatedly-failing endpoint.
- **Repro / Evidence**: `irev_client.py:87-93` (`total=4, backoff_factor=5`), `irev_client.py:103` (`timeout=90`); no wall-clock budget in `tick()`.
- **Recommended fix**: Lower `timeout` for live mode, cap total retry wall-time, and add a simple per-endpoint circuit breaker so a flapping IReV route is skipped for the rest of the tick rather than retried into the budget. Enforce a per-tick deadline aligned to the live interval.
- **Effort**: S
- **Tags**: timeouts, circuit-breaker, retries

---

## Reliability verdict

**Most likely 3 AM page (election night):** the live dashboard freezes — either the API stops responding entirely because 2+ viewers exhausted the 2 sync Gunicorn workers on the blocking SSE endpoint (F-401), or the scraper silently wedged on a single bad IReV response and is serving hours-old results as "live" (F-403 + F-402). Both are the worst possible failure for an election-integrity project, and both happen at peak traffic.

**Time until human intervention when it fires:** effectively unbounded on the scraper path — **nothing pages**. The healthcheck stays green (F-402), the daemon never crashes (F-413), and the error trail deletes itself (F-405). Detection depends on a human noticing frozen numbers, so realistic MTTD is tens of minutes to hours. The API-DoS path (F-401) is at least self-evident (the whole site is down) and may trigger DO's web healthcheck to restart — but that just drops connections and recurs. The system is engineered to *stay up looking healthy while doing nothing*, which for this project is more dangerous than crashing loudly.

**Fix order:** F-401 (async worker / drop SSE) and F-402 (semantic health + staleness alert) are the two that convert silent catastrophic failure into something you can see; do them first. F-403 + F-405 (per-election transactions, out-of-band audit log) remove the poison-pill wedge. F-404 (unique constraint) protects the numbers themselves. Everything else is hardening.
