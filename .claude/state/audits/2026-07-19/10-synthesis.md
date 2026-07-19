# 10 — Chief Auditor synthesis — Nigeria Election Dashboard — 2026-07-19

**Persona:** Chief Auditor (synthesis of personas 01–09). **Inputs:** all nine reports in this directory. **Ground truth:** reconciled against live code + the live DO app spec by the orchestrator; those ratings override any single persona where they differ (noted inline).

---

## 1. Executive summary

The bones are good and the numbers are not yet trustworthy. The refactor produced a clean Flask app-factory with well-separated blueprints, disciplined Alembic migrations, genuinely well-tested statistical math, and honest transparency *intentions* (a `/methodology` page, per-view source lines). But for a project whose entire reason to exist is correct vote totals, **result integrity has no automated backstop at any layer** — not in the schema (no unique constraint on votes, mixed aggregation grains summed blind), not in ingestion auth (admin write path fails open by default), not in refresh (materialized views never refreshed by the scraper), and not in the UI (a 2%-reporting provisional count is painted the same solid party color as a certified 2023 final).

The nine personas filed **108 findings: 18 Critical, 28 High, 36 Medium, 26 Low.** After reconciliation those 18 raw Criticals collapse to ~16 unique root causes (F-201≡F-701 and F-103≡F-401 are the same issue seen twice), and two ratings were corrected by ground truth: the API-gate `Sec-Fetch-Site` bypass is genuinely **Low** (F-207 correct, F-704 down-rated — the gated data is free by design), and CI is not merely red, it is **`disabled_manually`** and has not run since 2026-05-16.

**Production is up right now and is not actively breached.** The live `web` service currently sets `ADMIN_TOKEN` as an encrypted secret, so the fail-open admin hole is mitigated *today*. But it is a **latent Critical**: the code fails open by default with no startup guard, and the committed `.do/app.yaml` omits the token — so one spec-based redeploy or console slip re-opens unauthenticated result falsification. The other latent Criticals are equally one-event-away: the election-day capacity wall (2 in-flight requests on one 512 MB box, no rate limiting, no read cache), the Python-side vote aggregation that OOMs the moment PU-level rows land, and the scraper that can silently wedge on a single bad IReV response while the healthcheck stays green.

**The one sentence a maintainer must act on:** before the next live election, put a real integrity backstop on the vote table (DB unique constraint + single-grain-per-election + upsert) and make the admin write path fail *closed* — because today the public choropleth can double-count votes, publish a wrong winner, and render an in-progress lean as a called result, with no schema, no test, and no UI label stopping any of it.

### Finding tally (raw sum across all 9 reports)

| Persona | Critical | High | Medium | Low | Total |
|---|---|---|---|---|---|
| 01 Architect | 3 | 3 | 5 | 1 | 12 |
| 02 Security | 1 | 2 | 3 | 4 | 10 |
| 03 Performance | 2 | 3 | 4 | 4 | 13 |
| 04 Reliability | 3 | 3 | 5 | 4 | 15 |
| 05 Product | 1 | 6 | 6 | 5 | 18 |
| 06 Test/CI | 3 | 4 | 4 | 3 | 14 |
| 07 Adversary | 2 | 3 | 2 | 0 | 7 |
| 08 Newcomer | 2 | 2 | 5 | 2 | 11 |
| 09 Cost | 1 | 2 | 2 | 3 | 8 |
| **Total** | **18** | **28** | **36** | **26** | **108** |

**Reconciliation adjustments to the raw tally:** F-704 High→Low (per ground truth; effective High 27 / Low 27). F-201/F-701 is a *latent* Critical — currently mitigated in the live spec, but fail-open by default. Cross-persona de-duplication brings the 18 Critical IDs down to ~16 unique defects and, thematically, to the five compound clusters in §2.

---

## 2. Compound findings (same root cause, multiple personas)

These are the highest-leverage items in the whole audit: one root cause each, flagged independently by three-to-six personas. Fix the cluster, not the symptom.

