# Architect audit — Nigeria Election Dashboard — 2026-07-19

## Executive summary

The system is a clean-looking Flask app-factory with well-separated blueprints, a coherent
scraper/importer/analysis split, and sensible Alembic migrations — but the core asset, the
`election_results` vote table, has two design flaws that corrupt the one thing this project
exists to protect: correct vote totals. Results are stored at mixed aggregation grains in one
table and summed across grains at read time, and the table carries no DB-level uniqueness, so
concurrent PU-scrape + admin-entry (exactly the FCT 2026 flagship scenario) and any re-import
silently multiply votes. Separately, the live-day serving path is a hard scaling wall: an SSE
endpoint served by 2 synchronous gunicorn workers wedges the entire API at ~2 concurrent stream
clients, and the single-instance, unshardable scraper daemon cannot keep pace with 37-state live
load. The materialized-view subsystem is half-wired (built and refreshed on one path, read on
another, never refreshed by the daemon its own docstring names), producing inconsistent freshness
across the same dashboard.

## Severity counts

| Severity | Count |
|---|---|
| Critical | 3 |
| High     | 4 |
| Medium   | 4 |
| Low      | 1 |
| **Total**| **12** |

---

### F-101: `election_results` sums across aggregation grains → vote double-counting
- **Severity**: Critical
- **Persona**: Architect
- **Surface**: backend
- **Files**: `backend/app/api/elections.py:60-62`, `backend/app/api/analysis.py:490-496`, `backend/app/api/analysis.py:208-231`, `backend/app/api/analysis.py:275-286`, `backend/app/api/admin.py:178-190`, `backend/app/scraper/sync.py:459-469`
- **Problem**: `election_results` stores rows at every grain (`aggregation` ∈ pu|ward|lga|state|national) in one table. The scraper writes `aggregation='pu'` rows (`sync.py:462`) while the admin manual-entry and bulk-import suites write `aggregation='state'|'lga'` rows for the *same* election (`admin.py:183`, `admin.py:305`). Every analysis read path — `_votes_by_party`, `party_totals`, `winners_per_state`, `zone_summary`, `party_trajectory`, `_votes_for`, `biggest_swings`, and `elections.py` standings — sums `ElectionResult.votes` with **no `aggregation` filter**. The developer's own comment states the flawed invariant: "sum across all ElectionResult rows for this election, regardless of aggregation level — PU, ward, LGA, state, national all roll up the same way" (`elections.py:60-62`). That is only true when exactly one grain exists per election; the moment two coexist, totals become a multiple of the truth.
- **Impact**: Corrupted public vote totals, winner, share, and margin — the paramount failure mode. This is live-today, not latent: FCT 2026 is simultaneously PU-scraped and hand-entered via the admin suite built for it, so the choropleth winner and margins on the homepage can already be arithmetically wrong. Blast radius = every aggregate endpoint and the flagship live election.
- **Repro / Evidence**: `analysis.py:492-495` — `for r in session.scalars(select(ElectionResult).where(ElectionResult.election_id == election_id)): out[r.party_id] += r.votes` with no grain filter. Load one election with both a `pu` row (10 votes summed to 100 at PU) and a `state` row (100), and `_votes_by_party` returns 200.
- **Recommended fix**: Make single-grain-per-election an enforced invariant. Either (a) store only the finest available grain and derive all higher levels via views (single source of truth), or (b) add an explicit `result_grain` per election and have every read filter to that grain by default. Minimum stopgap: filter reads to the canonical grain for the election and add a partial unique index preventing mixed grains for one `election_id`.
- **Effort**: L
- **Tags**: data-integrity, data-model, migration-required, election-integrity

