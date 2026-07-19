# Cost Audit — Nigeria Election Dashboard — 2026-07-19

**Persona:** Cost (F-901…) · **Surface:** infra · **Method:** inferred from `.do/app.yaml` + scraper code. No cloud APIs called. All $ figures are estimates from DO App Platform / Droplet / Managed-PG list pricing (USD, `fra` region).

---

## Executive summary

The project's **own incremental DigitalOcean spend is ~$19–34/mo, most likely ~$23–25/mo**. It is a small bill — three `basic-xxs` App Platform components at $5 each ($15) plus a redundant $4–6 Caddy droplet plus build-minute/job overhead. The managed Postgres cluster adds **$0 incremental** because it is the *shared* `apcng-db` production cluster (its ~$15/mo is borne by apcng) — but that sharing is the single largest **risk**, not saving: an election-day write burst can starve the sibling app.

There is no runaway spend. The waste is structural, not scale-driven:
1. A **Caddy proxy droplet** ($4–6/mo) that App Platform's native custom-domain + managed TLS already replaces (`.do/app.yaml:18-19,52-53` route split is done in-app).
2. **`SCRAPER_BURST_FACTOR=5.0` committed permanently** (`.do/app.yaml:105`), which the daemon's own comment says produces **24,000 IReV calls/day** while any queue backlog exists (`daemon.py:119-122`) — a rate-limit-ban and shared-DB-CPU risk, though ~$0 direct DO cost.
3. **Seven identical backend builds per deploy** (web + scraper + 5 jobs all run `pip install -r requirements.txt` on `source_dir: backend`) — wasted build minutes on every push.

GitHub Actions is currently **free** because the repo is public; the `sleep 360` in the e2e job (`ci.yml:64`) is latent cost only if it goes private.

### Per-component monthly cost (estimate)