### Cluster A — Result integrity has no backstop at any layer  *(the crown jewel)*
**Rolls up:** F-101 (mixed aggregation grains double-count) + F-102 / F-404 (no DB unique constraint on votes) + F-402 / F-406 (stale-as-live: MVs never refreshed by the scraper, staleness never evaluated) + F-501 (provisional/live/manual tallies rendered identically to certified final) + F-201 / F-701 (unauthenticated falsification) + F-301 (PU-scale OOM on the same read path).
**Root cause:** the `election_results` table and every path that writes, reads, refreshes, serves, and labels it lack an integrity guard. Schema has no uniqueness; reads sum across grains with no filter; ingestion auth fails open; refresh is half-wired; the UI carries no provenance. Six independent failure modes, one undefended asset.
**Combined severity:** **Critical** — this is the defining risk of the product.
**The one fix that resolves the most:** enforce **single-grain-per-election + a partial unique constraint on the vote natural key + upsert-on-conflict** (closes F-101, F-102, F-404 and removes the row-explosion substrate F-301 operates on). The other two layers need their own fixes and cannot be skipped: **fail-closed admin auth** (F-201) and a **result-status/provenance model surfaced in the UI** (F-501). Treat those three as a single integrity workstream.

### Cluster B — Falls over on election day
**Rolls up:** F-103 / F-401 (blocking SSE on 2 sync gunicorn workers wedges the whole API at ~2 viewers) + F-302 (2 sync workers on 1×basic-xxs, no read caching, heavy reads polled every 30 s) + F-301 (OOM on the aggregation read path) + F-703 / F-203 (no inbound rate limiting → trivial DoS + unbounded login brute force).
**Root cause:** the public API is a single 512 MB box with two in-flight request slots, no edge/proxy caching, a bcrypt-per-login CPU-exhaustion primitive, and no rate limit — and the heaviest read path scales with ingested row count. Capacity, caching, and abuse-control all converge on the one day traffic peaks.
**Mitigation already in place:** frontend SSE is **disabled** (`SSE_URL` ships empty), so the SSE endpoint is a `curl`-DoS vector but is *not* auto-driven by the UI — do not re-enable it before the async-worker fix lands.
**Combined severity:** **Critical.**
**The one fix that resolves the most:** **HTTP micro-caching on the pollable read endpoints** (collapses N viewers to ~1 origin hit per interval, near-zero cost) **+ move off sync workers** (gthread/gevent) **+ `instance_count: 2`**. Rate-limiting (F-703/F-203) is the security complement and ships alongside it.

### Cluster C — Admin / secret hardening
**Rolls up:** F-202 / F-705 (unauthenticated SSRF + image-bomb in `/api/admin/ocr`) + F-204 (wildcard CORS on all `/api/*`, including admin + auth) + F-206 / F-702 (rotated-but-public bcrypt hashes of "clean alphanumeric" passwords in git history) + F-206 / F-706 (non-constant-time admin-token compare).
**Root cause:** the admin surface is routed directly to Flask on the public internet, and every defense-in-depth control around it (SSRF allow-list, CORS scoping, constant-time compare, credential hygiene) is absent or weak — so the F-201 fail-open, once tripped, is a fully weaponizable chain (drive-by falsification via CORS, internal recon via SSRF, admin takeover via cracked history hashes).
**Combined severity:** **High** (amplifies the Cluster-A Critical).
**The one fix that resolves the most:** **move `/api/admin/*` (and `/api/scrape/*`) off the public route** — reachable only via the authenticated Next.js proxy — which makes F-202/F-705, F-707, and a tripped F-201 unreachable from the internet in one infra change; pair with fail-closed auth, pinned CORS, and `hmac.compare_digest`.