### F-102: No DB-level uniqueness on `election_results` → duplicate rows double-count
- **Severity**: Critical
- **Persona**: Architect
- **Surface**: backend
- **Files**: `backend/app/models.py:255-259`, `backend/migrations/versions/0001_initial.py:131-172`, `backend/app/scraper/sync.py:380-388`, `backend/app/importer/loaders/seed_historical.py:21`
- **Problem**: `ElectionResult.__table_args__` declares only three non-unique indexes; migration 0001 creates no unique constraint on `(election_id, pu_id, party_id, aggregation)` or any equivalent. The only guard against duplicate vote rows is scattered application code: the scraper's read-then-count ward check (`sync.py:380-388`) and the importer's file-level "skip already-loaded source name" idempotency. Neither is transactional against concurrent writers, and neither survives a partial-then-retried load. The database — the last line of defence for an integrity-critical dataset — has no backstop, so any re-run of `seed_historical`, a partial PU sync that resumes, or an admin re-submit can insert duplicate vote rows that F-101's grain-blind sums then compound.
- **Impact**: Silent vote inflation with no schema-level detection. For a civic-integrity project this is a Critical structural gap; a single accidental double-seed corrupts published totals with no error raised.
- **Repro / Evidence**: `models.py:255` — `__table_args__ = (Index("ix_results_election_party", ...), Index("ix_results_state", ...), Index("ix_results_aggregation", ...))`. No `UniqueConstraint`. `sync.py:459` `session.add(ElectionResult(...))` has no upsert/on-conflict.
- **Recommended fix**: Add a unique constraint (or partial unique indexes per grain) on the natural key of a result row and convert writes to upserts (`INSERT ... ON CONFLICT DO UPDATE`). Backfill-dedupe existing rows in the same migration.
- **Effort**: M
- **Tags**: data-integrity, migration-required, election-integrity

### F-103: SSE stream on 2 synchronous gunicorn workers wedges the API on live day
- **Severity**: Critical
- **Persona**: Architect
- **Surface**: backend, infra
- **Files**: `backend/app/api/live.py:22-30`, `.do/app.yaml:12`
- **Problem**: `/api/live/events` is an infinite generator (`while True: time.sleep(15)`) that holds its worker for the entire client connection. The web service runs `gunicorn -w 2` with the default **sync** worker class and no threads (`app.yaml:12`). A sync worker serves exactly one request at a time, so each live EventSource connection permanently occupies one of only two workers. At two concurrent stream clients, 100% of workers are consumed and every other `/api/*` request (results, analysis, overview) blocks until a stream disconnects. The frontend opens these streams on the dashboard, so this saturates precisely when a live election draws traffic.
- **Impact**: Hard concurrency wall at ~2 simultaneous viewers on the exact day the product exists to serve. The API stops responding for all users. This is the single most acute scaling wall in the system.
- **Repro / Evidence**: Open three `curl -N https://.../api/live/events` connections; the third and all normal API calls hang.
- **Recommended fix**: Do not serve SSE from sync workers. Either move streaming to an async worker class (gunicorn + `gevent`/`uvicorn` workers) so a worker multiplexes many idle streams, or drop SSE for short-interval polling of a lightweight `/api/live/status` endpoint, or front the stream with a broker (Postgres LISTEN/NOTIFY or Redis pub/sub) on a dedicated async process. Cap per-connection lifetime regardless.
- **Effort**: M
- **Tags**: scaling-wall, concurrency, live-load, infra