| Component | Type | Slug / tier | Cnt | Low | High | Notes |
|---|---|---|---|---|---|---|
| `web` (Flask/gunicorn) | service | basic-xxs | 1 | $5 | $5 | `app.yaml:13-14`, floor tier |
| `frontend` (Next.js `npm start`) | service | basic-xxs | 1 | $5 | $5 | `app.yaml:49-50`, always-on Node SSR |
| `scraper` (daemon) | worker | basic-xxs | 1 | $5 | $5 | `app.yaml:85-86`, no scale-to-zero |
| DB (`apcng-db` shared PG16) | managed PG | shared cluster | — | $0 | $3 | `app.yaml:110-119`; ~$15 cluster borne by apcng; only storage growth is incremental |
| Caddy reverse-proxy | droplet | s-1vcpu-512mb | 1 | $4 | $6 | **redundant** — see F-901 |
| Jobs ×5 (1 PRE + 4 POST deploy) | job runtime | basic-xxs (prorated) | — | $0 | $2 | `app.yaml:121-191`, short-lived |
| Build minutes | build | — | — | $0 | $10 | 7 backend + 1 frontend build/deploy — see F-904/905 |
| Egress (DO outbound) | bandwidth | — | — | $0 | $1 | IReV pulls are *inbound* = free |
| GitHub Actions | CI | GH-hosted | — | $0 | $0 | free while repo public |
| **Total (project's own spend)** | | | | **~$19** | **~$34** | midpoint ~$23–25/mo |

### Severity summary

| Severity | Count | Findings |
|---|---|---|
| Critical | 1 | F-903 |
| High | 2 | F-901, F-902 |
| Medium | 2 | F-904, F-905 |
| Low | 3 | F-906, F-907, F-908 |

---

## Findings

### F-901: Redundant Caddy proxy droplet — App Platform already does custom-domain + TLS
- **Severity**: High
- **Persona**: Cost
- **Surface**: infra
- **Files**: `.do/app.yaml:18-19,52-53` (in-app route split); brief §Infra (`elections-proxy` droplet ~$4/mo)
- **Problem**: A separate Caddy droplet (`elections-proxy`) fronts `elections.innoedgetech.com`, but the App Platform spec already routes `/api` → `web` (`app.yaml:18-19`) and `/` → `frontend` (`app.yaml:52-53`). App Platform natively terminates custom domains with free managed Let's Encrypt TLS, so the droplet duplicates work the platform does for free. Nothing in the repo (no `Caddyfile`, no Dockerfile) shows the droplet performing header injection or path rewriting the ingress cannot.
- **Impact**: $4–6/mo of pure waste (droplet + any snapshot/backup add-on). At 10× scale it stays flat — an always-there tax, plus a second box to patch (security/ops cost).
- **Repro / Evidence**: `grep -ri caddy` over the repo returns nothing — the proxy is hand-configured outside IaC, so it is undocumented drift. The route split already exists in `app.yaml`.
- **Recommended fix**: Point `elections.innoedgetech.com` directly at the App Platform app as a managed custom domain (free TLS), or front it with Cloudflare's free tier. Destroy the droplet once DNS cuts over and TLS validates.
- **Current monthly cost**: ~$4–6 · **Projected after fix**: $0 · **Effort**: S · **Payback**: immediate (< 1h work, saves every month thereafter)
- **Tags**: infra, quick-win, redundant-resource

### F-903: Shared `apcng-db` cluster has no resource isolation — election load can degrade the sibling app
- **Severity**: Critical
- **Persona**: Cost
- **Surface**: infra
- **Files**: `.do/app.yaml:110-119`; write path `scraper/phases.py:76-145` (per-call upserts) driven by `daemon.py:106-132`
- **Problem**: The dashboard's Postgres DB is a database+role carved out of the **shared production `apcng-db` cluster**. Managed PG isolates schemas/roles but **not CPU, IOPS, or connections** — those are cluster-wide. On election day (live mode, 120s ticks, `daemon.py:108-112`) or during a burst backfill drain (F-902), the scraper runs sustained upsert-heavy transactions (`phases.py:upsert_lga/ward/polling_unit`, each a `SELECT`+`INSERT`) on the same physical instance serving apcng. The smallest managed tier (1 vCPU / 1 GB) has no headroom for a second app's write spike.
- **Impact**: A sibling **production outage** is the cost here, not a line item — if election-day load pegs cluster CPU/IOPS, apcng degrades or errors, and vice-versa (apcng load could blind the dashboard exactly when Nigeria is watching results). Blast radius spans two unrelated products off one $15/mo box. This is the coupling the rubric flags as Critical: outage-cost to a sibling.
- **Repro / Evidence**: `app.yaml:118 cluster_name: apcng-db` with `production: true`; the comment (`app.yaml:114-117`) documents data isolation but is silent on the *shared-compute* coupling. No connection cap or statement-timeout is set in `config.py` for the scraper's engine.
- **Recommended fix**: (a) Cheapest mitigation now — cap the scraper's SQLAlchemy pool small and set a conservative `statement_timeout`, and keep `SCRAPER_BURST_FACTOR=1.0` (F-902) so steady-state write rate stays low. (b) Proper fix before the next major election — move the dashboard to its own smallest managed PG cluster (+~$15/mo) to decouple the blast radius, or right-size the shared cluster up one tier and reserve headroom. Decide on the $15/mo vs. sibling-outage-risk trade explicitly.
- **Current monthly cost**: $0 incremental (amortized) · **Projected after fix**: $0 (pool cap) or +$15 (dedicated cluster) · **Effort**: S (caps) / M (split cluster) · **Payback**: risk-avoidance — one avoided election-day outage dwarfs $15/mo
- **Tags**: infra, shared-cluster, coupling, reliability-cost

### F-902: `SCRAPER_BURST_FACTOR=5.0` committed permanently → ~24,000 IReV calls/day on backlog
- **Severity**: High
- **Persona**: Cost
- **Surface**: infra
- **Files**: `.do/app.yaml:103-105`; budget math `scraper/daemon.py:106-132`; safe default `config.py:59`
- **Problem**: The safe default is `1.0` (`config.py:59`, ~960 calls/day per the code comment), but the deployed spec hard-codes `5.0` (`app.yaml:105`). In idle mode with any queue backlog, the daemon then runs `budget = int(20 * 5) = 100` calls per cycle and shortens the sleep to `1800/5 = 360s`, which its own comment states is **"24,000 calls/day"** (`daemon.py:119-122`). The token bucket caps at 30 req/min = 43,200/day (`irev_client.py:51,84`), so 24k/day is not throttled — it runs at full tilt until the backlog clears.
- **Impact**: Direct DO cost ≈ **$0** (fixed-price worker; IReV responses are *inbound* = free egress). The real cost is **reliability/reputation**: `app.yaml:102` itself warns "8.0+ may trip INEC rate limits," and 24k/day against INEC's public SPA endpoint risks an **IP ban on the DO egress address** — which kills the scraper precisely on election day, the one day the product exists for. It also amplifies F-903 (write burst on the shared cluster). Leaving 5.0 as the committed steady-state value is the waste: burst is a one-off backfill tool, not a permanent setting.
- **Repro / Evidence**: `app.yaml:105 value: "5.0"` overriding `config.py:59` default `"1.0"`; `daemon.py:127-130` shortens sleep by `1800/burst`.
- **Recommended fix**: Set the committed value back to `"1.0"` (or delete the env so the default applies). Bump to 5.0 **temporarily** via `doctl`/console only during an intentional initial backfill, then revert. Better: gate high burst behind the calendar being in `idle` with no imminent election.
- **Current monthly cost**: ~$0 direct (ban risk unpriced) · **Projected after fix**: ~$0, ban risk removed · **Effort**: S (one-line spec change) · **Payback**: immediate
- **Tags**: infra, quick-win, rate-limit, config-hygiene

### F-904: Every deploy rebuilds the backend 7× — one identical `pip install` per component
- **Severity**: Medium
- **Persona**: Cost
- **Surface**: infra
- **Files**: `.do/app.yaml:11,83,128-129,140-141,152-153,170-171,186-187` (7 × `build_command: pip install -r requirements.txt`, all `source_dir: backend`)
- **Problem**: `web`, `scraper`, and all five jobs (`migrate`, `seed`, `discover-headers`, `seed-historical`, `seed-users`) each declare their own `build_command: pip install -r requirements.txt` on the same `source_dir: backend`. App Platform builds each component in its own build container — it does not share a built image across components — so any change under `backend/` triggers **7 identical builds** of a requirements set that includes heavy wheels (`numpy`, `Pillow`, `pytesseract`, `psycopg[binary]` — `requirements.txt:5,11,12,13`). `deploy_on_push: true` means this fires on every commit to `main`.
- **Impact**: ~10–14 build-minutes/deploy (7 × ~1.5min backend + ~3–4min frontend). At 15–40 pushes/mo that is ~200–560 build-min/mo. Beyond the free build-minute allotment this is **~$0–10/mo** and grows linearly with commit cadence (a hidden cost cliff on a busy sprint).
- **Repro / Evidence**: Seven components share `source_dir: backend` + the identical `build_command`; DO builds them independently.
- **Recommended fix**: Build the backend image **once**, push to DOCR, and reference it by digest from `web`, `scraper`, and the jobs (`image:` instead of per-component `build_command`). Alternatively collapse the seed jobs (F-905) to cut the count. Set a DOCR retention/garbage-collection policy so old tags don't accrue storage.
- **Current monthly cost**: ~$0–10 (build overage) · **Projected after fix**: ~$0–2 · **Effort**: M · **Payback**: ~1–3 months at a moderate push cadence; also speeds deploys
- **Tags**: infra, build-minutes, docr, redundant-build

### F-905: Four separate POST_DEPLOY seed jobs each spin their own container + build
- **Severity**: Medium
- **Persona**: Cost
- **Surface**: infra
- **Files**: `.do/app.yaml:134-191` (`seed`, `discover-headers`, `seed-historical`, `seed-users`)
- **Problem**: Four idempotent POST_DEPLOY jobs run sequentially after every deploy, each with its own `pip install` build (counted in F-904) and its own container cold-start. They do closely related work — seed reference data, discover headers, seed historical CSVs, upsert users — and could run as ordered steps inside a single job entrypoint.
- **Impact**: 4× job-container spin-ups + 4× backend builds per deploy instead of 1×. Marginal in $ (jobs are short and prorated, ~$0–2/mo) but it compounds F-904's build waste and adds deploy latency. At 10× deploy frequency the build-minute component scales with it.
- **Repro / Evidence**: Four `kind: POST_DEPLOY` blocks, each `source_dir: backend` + `pip install` + a distinct `python -m app.*` runner.
- **Recommended fix**: Merge into one POST_DEPLOY job whose `run_command` invokes a small `app.seed_all` orchestrator calling the four steps in order (each already idempotent per the spec comments). Keeps behavior, cuts builds 4→1 and container starts 4→1.
- **Current monthly cost**: ~$0–2 (compounds F-904) · **Projected after fix**: ~$0 · **Effort**: S–M · **Payback**: rolls up with F-904; faster deploys
- **Tags**: infra, jobs, deploy-latency, consolidation

### F-906: e2e CI job burns a fixed `sleep 360` every push to main
- **Severity**: Low
- **Persona**: Cost
- **Surface**: infra
- **Files**: `.github/workflows/ci.yml:50-68` (esp. `:64 run: sleep 360`)
- **Problem**: The `e2e` job waits a hard-coded 6 minutes for the DO deploy to roll out, then probes. On a GitHub-hosted runner every push to `main` idles a runner for 6 min doing nothing, on top of the actual probe and the `backend`/`frontend` jobs.
- **Impact**: **$0 today** — the repo is public, so GH-hosted minutes are free. It is a **latent cost**: if the repo ever goes private, this is ~6 wasted runner-min/deploy (~200–560 min/mo billable). It also delays red/green feedback by 6 min every merge.
- **Repro / Evidence**: `ci.yml:64 run: sleep 360` inside the push-only e2e job (`ci.yml:55`).
- **Recommended fix**: Replace the fixed sleep with a bounded readiness poll (curl `/api/health` every 15s up to a timeout) so it proceeds as soon as the deploy is live and fails fast if it never is. Guards against both the latent cost and slow feedback.
- **Current monthly cost**: $0 (public repo) · **Projected after fix**: $0, latent-cost removed · **Effort**: S · **Payback**: immediate if repo ever goes private; feedback speed now
- **Tags**: ci, latent-cost, quick-win

### F-907: Always-on scraper worker idles 24h/day for most of the year
- **Severity**: Low
- **Persona**: Cost
- **Surface**: infra
- **Files**: `.do/app.yaml:76-108`; idle behavior `daemon.py:118-132`, `calendar.py:108-113` (idle_interval 86,400s)
- **Problem**: The scraper is a persistent `basic-xxs` worker ($5/mo). Outside election windows the calendar puts it in `idle` mode sleeping up to 24h between ticks (`calendar.py:58,111`), i.e. it is paid to sleep on most calendar days. App Platform workers cannot scale to zero.
- **Impact**: ~$5/mo for a process that is meaningfully busy only around scheduled elections. Not waste in the strict sense — election-day responsiveness (120s live ticks, `daemon.py:108`) justifies always-on — but it is $60/yr for episodic work worth naming.
- **Repro / Evidence**: `run_command: python -m app.scraper.daemon` (`app.yaml:84`) always running; idle sleep `min(decision.interval_seconds, ...)` up to 86,400s.
- **Recommended fix**: Accept the $5/mo for election-day responsiveness (recommended — a GHA-cron or DO-Function alternative has 5-min-floor cadence and cold-starts that hurt live mode), **or** if elections are rare, drive sync from a scheduled trigger during active windows only and stop the worker between cycles. Document the deliberate choice so it isn't mistaken for waste later.
- **Current monthly cost**: ~$5 · **Projected after fix**: ~$5 (keep) or ~$0–1 (scheduled) · **Effort**: M (if changed) · **Payback**: ~1yr to recoup an M-effort change — usually not worth it; flagged for awareness
- **Tags**: infra, scale-to-zero, accepted-cost

### F-908: Frontend is correctly a Node service, not a static export (counters the "make it static" hypothesis)
- **Severity**: Low
- **Persona**: Cost
- **Surface**: infra
- **Files**: `.do/app.yaml:47-51` (`npm start`, basic-xxs); `frontend/next.config.mjs:3-24` (`async rewrites()`); NextAuth server routes per brief (`app/api/auth/[...nextauth]`, `app/admin-api/[...path]/route.ts`)
- **Problem**: The always-on Node server ($5/mo) is a natural "can this be a cheaper static export?" target. It cannot: `next.config.mjs` uses `async rewrites()` (server-only), the app runs **NextAuth** (server-side session/callback routes) and a **server-side admin proxy** that injects `X-Admin-Token`. `output: 'export'` would break all three. It is already at the floor tier (basic-xxs) with `instance_count: 1`, so there is no right-sizing headroom either.
- **Impact**: $0 achievable saving on App Platform without re-architecting auth. Documenting this prevents a future "just make it static to save $5" change that would silently break login and the admin surface.
- **Repro / Evidence**: `next.config.mjs:18-23` returns dynamic rewrites; no `output` key present (confirmed — grep shows only `export default nextConfig`); `next-auth` in `package.json`.
- **Recommended fix**: Keep as-is. If $5/mo ever matters at scale, the only real lever is Cloudflare Pages + `@cloudflare/next-on-pages` (free hosting, Workers for the auth/proxy routes) — an **L-effort** re-platform with marginal payback; not recommended now.
- **Current monthly cost**: ~$5 · **Projected after fix**: ~$5 (no viable cheaper option) · **Effort**: L (if pursued) · **Payback**: > 1yr — do not pursue
- **Tags**: infra, no-op, documentation

---

## Cost verdict

- **Total project spend (own incremental):** ~$19–34/mo, midpoint **~$23–25/mo**. Small and not scale-threatened.
- **Total identifiable monthly waste:** **~$8–16/mo** — the redundant Caddy droplet ($4–6, F-901) + redundant backend build minutes ($0–10, F-904/905). Everything else is either $0-direct-risk (F-902/F-903) or accepted cost (F-907/F-908).
- **Achievable in one remediation sprint:** kill the droplet (F-901) and consolidate builds/seed-jobs (F-904/905) → **~$8–16/mo saved**, plus two **risk removals with ~$0 direct cost but high blast-radius**: revert `SCRAPER_BURST_FACTOR` to 1.0 (F-902) and cap the scraper's DB pool / decide the shared-cluster split (F-903).
- **Unit economics at 10× scale:** the App Platform trio stays ~$15/mo (single instances, no autoscale in spec) — this dashboard does not have a compute cost cliff. The **only** thing that breaks at 10× is F-903: more election-day traffic on the *shared* `apcng-db` cluster raises the odds of a two-for-one outage. Spending $15/mo on a dedicated cluster before the next major cycle is the one scale-driven investment worth pre-committing.

### Top 3 savings
1. **F-901 — delete the Caddy droplet, use App Platform native TLS:** **$4–6/mo**, effort S, payback immediate.
2. **F-904 + F-905 — build backend once (DOCR image) + collapse 4 seed jobs into 1:** **~$5–10/mo** in build minutes, effort M, plus faster deploys.
3. **F-903 — decouple from the shared `apcng-db` cluster (pool cap now; dedicated cluster before next election):** **$0 direct**, but prevents a sibling-app outage that would cost far more than the +$15/mo a dedicated cluster runs.