### Cluster D — Repo hygiene / onboarding / no CI signal
**Rolls up:** F-801 (public, authoritative-looking `.claude/state/CONTEXT.md` wrong on every architectural fact) + F-802 / F-107 (dead root monolith `election_dashboard.py` + root Procfile/requirements boot and install the *wrong* app) + F-805 (26 MB committed `.db`) + F-601 / F-604 / F-605 (CI `disabled_manually`; both lint steps structurally broken) + F-904 / F-905 (7× redundant backend builds from the monorepo layout).
**Root cause:** the just-open-sourced repo still carries the pre-refactor monolith, stale docs, and dead data, while CI validates nothing — a public civic project that actively misleads contributors *and* ships every commit unchecked.
**Combined severity:** **High** (contributor-trust + false-green regression risk on an integrity-critical public repo).
**The one fix that resolves the most:** **delete the dead root artifacts** (monolith, root Procfile/requirements, committed `.db`, stale CONTEXT.md) **+ `ruff --fix` + add the Next ESLint config + re-enable CI** — mostly deletions and mechanical fixes that collapse the newcomer ramp from days to ~1 day and restore an automated signal.

### Cluster E — Shared `apcng-db` coupling
**Rolls up:** F-903 (shared production cluster, no CPU/IOPS/connection isolation) + F-409 (no `statement_timeout`, no `pool_recycle`, no pool sizing) + F-313 / F-111 (default 5+10 pool per process on the shared cap → cross-project exhaustion) + F-205 (API keys stored plaintext on the shared cluster).
**Root cause:** the dashboard shares apcng's production Postgres with no compute isolation and no connection budget, so an election-day write burst can take down the sibling app (and vice-versa), and a single cluster breach exposes both products' data.
**Combined severity:** **Critical** (per Cost F-903 — the blast radius is a *second* production outage, not a line item).
**The one fix that resolves the most:** **immediate** — cap the SQLAlchemy pool, set `statement_timeout` + `idle_in_transaction_session_timeout` + `pool_recycle`, and keep `SCRAPER_BURST_FACTOR=1.0` (closes F-409, F-313, F-111, defangs F-903 short-term). **Strategic** — a dedicated smallest-tier cluster before the next major election (~+$15/mo) to remove the coupling entirely.

---

## 3. Top 10 issues ranked by Severity × Likelihood × Ease-to-fix

Scoring: **S**everity (Critical 5 / High 4 / Medium 3 / Low 2). **L**ikelihood of hitting production within ~90 days at current usage (1–5, my judgment). **E**ase-to-fix (effort inverted so quick wins rank up: S=5, M=3, L=2, XL=1). **Score = S × L × E**, higher = do first.

| Rank | Score | F-IDs | Title | S | L | E | Personas | Surface |
|---|---|---|---|---|---|---|---|---|
| 1 | **100** | F-601 (+F-604/F-605) | CI `disabled_manually` + both lint steps broken → zero signal on HEAD | 5 | 4 | 5 | Test/CI, Newcomer | infra |
| 2 | **75** | F-201 / F-701 | Fail-open admin auth (latent — mitigated live, fail-open by default) | 5 | 3 | 5 | Security, Adversary | backend+infra |
| 3 | **75** | F-903 / F-409 / F-313 / F-111 | Shared-DB: no pool caps / no `statement_timeout` → sibling-outage + exhaustion | 5 | 3 | 5 | Cost, Reliability, Perf, Architect | infra |
| 4 | **75** | F-602 | Admin login (`/api/auth/login`) has zero tests | 5 | 3 | 5 | Test/CI | backend |
| 5 | **60** | F-102 / F-404 | No DB unique constraint on votes → silent double-count | 5 | 4 | 3 | Architect, Reliability | backend |
| 6 | **60** | F-302 | 2 sync workers / 1×basic-xxs / no read cache → election-day brownout | 5 | 4 | 3 | Performance, Architect | infra |
| 7 | **60** | F-703 / F-203 | No inbound rate limiting → trivial DoS + login brute force | 5 | 4 | 3 | Adversary, Security | backend |
| 8 | **60** | F-402 | Healthcheck lies → stale-as-live scraper undetected, no alert | 5 | 4 | 3 | Reliability | backend+infra |
| 9 | **60** | F-902 | `SCRAPER_BURST_FACTOR=5.0` committed → 24k IReV calls/day → INEC IP-ban risk | 4 | 3 | 5 | Cost | infra |
| 10 | **60** | F-305 (+F-106) | Missing indexes on `election_results`; `lazy="selectin"` eager-load cascade | 4 | 3 | 5 | Performance, Architect | backend |