### F-104: Scraper daemon is an unshardable singleton with no row-locking — sync throughput ceiling
- **Severity**: High
- **Persona**: Architect
- **Surface**: backend, infra
- **Files**: `.do/app.yaml:76-86`, `backend/app/scraper/sync.py:274-291`, `backend/app/scraper/daemon.py:64-132`
- **Problem**: All sync flows through one worker (`instance_count: 1`) ticking a global queue. `select_next_targets` picks work with a plain `SELECT ... ORDER BY sync_priority LIMIT n` and **no `FOR UPDATE SKIP LOCKED`** (`sync.py:282-290`), so the design cannot be scaled horizontally: a second daemon instance would select and reprocess the same election rows, and the walk writes results (F-102 has no unique backstop). At national live load — 37 states, thousands of wards each, one ward per tick, `30 × burst` API calls per 120s cycle — a single serialized worker cannot keep the live set current; results lag hours behind INEC uploads.
- **Impact**: Throughput ceiling on live-election freshness with no horizontal escape hatch. Degrades gracefully (staleness, not outage), but caps the system's core value proposition on live day.
- **Repro / Evidence**: `sync.py:304` `targets = select_next_targets(session, limit=max_api_calls)` selects unlocked rows; running two daemons double-processes.
- **Recommended fix**: Introduce claim-based work distribution — `FOR UPDATE SKIP LOCKED` on target selection (or a per-state lease column) so the daemon can run N instances partitioned by state/priority. Pair with F-102's upsert so re-processing is idempotent.
- **Effort**: L
- **Tags**: scaling, scraper-coupling, concurrency

### F-105: Materialized-view subsystem half-wired — refresh coupling broken, reads inconsistent
- **Severity**: High
- **Persona**: Architect
- **Surface**: backend
- **Files**: `backend/app/analysis/refresh.py:30-57`, `backend/app/scraper/daemon.py:75-132`, `backend/app/importer/loaders/generic_csv.py:159-161`, `backend/app/api/analysis.py:59-114`
- **Problem**: Four MVs are built and uniquely indexed (migration 0003) and `refresh_materialized_views()` exists, but the wiring is inconsistent. (1) The **only** caller is the CSV importer (`generic_csv.py:161`); the daemon never imports or calls refresh, despite `refresh.py:3` and `daemon.py`'s docstring claiming "by the daemon nightly." (2) Live scraper PU writes and all admin writes therefore never refresh any MV. (3) The API reads only `mv_enp` (`analysis.py:66-92`); turnout, swing, and competitiveness recompute live from base tables (`analysis.py:25-56`, `166-193`, `122-163`), so three of four MVs are maintained but never read. Net effect: during a live election the ENP endpoint serves stale MV data while every neighbouring endpoint computes live — inconsistent freshness within one dashboard — and the project pays refresh cost for views it doesn't read.
- **Impact**: Silent staleness on the one MV-backed endpoint during live updates, plus wasted maintenance. Also a latent reliability issue: `_refresh_one` falls back to a blocking (non-`CONCURRENT`) `REFRESH` on *any* exception (`refresh.py:52`), which takes an ACCESS EXCLUSIVE lock and freezes reads of that MV.
- **Repro / Evidence**: `grep refresh_materialized_views backend/app` → single call site in `generic_csv.py`. `daemon.py` has no `refresh` import. `analysis.py` reads `mv_enp` only.
- **Recommended fix**: Decide the MV contract: either read all four MVs from the API and refresh them on a scheduled cadence owned by the daemon (concurrent-only, with a real "not populated" guard rather than blanket `except Exception`), or drop the unused MVs and keep compute-on-read. Do not leave a maintained-but-unread middle state.
- **Effort**: M
- **Tags**: materialized-views, coupling, freshness, reliability