**Formula caveat — three Critical result-integrity findings the ease-adjustment under-ranks (do NOT defer them):**
- **F-101** (mixed-grain double-count, S5 × L4 × E2 = **40**) — *live-today* for FCT 2026 (simultaneously PU-scraped and hand-entered). Ranks #11 only because the full grain redesign is L-effort. **Sprint-1 mandatory** (stopgap: filter reads to the canonical grain + partial unique index).
- **F-501** (provisional indistinguishable from certified, S5 × L4 × E2 = **40**) — one journalist screenshot away from a disinformation incident. **Sprint-1/2 mandatory.**
- **F-403** (poison-pill tick wedges the scraper silently, S5 × L3 × E2 = **30**) — the archetypal 3 AM page that never pages. **Sprint-2 mandatory.**

---

## 4. Four-sprint remediation roadmap

Small team assumption (1–3 engineers), two-week sprints, ~20% capacity reserved for unknowns. Owners: **BE** = backend eng, **FE** = frontend eng, **Infra** = DevOps/infra.

### Sprint 1 — Stop the bleeding before the next live election
*Theme: integrity backstop + fail-closed admin + rate limiting + capacity + restore a CI signal.*
- **F-102 / F-404** — partial unique constraint on the vote natural key + upsert-on-conflict + dedupe backfill (BE, M)
- **F-101 (stopgap)** — filter every analysis read to the election's canonical grain + partial unique index blocking mixed grains for one `election_id`; begin the full redesign (BE, L — spills into Sprint 2)
- **F-201 / F-701** — fail *closed*, assert `ADMIN_TOKEN` at startup in production, add it as a committed `SECRET` on the `web` service (BE + Infra, S)
- **F-703 / F-203** — `flask-limiter` on `/api/auth/login` + `/api/developer/apply`, looser caps on public reads (BE, M)
- **F-302** — `Cache-Control: s-maxage` micro-caching on pollable read endpoints + `instance_count: 2` for web/frontend; move to gthread/gevent workers (Infra + BE, M)
- **F-301** — replace Python-side row hydration in `standings` / `_votes_by_party` / `_stats` with SQL `GROUP BY` (BE, M)
- **F-402** — semantic healthcheck (503/`degraded` when `now − scraper_last_run` exceeds a mode-aware threshold) + external uptime/staleness probe + alert (BE + Infra, M)
- **F-601 / F-604 / F-605** — `ruff --fix`, add `frontend/.eslintrc.json`, re-enable CI, confirm one green run (BE + FE, S)
- **F-903 / F-409 / F-313 / F-111** — cap pool, set `statement_timeout` + `pool_recycle` (BE, S)
- **F-902** — revert `SCRAPER_BURST_FACTOR` to `1.0` (Infra, S)
- Fold in the quick-win deletions (§5) in the first days.

### Sprint 2 — Integrity depth + election-day resilience
*Theme: finish the crown jewel, make the scraper honest, gate the pipeline.*
- **F-101 (full)** — single-source-of-truth grain model (`result_grain` per election + derived views) (BE, L)
- **F-501 (+F-502)** — result-status model (Certified / Provisional / Live-counting), un-mistakable visual treatment, "% of PUs reporting" + real "as of" timestamp across map, panel, and standings (FE + BE, L)
- **F-403 / F-405** — per-election transactions/savepoints + out-of-band audit-log session so failure records survive the rollback + dead-letter after N failures (BE, L)
- **F-406 / F-105 / F-304 / F-309** — decide the MV contract: refresh in the daemon on a cadence + after admin writes, point turnout/competitiveness at their MVs, debounce refresh, distinguish "not populated" from "refresh failed" (BE, M)
- **F-602 / F-603 / F-607** — auth-login tests, result-integrity validator tests, extract the certified-total assertions into a pre-merge integration test (BE, M)
- **F-606** — branch protection / required checks on `main` once green (Infra, S)

### Sprint 3 — Scale-out + observability + admin hardening
*Theme: remove the throughput ceiling and the recon surface.*
- **F-104** — claim-based work distribution (`FOR UPDATE SKIP LOCKED` / per-state lease) so the scraper can shard (BE, L)
- **F-303 / F-304** — kill the N+1 fan-out; serve analytics margins from MVs (BE, M)
- **F-202 / F-705** — SSRF allow-list + private-IP block + redirect/size caps + generic errors on `/api/admin/ocr`; move `/api/admin/*` + `/api/scrape/*` off the public route (BE + Infra, M)
- **F-204 / F-206 / F-702 / F-205 / F-706** — pin CORS; verify password rotation durably deployed + strong policy + MFA/IP-allowlist on `/admin`; hash API keys at rest; constant-time token compare (BE, M)
- **F-413 / F-414 / F-415 / F-410** — structured logging + Sentry + RED metrics; `scrape_log` retention; per-tick deadline + IReV circuit breaker; pass the caller session into `_maybe_cache` (BE, M)
- **F-608 / F-609 / F-610 / F-611** — scraper token-bucket/retry, `resolve_party`, gate negative-branch, and frontend admin-gate tests (BE + FE, M)

### Sprint 4 — Polish, accessibility, docs, cost
*Theme: make it usable by everyone and cheap to run.*
- **F-503 / F-504 / F-506 / F-507 / F-508 / F-510 / F-511** — accessibility: keyboard/SR map equivalents, `aria-live` on the live surface, colorblind-safe party encoding, AA contrast on `--text-dim`, reduced-motion guard, form labels (FE, L)
- **F-505 / F-513** — wire the existing skeletons + render `error` on every async view (FE, M)
- **F-509** — strip internal jargon / CLI snippets / raw `state_id` from public views (FE, M)
- **F-801 / F-802 / F-805 / F-107** — delete stale CONTEXT.md, dead monolith, committed `.db`, fix the Procfile (Infra, S — pull earlier as quick wins)
- **F-803 / F-804 / F-806 / F-809 / F-810 / F-811** — README quick-start (`seed_historical`, DB name, `/admin` env chain), `DECISIONS.md`/`ARCHITECTURE.md` + community-health files, pin Python version, delete orphan `/messaging` (Infra + FE, S–M)
- **F-901 / F-904 / F-905** — delete the Caddy droplet (native App Platform TLS); build the backend image once via DOCR + collapse the 4 seed jobs into 1 (Infra, S–M)
- Remaining Low items: F-514, F-515, F-516, F-517, F-518, F-108, F-109, F-110, F-112.

---

## 5. Quick wins (< 1 day each)

Ship these before or in the first days of Sprint 1 — pure deletions and mechanical fixes that buy goodwill and free capacity. Several are *also* Sprint-1 Criticals (marked ★) — they are both quick and load-bearing.