### F-106: `lazy="selectin"` on the 4-level geography hierarchy — every `select(State)` fetches the whole PU tree
- **Severity**: High
- **Persona**: Architect
- **Surface**: backend
- **Files**: `backend/app/models.py:78`, `backend/app/models.py:95`, `backend/app/models.py:107`, `backend/app/api/analysis.py:262`, `backend/app/api/calendar.py:33`, `backend/app/api/admin.py:65`
- **Problem**: `State.lgas`, `Lga.wards`, and `Ward.polling_units` are all `lazy="selectin"`. Selectin eagerly loads relationships whenever parent objects are materialized, and the chain cascades: loading `State` objects triggers a follow-up load of all their LGAs, then all wards of those LGAs, then all polling units of those wards. Several public/admin endpoints materialize `State` ORM objects — `winners_per_state` (`analysis.py:262`, backs the homepage choropleth), the calendar view (`calendar.py:33`), and admin (`admin.py:65`) — so a single `select(State)` with no loader options pulls the entire national geography down to ~176k polling-unit rows into memory per request.
- **Impact**: Memory and query blowup on public endpoints as the PU table fills via scraping. `states.py` accidentally dodges it by selecting `Lga` directly, but the default is a landmine any future `select(State)` steps on. At national data volume this turns the choropleth endpoint into a multi-hundred-thousand-row fetch.
- **Repro / Evidence**: `models.py:78` `relationship(back_populates="state", lazy="selectin")` × 3 levels; `analysis.py:262` `states = {s.state_id: s for s in session.scalars(select(State))}` fires the cascade.
- **Recommended fix**: Default these relationships to `lazy="raise"` (or `"select"`) and opt into eager loading explicitly with `selectinload()` only where a bounded subtree is needed. Never eager-load `polling_units` from `State`.
- **Effort**: S
- **Tags**: orm, n-plus-one, scaling, quick-win

### F-107: Legacy monolith + committed SQLite DB still wired via Procfile — dual source of truth
- **Severity**: Medium
- **Persona**: Architect
- **Surface**: shared, infra
- **Files**: `Procfile:1`, `.do/app.yaml:12`, `election_dashboard.py` (repo root, 94 KB), `election_data.db` (repo root, 26 MB)
- **Problem**: The repo root still contains the pre-refactor monolith `election_dashboard.py` and a 26 MB SQLite `election_data.db` (plus `-wal`/`-shm`). `Procfile:1` still boots the **legacy** app on SQLite (`gunicorn election_dashboard:app`), while `.do/app.yaml:12` boots the **new** factory on managed Postgres (`gunicorn ... app.wsgi:app`). New modules cite the old file as their porting source (`scraper/discovery.py`, `importer/loaders/excel_candidates.py`, `ocr/ec8a.py`). Two apps, two datastores, two entrypoints coexist in one repo with no marker of which is canonical.
- **Impact**: Any Procfile-driven deploy (Heroku, `foreman`, some CI) silently runs the old app against a stale committed SQLite snapshot. Repo bloat and a "which is truth" hazard for every new contributor on a just-open-sourced project.
- **Repro / Evidence**: `Procfile` names `election_dashboard:app`; `app.yaml` names `app.wsgi:app`. Both present, no README note reconciling them.
- **Recommended fix**: Delete or archive the monolith and the committed DB (add to `.gitignore`; purge from history if size matters), and either delete `Procfile` or repoint it at `app.wsgi:app` so all deploy paths agree.
- **Effort**: S
- **Tags**: migration-debris, dual-codebase, repo-hygiene

### F-108: Calendar computes live-state targets that the daemon discards — split "what's live" authority
- **Severity**: Medium
- **Persona**: Architect
- **Surface**: backend
- **Files**: `backend/app/scraper/calendar.py:88-113`, `backend/app/scraper/daemon.py:106-132`, `backend/app/scraper/sync.py:159-170`
- **Problem**: `decide_mode()` returns a `WakeDecision` carrying `state_ids` of the currently-live states (`calendar.py:88`), but the daemon uses only `decision.mode` and `decision.interval_seconds` — it never reads `state_ids` (`daemon.py:108-132`). Live prioritisation instead depends on a *separate* mechanism: `_compute_priority` set during header discovery, which runs at most once per 24h (`daemon.py:80`). So "this election is live" has two independent sources of truth (calendar vs. once-daily priority column) that must agree, and the daemon honours only the weaker one.
- **Impact**: A calendar-live election that header-discovery hasn't yet tagged priority=1 (new IReV row, or discovery not yet run) won't be aggressively synced even though `decide_mode` says "live." The computed `state_ids` is dead output — a leaky abstraction that implies targeting that doesn't happen.
- **Repro / Evidence**: `calendar.py:88` builds `state_ids`; no reference to `decision.state_ids` anywhere in `daemon.py`.
- **Recommended fix**: Make the daemon consume `decision.state_ids` to bump those elections' priority (or filter `select_next_targets`) at tick time, so the calendar is the single authority for liveness. Remove the field if it is not going to be used.
- **Effort**: S
- **Tags**: single-source-of-truth, scraper-coupling, dead-output