- **Delete the dead root monolith** `election_dashboard.py` + root `Procfile` + root `requirements.txt` (F-802, F-107)
- **Untrack the 26 MB `election_data.db`**, add `*.db` to `.gitignore` (F-805)
- **Delete / replace the stale `.claude/state/CONTEXT.md`** with a "superseded — see README" pointer (F-801)
- **`ruff check --fix`** clears the 84 lint violations; **add `frontend/.eslintrc.json`** (`{ "extends": "next/core-web-vitals" }`); **re-enable CI** (F-604, F-605, F-601)
- ★ **Add the DB unique-constraint migration** on the vote natural key (F-102) — the single highest-value one-migration change
- **Add the two missing indexes** `ix_results_election_lga_party` + `ix_results_party` (`CONCURRENTLY`) (F-305)
- ★ **Fail-closed `_require_admin`** + startup assertion + `ADMIN_TOKEN` as a committed SECRET (F-201/F-701)
- **`hmac.compare_digest`** for the admin token (F-706); **pin `CORS_ORIGINS`** to the canonical origin (F-204)
- **Revert `SCRAPER_BURST_FACTOR` to `1.0`** in the committed spec (F-902)
- **Set `pool_size`/`max_overflow`/`pool_recycle` + `statement_timeout`** in `db.py` (F-409/F-313/F-111)
- **Default the geography relationships to `lazy="raise"`**, opt into `selectinload()` explicitly (F-106)
- **Delete the Caddy droplet**, point the domain at App Platform native TLS (F-901)
- **Delete the orphan `/messaging` route** + fix the stale `NAV_ITEMS` `/messaging` entry (F-811, F-514)
- **Align `runtime.txt` to Python 3.11** (F-810); **add `seed_historical` + fix the DB name** in the README quick-start (F-803, F-804)
- **`useReducedMotion` guard** on `AnimatedCounter` (F-510); **add `<label>`s** to the api-access form (F-511)

---

## 6. Strategic refactors (dedicated investment)

| Refactor | F-IDs | Cost now | Cost in 6 months | Trigger to do it now |
|---|---|---|---|---|
| **Aggregation-grain redesign** — single-source-of-truth grain + derived views | F-101, F-109 | ~1 sprint | Corrupted public totals shipped in production + a dedupe/backfill of poisoned rows + reputational damage | **Already tripped** — FCT 2026 runs PU-scrape + admin-entry on the same election today |
| **Async worker model + capacity** — gevent/gthread or ASGI SSE sidecar, read caching/CDN, `SKIP LOCKED` scraper sharding | F-103/F-401, F-302, F-104, F-303 | ~1 sprint | An election-day brownout on live national TV | The next scheduled live governorship/presidential election inside the capacity window |
| **Dedicated DB cluster** — move off shared `apcng-db` | F-903 | +$15/mo + a migration | A two-for-one outage: election-day write burst takes down apcng (or apcng load blinds the dashboard) | Before the next major election, or when apcng's own load grows — whichever first |
| **Result-status / provenance model end-to-end** — schema → API → UI Certified/Provisional/Live labeling | F-501, F-502 | ~1 sprint | A screenshot of an in-progress count broadcast as an "official" called result | Before any live election is served to the public |

---

## 7. Board / stakeholder risks (civic-data credibility)

Expressed in business terms — the four things that can end this project's credibility, in priority order.

1. **Result integrity has no automated backstop.** The dashboard can publish an arithmetically wrong winner *today* — the flagship FCT 2026 election is simultaneously machine-scraped and hand-entered, and the two are summed together with no schema, no test, and no UI label to stop the double-count — and it renders a 2%-reporting provisional count identically to a certified final. For a platform whose entire value is "the numbers are right," a single wrong or misread number circulating as "official" is a reputational incident that outlives any code fix. This is the existential risk.
2. **The dashboard goes dark exactly when it matters.** The public API is a single 512 MB box with two in-flight request slots, no rate limiting, and no read caching. A few hundred concurrent viewers — or a trivial flood any script kiddie can run — takes it offline on election night. This is an availability/credibility risk, and notably it is *not* a cost problem: the entire bill is ~$23–25/month.
3. **The admin write-path is one misconfiguration from unauthenticated result falsification.** It is protected *right now* by a live secret, but the code fails open by default and the committed infrastructure spec omits the secret, so any redeploy from that spec re-opens it. Combined with public routing, wildcard CORS, and crackable password hashes still in public git history, this is the finding that would fail a security due-diligence review of a civic-data platform.
4. **No CI gate and a misleading public repo.** CI has been disabled since May and every commit since ships unvalidated; the just-open-sourced repo boots a dead monolith, ships a stale doc that is wrong on every architectural fact, and carries rotated-but-public password hashes. For an OSS project actively soliciting contributors ("PRs Welcome"), this undercuts both contributor trust and the "we validate our results code" claim.

---

## 8. What we will NOT fix (accept + document rationale)

The most important section — these are conscious risk acceptances, each with a trigger that would reverse it.

1. **API-gate `Sec-Fetch-Site` / `Origin` / `Referer` bypass — ACCEPT (F-704 down-rated to Low, F-207 Low is correct).** The gate's own docstring calls it "an access-management signal, not a security boundary"; everything behind it is free public election data; and `/api/admin` + `/api/auth` + `/api/developer` are gate-exempt anyway — so the bypass grants nothing beyond what is already free, losing only attribution/metering. **Do not spend a security sprint on this.** *Trigger to revisit:* the moment any rate-limiting, quota, or billing is layered on the gate, the bypass becomes material and must be closed then (server-injected internal header, not spoofable fetch metadata).
2. **Always-on scraper worker (F-907) — ACCEPT.** $5/mo for a worker that idles most of the year is the correct trade for 120 s live-tick responsiveness on election day; scale-to-zero alternatives (GHA cron, DO Functions) have a 5-minute floor and cold-starts that break live mode. *Trigger:* only revisit if elections become genuinely rare *and* cost pressure rises.
3. **Frontend as a Node service, not a static export (F-908) — ACCEPT.** NextAuth server routes + the admin-token proxy + `async rewrites()` make `output: 'export'` impossible, and it is already at the floor tier. Documenting this prevents a future "just make it static to save $5" change that would silently break login and the admin surface. *Trigger:* none worth acting on short of a full Cloudflare Pages re-platform at real scale.
4. **English-only / no i18n (F-517) — ACCEPT for now.** Defensible for a Nigerian civic product — English is the official lingua franca and `<html lang="en">` is set. *Trigger:* if Hausa/Yoruba/Igbo support goes on the roadmap, externalize strings *then* — flagged because the retrofit cost grows the longer strings stay scattered inline.
5. **Git-history bcrypt-hash scrub (F-206/F-702) — PARTIAL accept.** Treat the historical hashes as permanently disclosed; the load-bearing fixes are confirming the current admin password is strong/unique/unrelated to any historical value and rate-limiting the login (Sprint 1). A BFG history rewrite + force-push of public history is *optional* (it only removes the pattern signal) and is accepted as **not done** as long as rotation is verified. *Trigger:* any suspicion of password reuse.

---

## Executive summary for an investor email

The Nigeria Election Dashboard is architecturally sound and cheap to run (~$23–25/month), with a clean service split, disciplined migrations, and genuinely well-tested analytics math — but it is not yet safe to trust for a live election. A nine-lens audit found 108 issues (18 Critical, 28 High); the Criticals collapse to five root causes, and one dominates: the vote table has no integrity backstop at any layer, so the public map can double-count votes and show an in-progress count as a certified result, with no schema constraint, no test, and no UI label stopping it. Production is up and not breached — the admin write-path is protected by a live secret today — but it fails open by default, the single 512 MB serving box has no rate limiting or caching (an election-day brownout risk), and CI has been disabled since May so nothing is validating the code that ships. The four-sprint plan front-loads the survival items: Sprint 1 stops the bleeding (vote-table constraint, fail-closed admin, rate limiting, capacity, restored CI); Sprint 2 completes the integrity model and provenance labeling; Sprints 3–4 handle scale-out, observability, accessibility, and repo hygiene. We are consciously *not* fixing four things and have documented why with reversal triggers: the free-API gate's header "bypass" (it only gates already-free data), the always-on scraper, the non-static frontend, and English-only UI. The bones are good; the next four sprints are about making the published numbers trustworthy before the country is watching.