### F-109: Party is an uncontrolled dimension — six autocreate sites mint rows from raw codes
- **Severity**: Medium
- **Persona**: Architect
- **Surface**: backend
- **Files**: `backend/app/importer/normalizers.py:45-49`, `backend/app/scraper/sync.py:456`, `backend/app/api/admin.py:175`, `backend/app/api/admin.py:297`, `backend/app/importer/loaders/candidate_csv.py:79`, `backend/app/importer/loaders/excel_candidates.py:89`
- **Problem**: `resolve_party(..., autocreate=True)` silently inserts a new `Party` whenever a code isn't found (`normalizers.py:45`), and six call sites across the scraper, both admin write paths, and two importers pass `autocreate=True`. All analysis groups votes by `party_id`, so any typo or casing/whitespace variant in a scraped or hand-typed code that survives the light normalization mints a distinct party and fragments that party's totals across two rows.
- **Impact**: Vote aggregation for a real party can split across a canonical row and an autocreated variant, understating totals and polluting the party dimension of an integrity-critical dataset. The canonical party list should be governed, not emergent.
- **Repro / Evidence**: Feed party_code "A P C" or "apc " through `sync._persist_ward_pu_results`; `resolve_party` uppercases/strips (`normalizers.py:34` only `.upper()`, relying on caller strip) and, on miss, creates `Party(code=..., name=code)`.
- **Recommended fix**: Restrict autocreate to a single vetted ingestion path (or none); have the scraper and admin paths resolve against a controlled party registry and route unknowns to a review queue rather than auto-minting. Add a normalization + alias table.
- **Effort**: M
- **Tags**: data-governance, dimension, election-integrity

### F-110: Contradictory schema-ownership assumptions between code and infra on a shared cluster
- **Severity**: Medium
- **Persona**: Architect
- **Surface**: shared, infra
- **Files**: `backend/app/db.py:6-9`, `backend/app/db.py:25`, `backend/app/db.py:45-54`, `.do/app.yaml:110-119`
- **Problem**: `db.py` documents a model where DO hands the app a *non-owner* role that can't write `public`, so the app creates and pins an `elections` schema via `search_path` (`db.py:6-9`). But `app.yaml:114-119` provisions a *dedicated database with an owner role* ("full DDL rights on its own DB, no PG public-schema gotchas") on PG **16**, while the docstring says PG **15 dev tier**. `SCHEMA_NAME` defaults to `""` (no search_path pinning) and `app.yaml` sets no `DB_SCHEMA`, so the two mental models are reconciled only implicitly by the role's default `search_path`.
- **Impact**: Migration/table ownership on the shared `apcng-db` cluster rests on an undocumented implicit behaviour. A future role/cluster change (or setting `DB_SCHEMA`) can silently split "where migrations create tables" from "where the app looks for them," breaking every unqualified query.
- **Repro / Evidence**: `db.py:25` `SCHEMA_NAME = os.environ.get("DB_SCHEMA", "")`; conditional `search_path` block at `db.py:45` only fires when non-empty; `app.yaml` never sets it.
- **Recommended fix**: Pick one model, set `DB_SCHEMA` explicitly in `app.yaml`, and make the migration and the engine agree on it deterministically. Update `db.py`'s docstring to the real PG16/owner-DB reality.
- **Effort**: S
- **Tags**: config-drift, shared-cluster, migration-ownership

### F-111: No connection-pool sizing on a shared cluster — cross-project exhaustion risk
- **Severity**: Medium
- **Persona**: Architect
- **Surface**: backend, infra
- **Files**: `backend/app/db.py:36-57`, `.do/app.yaml:4-15`, `.do/app.yaml:76-86`, `.do/app.yaml:110-119`
- **Problem**: `init_engine` sets `pool_pre_ping=True` but no `pool_size`, `max_overflow`, or `pool_recycle`, so each process uses SQLAlchemy defaults (5 base + 10 overflow = up to 15 connections). The web service runs 2 gunicorn workers (up to ~30 connections), plus a scraper worker (up to 15), plus PRE/POST-deploy jobs — all against the **shared** `apcng-db` cluster that also serves the apcng project. DO's smaller managed-PG tiers cap total connections low (tens), and the cap is shared across both projects.
- **Impact**: Under load or during a deploy (jobs + web + worker concurrent), this app can exhaust the shared cluster's connection limit and take down apcng too — a cross-project blast radius from an unbounded default pool.
- **Repro / Evidence**: `db.py:39` `create_engine(url, echo=echo, pool_pre_ping=True, future=True)` — no pool bounds. `app.yaml:12` `-w 2`; worker + jobs bind the same `${db.DATABASE_URL}`.
- **Recommended fix**: Set explicit modest `pool_size`/`max_overflow` per process sized to the shared cluster's cap and worker count, add `pool_recycle`, and consider a pgbouncer/connection-pool in front of the shared cluster. Budget connections across both projects deliberately.
- **Effort**: S
- **Tags**: shared-cluster, connection-budget, cost, reliability

### F-112: Access-gate exemptions hardcode blueprint prefixes — routing/policy coupling
- **Severity**: Low
- **Persona**: Architect
- **Surface**: backend
- **Files**: `backend/app/api_gate.py:28-34`, `backend/app/api_gate.py:62-72`, `backend/app/__init__.py:54-68`
- **Problem**: `install_api_gate` decides "which endpoints are open" from a hardcoded `EXEMPT_PREFIXES` tuple of URL strings (`api_gate.py:28`), decoupled from the blueprints those URLs belong to. Adding or renaming a public blueprint requires remembering to edit this separate tuple; a mismatch either gates a meant-to-be-public route or exposes one meant to be keyed. Access policy is expressed as string prefixes rather than a property of each blueprint.
- **Impact**: Low blast radius today, but a real coupling seam: the gate and the route table can drift, and on a public API the failure mode (accidentally gating or exposing) is quietly wrong rather than loudly broken.
- **Repro / Evidence**: `api_gate.py:33` lists `/api/methodology` etc. as strings; `__init__.py:59` registers `calendar_api.bp` etc. with their own `url_prefix` — two places to keep in sync.
- **Recommended fix**: Attach an access attribute to each blueprint (e.g. a registry of public vs. keyed blueprints) and derive the exemption set from it, so registration and policy live in one place.
- **Effort**: S
- **Tags**: coupling, access-policy, maintainability

---

## Architecture verdict

I would not bet this codebase scales to the next 10× as-is, and more urgently I would not trust
its published numbers under the current write topology. The blueprint/scraper/importer/analysis
decomposition is genuinely sound and the migrations are disciplined, so the bones are good — but
the `election_results` table violates single-source-of-truth at the grain level (F-101) and has no
uniqueness backstop (F-102), which for a project whose entire reason to exist is result integrity
is disqualifying until fixed. The live-serving path then hits two hard walls at exactly the moment
it matters: SSE on synchronous workers wedges the API at two viewers (F-103), and the singleton,
lock-free daemon cannot fan out to 37-state load (F-104). Fix the two integrity flaws first
(they are live-today for FCT 2026), then the SSE worker model and the ORM eager-load default
(F-106) as the cheapest high-leverage scaling wins; the MV, calendar-authority, party-dimension,
and shared-cluster items are the second wave. With F-101 through F-106 addressed, the architecture
is a credible base for national scale; without them, it will publish wrong totals before it ever
runs out of capacity.
