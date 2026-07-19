# Audit — Persona 08: The Newcomer ("I started Monday")

**Auditor lens:** senior engineer, day 1, no tribal knowledge, onboarding to an
open-source repo that is actively soliciting outside contributors ("PRs Welcome"
badge, CONTRIBUTING.md, public API-by-application). Read-only. Findings only.

## Executive summary

**Time-to-first-successful-run estimate:**
- Backend process *starts*: **~30–45 min** (Docker + Postgres + venv + migrate + seed), assuming the reader follows the README quick-start *exactly* and does not consult `.env.example`.
- Backend starts **with data actually visible on the dashboard**: **~2–4 hours.** The quick-start seeds states/parties/calendar but never runs `seed_historical`, so every results view, choropleth, and `/analysis/*` endpoint comes back empty. A competent newcomer will assume they broke something, re-run migrations, diff configs, and eventually spelunk `.do/app.yaml` to discover the missing seed step. That detour is the single biggest time sink.
- Full local parity including `/admin` login: **~half a day** (undocumented NextAuth + admin-token + seeded-user chain).

**Biggest blockers (one line each):**
1. **Quick-start boots an empty dashboard** — `python -m app.seed` loads no election results; the results seed (`app.importer.loaders.seed_historical`) is omitted from the quick-start entirely (F-803).
2. **A committed, authoritative-looking `.claude/state/CONTEXT.md` is wrong on every fact** — tells the newcomer the backend is a single 2441-line SQLite file with no auth on region `nyc`/PG15, and points them at a "secret" on line 39 of the legacy file (F-801).
3. **The repo root looks like the app but is the dead monolith** — `election_dashboard.py` + root `requirements.txt` + root `Procfile` + 26MB `election_data.db`, all git-tracked, all boot/install the retired pre-refactor app (F-802).

**Onboarding verdict** (full detail at the end): realistic productive-newcomer ramp is **4–6 working days**, and the rate-limiting step is not the code — it is untangling which of the two apps in the repo is real and why the dashboard is empty after a by-the-book setup.

## Severity table

| ID | Severity | Title | Surface |
|---|---|---|---|
| F-801 | Critical | Committed `.claude/state/CONTEXT.md` misleads on every architectural fact | shared |
| F-802 | Critical | Dead monolith at repo root installs/boots the wrong app | shared |
| F-803 | High | Quick-start omits `seed_historical` → dashboard boots with zero results | backend |
| F-804 | High | `DATABASE_URL` database-name contradicts across README / `.env.example` / config default | shared |
| F-805 | Medium | 26 MB legacy `election_data.db` committed — clone bloat + "which DB is real?" confusion | shared |
| F-806 | Medium | Local `/admin` login path is undocumented (secret + token + seeded user all unstated) | web |
| F-807 | Medium | The "same-origin" gate is tribal knowledge; split-port local dev only works because enforcement defaults off | backend |
| F-808 | Medium | CI `e2e` job on `main` probes a live DO deploy — likely the RED main a newcomer can't reproduce or interpret | infra |
| F-809 | Medium | No architecture/DECISIONS doc; no CODE_OF_CONDUCT / issue / PR templates for a repo waving "PRs Welcome" | shared |
| F-810 | Low | `backend/runtime.txt` pins Python 3.12.7 while README / CI / pyproject say 3.11 | backend |
| F-811 | Low | Orphan `/messaging` route and no route map/glossary of pages | web |

---

## Findings

### F-801: Committed `.claude/state/CONTEXT.md` misleads a newcomer on every architectural fact
- **Severity**: Critical
- **Persona**: Newcomer
- **Surface**: shared
- **Files**: `.claude/state/CONTEXT.md:6-8,13,19,40-41,46`
- **Problem**: This file is git-tracked (`.gitignore:26-27` explicitly force-keeps `.claude/state/**`), so it ships in the public OSS repo. It is titled "CONTEXT — current state, gotchas, recent findings," which reads as the canonical orientation doc — exactly what a new contributor opens first. Every load-bearing claim in it is now false: "Backend: single file `election_dashboard.py` (2441 lines), Flask + SQLite + background scraper thread" (`:6-8`), "No auth on any endpoint" (`:41`), "region `nyc` … managed PG15" (`:46`), and — worst — line 13 instructs the reader that the IReV key lives "in legacy file at line 39" and should be moved to an env var, sending a newcomer hunting for a "secret" inside the dead monolith. The current reality (per `00-brief.md` and the code) is a Flask app-factory, SQLAlchemy 2 + Postgres 16, NextAuth-gated `/admin`, region `fra`. Nothing warns the reader the file is stale.
- **Impact**: A newcomer who trusts this file builds a completely wrong mental model, wastes hours reconciling it against the code, and may act on the "find the key on line 39" instruction. High blast radius because it is the most authoritative-sounding doc in the repo and it is public.
- **Repro / Evidence**: `git ls-files .claude/state/CONTEXT.md` → tracked. `CONTEXT.md:6` "single file `election_dashboard.py` (2441 lines) … SQLite"; `:46` "region `nyc` … PG15 dev tier"; `:41` "No auth on any endpoint." All contradicted by `backend/app/__init__.py`, `.do/app.yaml:2` (`region: fra`) / `:113` (`version: "16"`), and `backend/app/api/auth.py`.
- **Recommended fix**: Either stop tracking `.claude/state/` in the public repo (drop the `!.claude/state/**` un-ignore) or replace CONTEXT.md's body with a one-line "superseded — see README/00-brief" pointer. A newcomer-facing repo should not ship an internal scratch file that pre-dates the refactor.
- **Effort**: S
- **Tags**: docs, contradictory-docs, quick-win, oss-hygiene

### F-802: Dead monolith at the repo root makes the most-visible "app" the wrong one
- **Severity**: Critical
- **Persona**: Newcomer
- **Surface**: shared
- **Files**: `election_dashboard.py:1` (94 KB), `requirements.txt:1-7` (root), `Procfile:1` (root), `election_data.db` (root, 26 MB) — all git-tracked
- **Problem**: The repo root — the first thing a newcomer sees — contains a complete, runnable-looking legacy Flask app that is retired. `Procfile:1` is `web: gunicorn election_dashboard:app …`, i.e. any PaaS or `foreman`/`honcho` run from the root boots the *dead* monolith, not `backend/app.wsgi`. The root `requirements.txt` pins only 7 deps (flask, flask-cors, requests, openpyxl, gunicorn, Pillow, numpy) — no SQLAlchemy, Alembic, Pydantic, or bcrypt — so the reflexive `pip install -r requirements.txt` from the repo root installs the wrong, incomplete dependency set and the real backend won't import. The real entrypoints live one level down in `backend/` with their own `backend/Procfile` and `backend/requirements.txt`. Two Procfiles, two requirements files, two apps, and the *dead* copy is the one at the top.
- **Impact**: A newcomer following instinct (`pip install -r requirements.txt`, `foreman start`, "run the Procfile") boots or installs the legacy FCT-only SQLite app and gets an experience that matches neither the README nor production. Very high onboarding blast radius; also an OSS credibility problem (a public repo that appears to be a single 2400-line script).
- **Repro / Evidence**: `git ls-files` lists `election_dashboard.py`, `election_data.db`, `Procfile`, `requirements.txt` at root. Root `Procfile:1` → `election_dashboard:app`; `backend/Procfile:1` → `app.wsgi:app`. Root `requirements.txt` has no `SQLAlchemy`/`alembic`; `backend/requirements.txt:4-6` does.
- **Recommended fix**: Delete the legacy root artifacts (`election_dashboard.py`, root `Procfile`, root `requirements.txt`, `FCT_2026_Area_Council_Elections.xlsx`, and the SQLite DB — see F-805) once parity is confirmed, or move them under an explicitly labelled `legacy/` directory with a README stub. One app per repo root.
- **Effort**: S
- **Tags**: dead-code, discoverability, oss-hygiene, ask-the-team

### F-803: README quick-start omits the results seed, so the dashboard boots empty
- **Severity**: High
- **Persona**: Newcomer
- **Surface**: backend
- **Files**: `README.md:82-84` (quick-start), `backend/app/seed.py:1-4`, `backend/app/importer/loaders/seed_historical.py:1-8`, `.do/app.yaml:164-175`
- **Problem**: The quick-start runs `alembic upgrade head` then `python -m app.seed` then gunicorn. But `app/seed.py:3` only "Inserts states, default parties, and known election calendar entries" — no results. The actual election data is loaded by a *separate* module, `app.importer.loaders.seed_historical`, which the quick-start never mentions; it only appears in production as a POST_DEPLOY job (`.do/app.yaml:164-175`). A newcomer who completes the quick-start gets a running app whose every results table, choropleth, and `/api/analysis/*` endpoint is empty, with nothing in the README explaining why or what to run next.
- **Impact**: The default, documented happy path produces a dashboard that looks broken. The newcomer cannot tell whether they misconfigured something or the app is buggy, and will burn hours before finding the missing seed command in `app.yaml`. This is the top time-sink in the ramp.
- **Repro / Evidence**: Follow `README.md:72-90` verbatim → app starts → open any results view → empty. `grep -rn "seed_historical" README.md` returns only `README.md:141` (the *importer* section, a different manual-load context), never the quick-start.
- **Recommended fix**: Add `python -m app.importer.loaders.seed_historical` (and note the optional `flask auth create-user` for `/admin`) to the quick-start immediately after `python -m app.seed`, with a one-line "this loads the bundled 2015–2026 results" caption.
- **Effort**: S
- **Tags**: docs, onboarding-blocking, quick-win

### F-804: `DATABASE_URL` database name contradicts across README, `.env.example`, and the config default
- **Severity**: High
- **Persona**: Newcomer
- **Surface**: shared
- **Files**: `README.md:79-80`, `backend/.env.example:4`, `backend/app/config.py:39-42`
- **Problem**: The README quick-start boots `postgres:15` (whose only database is `postgres`) and exports `DATABASE_URL=…localhost:5432/postgres` (`README.md:79-80`). But `backend/.env.example:4` and the `config.py:41` default both use `…localhost:5432/elections` (database `elections`). The two documents the README itself points a newcomer to (`README.md:92` "Env-var reference: backend/.env.example") disagree on the database name. A reader who mixes them — uses the README's `postgres:15` container but relies on `.env.example`/the config default — hits `alembic upgrade head` failing with `database "elections" does not exist`, an opaque error with no breadcrumb. Secondary mismatch: README uses PG **15**, production/`.do/app.yaml:113` uses PG **16**.
- **Impact**: A newcomer who trusts the referenced env file over the inline quick-start gets a hard migration failure on step one. Even the reader who follows the README exactly is left with two conflicting "sources of truth" for the DB name.
- **Repro / Evidence**: `README.md:79` `docker run … postgres:15` (default DB `postgres`) vs `backend/.env.example:4` `…/elections` vs `config.py:41` `…/elections`.
- **Recommended fix**: Pick one database name across all three (e.g. `elections`), and make the README's `docker run` create it (`-e POSTGRES_DB=elections`). Align the Postgres major version with production (16).
- **Effort**: S
- **Tags**: docs, contradictory-docs, setup-fails

### F-805: 26 MB legacy `election_data.db` is committed — clone bloat and "which DB is real?" confusion
- **Severity**: Medium
- **Persona**: Newcomer
- **Surface**: shared
- **Files**: `election_data.db` (root, 26 MB, git-tracked), `.gitignore:12-15`
- **Problem**: A 26 MB SQLite database sits at the repo root and is tracked in git, yet the live app uses managed Postgres and this file is the retired FCT-only snapshot (per the stale CONTEXT.md that references it as a parity fixture). `.gitignore:13-14` ignores `*.db-shm`/`*.db-wal` but *not* `*.db`, so the main DB file is intentionally committed. A newcomer sees a checked-in `.db` and reasonably assumes it is the app's datastore, contradicting the Postgres story in the README and multiplying the "there are two apps here" confusion from F-802.
- **Impact**: Every clone pulls 26 MB of dead data; the file's presence directly undercuts the "backend is Postgres" mental model. Not a hard blocker, but it compounds discoverability debt.
- **Repro / Evidence**: `git ls-files election_data.db` → tracked; `du -h election_data.db` → 26M. README architecture (`README.md:66-68`) says Postgres; no README line explains the SQLite file.
- **Recommended fix**: Remove `election_data.db` from tracking (add `*.db` to `.gitignore`) once any parity use is retired; if it must stay as a fixture, move it under `backend/tests/fixtures/` with a caption. Bundle only the CSV seeds under `backend/data/historical/`.
- **Effort**: S
- **Tags**: repo-bloat, dead-data, oss-hygiene

### F-806: Local `/admin` login is undocumented — secret, token, and seeded user are all unstated
- **Severity**: Medium
- **Persona**: Newcomer
- **Surface**: web
- **Files**: `README.md:87-89` (frontend quick-start), `frontend/.env.example:10,14`, `README.md:96-108` (admin-users section)
- **Problem**: The frontend quick-start (`README.md:89`) launches with only `NEXT_PUBLIC_API_URL` set. But `frontend/.env.example` shows four more moving parts required to exercise `/admin`: `API_URL` (server-side, `:6`), `NEXTAUTH_URL` (`:8`), `NEXTAUTH_SECRET` (`:10`, empty), and `ADMIN_TOKEN` (`:14`, must match the backend's). None of these appear in the quick-start, and the README's "Admin users" block (`:96-108`) covers creating a *user* but not the NextAuth env wiring needed for the login page to function locally. A newcomer wanting to test the ingestion admin (the one gated feature) has to reverse-engineer the NextAuth ↔ Flask ↔ admin-proxy chain from `.env.example` and `frontend/src/lib/auth.ts`.
- **Impact**: The only login-gated surface — the entire reason auth exists in this project — cannot be run locally by following the docs. Contributors touching `/admin` are blocked until they piece together four env vars and a seeded user.
- **Repro / Evidence**: `README.md:87-89` sets one var; `frontend/.env.example:6-14` lists four more marked required/empty. No quick-start step ties them together.
- **Recommended fix**: Add an "Optional: run /admin locally" block to the quick-start listing the four env vars (with `openssl rand -base64 32` for the secret, already shown at `frontend/.env.example:9`), the `flask auth create-user` step, and the note that `ADMIN_TOKEN` must match backend.
- **Effort**: S
- **Tags**: docs, auth, onboarding

### F-807: The "same-origin" API gate is tribal knowledge; split-port local dev only works because enforcement defaults off
- **Severity**: Medium
- **Persona**: Newcomer
- **Surface**: backend
- **Files**: `backend/app/api_gate.py:39-44,86-87`, `backend/app/config.py:61-63`, `backend/.env.example:28-31`
- **Problem**: `_is_same_origin()` (`api_gate.py:39-44`) passes dashboard traffic only when `Sec-Fetch-Site: same-origin` OR the Origin/Referer host equals the request host. In local dev the browser page is `localhost:3000` and the API is `localhost:8080` — different port, so neither condition holds. Local dev nonetheless works *only* because `api_key_enforcement` defaults off when `ENV != production` (`config.py:61-63`), which lets the gate fall through at `api_gate.py:86-87`. This coupling is documented nowhere a newcomer would look. The moment a contributor sets `ENV=production` or `API_KEY_ENFORCEMENT=true` locally to test prod-like behavior, the dashboard's own data calls start returning 401 "API key required," with no hint that the cause is the port-based same-origin check.
- **Impact**: A newcomer debugging "why is my local dashboard suddenly 401-ing its own requests?" has no documentation trail; the answer lives in the interaction between two files. Least-surprise violation.
- **Repro / Evidence**: Set `API_KEY_ENFORCEMENT=true` locally with the split-port README setup → dashboard fetches from `:3000`→`:8080` are cross-origin → `api_gate.py:44` returns false → 401 at `:89-100`.
- **Recommended fix**: Document the gate's local behavior in `backend/.env.example` near `API_KEY_ENFORCEMENT` (`:28-31`) — "same-origin pass is host:port based; keep enforcement off for split-port local dev, or run frontend and API behind one origin." Consider treating `localhost`/`127.0.0.1` as same-origin regardless of port in non-production.
- **Effort**: S
- **Tags**: tribal-knowledge, auth, least-surprise

### F-808: CI `e2e` job on `main` probes a live DO deployment — likely the RED main a newcomer can't reproduce
- **Severity**: Medium
- **Persona**: Newcomer
- **Surface**: infra
- **Files**: `.github/workflows/ci.yml` (`e2e` job), `backend/tools/e2e.py`
- **Problem**: The `e2e` job runs on push to `main`, sleeps 360s "for DO deploy to roll out," then runs `python3 backend/tools/e2e.py` against a hardcoded live URL `E2E_URL: https://ng-election-dashboard-lkxwq.ondigitalocean.app`. This couples the green/red state of `main` to a running production-ish deployment plus its POST_DEPLOY seed jobs — external state a contributor cannot influence or reproduce. The README's CI badge points at this workflow. A newcomer who sees a red `main` badge (the brief notes pre-existing RED CI on main) has no way to tell whether `main` is broken, whether their PR is affected (PRs skip `e2e`), or whether red-on-main is simply the expected steady state.
- **Impact**: A red default-branch badge on an OSS project reads as "this project is broken," discouraging contribution, and the newcomer cannot diagnose it locally. Erodes trust in CI as a signal.
- **Repro / Evidence**: `ci.yml` `e2e` job: `if: github.event_name == 'push' && github.ref == 'refs/heads/main'`, `run: sleep 360`, `E2E_URL: https://ng-election-dashboard-lkxwq.ondigitalocean.app`. PR jobs are `backend` + `frontend` only.
- **Recommended fix**: Document in CONTRIBUTING that `e2e` is a post-deploy smoke test against live infra and is expected to be independent of PR review; gate the README badge to the PR-relevant jobs, or make `e2e` non-blocking / clearly labelled "deploy smoke, not PR gate."
- **Effort**: M
- **Tags**: ci, docs, contributor-trust, ask-the-team

### F-809: No architecture/DECISIONS doc and no community health files for a repo inviting contributors
- **Severity**: Medium
- **Persona**: Newcomer
- **Surface**: shared
- **Files**: absent: no `ARCHITECTURE.md`, no `DECISIONS.md`, no `CODE_OF_CONDUCT.md`, no `.github/ISSUE_TEMPLATE/`, no `.github/PULL_REQUEST_TEMPLATE.md` (only `.github/workflows/ci.yml` exists)
- **Problem**: The README carries a "PRs Welcome" badge and a CONTRIBUTING.md, but the repo lacks the standard scaffolding a newcomer relies on: no CODE_OF_CONDUCT (a GitHub community-standards expectation for OSS), no issue or PR templates to shape contributions, and no design-decision record explaining *why* the notable choices were made (why Postgres over the original SQLite, why the free-API-by-application gate, why the shared `apcng-db` cluster, why `SEED_USERS` is env-driven rather than a fixture). The only architecture artifact is the ASCII diagram at `README.md:56-64`, which is helpful but shallow. The "why" knowledge currently lives only in the stale CONTEXT.md (F-801) and code comments.
- **Impact**: Contributors re-litigate settled decisions, file malformed issues, and cannot find rationale — the classic "ask the original team about everything" tax. Compounds over every new contributor.
- **Repro / Evidence**: `find .github -type f` → only `workflows/ci.yml`. No `DECISIONS.md`/`ARCHITECTURE.md` at any level.
- **Recommended fix**: Add a short `DECISIONS.md` (or `docs/architecture.md`) capturing the 5–6 non-obvious choices, a `CODE_OF_CONDUCT.md` (Contributor Covenant), and minimal issue/PR templates. Fold the still-true "gotchas" from CONTEXT.md into DECISIONS.md before deleting it (F-801).
- **Effort**: M
- **Tags**: docs, oss-hygiene, decisions

### F-810: `runtime.txt` pins Python 3.12.7 while README, CI, and pyproject all say 3.11
- **Severity**: Low
- **Persona**: Newcomer
- **Surface**: backend
- **Files**: `backend/runtime.txt:1`, `backend/pyproject.toml` (`requires-python = ">=3.11"`, `target-version = "py311"`), `.github/workflows/ci.yml` (`python-version: "3.11"`), `README.md:66`
- **Problem**: `backend/runtime.txt:1` declares `python-3.12.7`, but every other signal says 3.11: the README architecture line, `pyproject.toml`'s `requires-python`/ruff/mypy target, and CI's setup-python matrix. A newcomer deciding which interpreter to create their venv with gets conflicting answers, and CI (3.11) may accept syntax the local 3.12 rejects or vice-versa.
- **Impact**: Minor — most 3.11/3.12 code is compatible — but it is a "which version do I install?" stumble on day one and a latent CI-vs-local drift.
- **Repro / Evidence**: `cat backend/runtime.txt` → `python-3.12.7`; `ci.yml` → `python-version: "3.11"`; `pyproject.toml` → `target-version = "py311"`.
- **Recommended fix**: Pin one version. Align `runtime.txt` to 3.11 (matching CI and the mypy/ruff target), or bump CI + pyproject to 3.12 if 3.12 is intended.
- **Effort**: S
- **Tags**: config-drift, quick-win

### F-811: Orphan `/messaging` route and no map of what each page does
- **Severity**: Low
- **Persona**: Newcomer
- **Surface**: web
- **Files**: `frontend/src/app/messaging/page.tsx:1-22`
- **Problem**: `frontend/src/app/` has 14 route folders (`page.tsx`/`route.ts`), one of which — `/messaging` — renders only a tombstone ("Polling-agent SMS/WhatsApp flows are not part of the pan-Nigeria backbone. The legacy FCT-specific surface has been retired."). It is not linked from any nav (`grep messaging frontend/src/components` → nothing) and not mentioned in the README. A newcomer enumerating routes finds a page whose existence has no explanation except that it used to be something. More broadly, there is no route/page glossary, so the newcomer must open all 14 folders to learn what `insights` vs `analytics` vs `dashboard` vs `overview` (the root `page.tsx`) each are.
- **Impact**: Low — a self-explaining tombstone is harmless — but it is dead-weight surface area and a symptom of the missing "what are the pages?" map, which slows frontend orientation.
- **Repro / Evidence**: `frontend/src/app/messaging/page.tsx:9-12` (retirement text); route present but absent from nav and README.
- **Recommended fix**: Delete the retired `/messaging` route (or keep it only if an inbound link still exists), and add a short "Pages" table to the README or a `frontend/README.md` mapping each route to its purpose.
- **Effort**: S
- **Tags**: dead-code, discoverability

---

## Persona-required extras

### Top 3 things I would document FIRST if I owned this codebase
1. **The full "clone → data on screen" runbook** — fix the quick-start so it includes `seed_historical` (F-803), one database name (F-804), and the optional `/admin` env chain (F-806). This alone cuts the ramp from hours to minutes.
2. **A DECISIONS.md capturing the "why"** — Postgres-over-SQLite, the free-API-by-application gate and its same-origin pass (F-807), the shared `apcng-db` binding, `SEED_USERS`-is-env-driven, the Caddy proxy droplet, and `deploy_on_push` + repo-rename caveats. These are the exact questions a newcomer would otherwise DM the author about (F-809).
3. **A "this file is dead" boundary** — delete or fence off the root monolith (F-802), the committed SQLite DB (F-805), and the stale CONTEXT.md (F-801), so nothing in the repo contradicts the README.

### Top 3 things I would rename for consistency
1. **The product's own name.** It appears as "Nigeria Election Dashboard" (`README.md:3`), `ng-election-dashboard` (`pyproject.toml`, `.do/app.yaml:1`, DO URL `ng-election-dashboard-lkxwq`), `fct-election-dashboard` (former repo name), "FCT 2026" (CONTEXT.md), and the on-disk working dir "Election results." Pick one slug and use it everywhere.
2. **The API-key concept.** One feature is called `/api-access` (frontend route), `/api/developer` (backend blueprint + gate exempt prefix, `api_gate.py:30`), `ApiClient` (model), and "developer key" / "API key" (docs). A newcomer cannot tell these are the same thing. Standardize on one name for the route, endpoint, and model.
3. **The `ned_` vs `ng-` abbreviation.** API keys are prefixed `ned_` (`README.md:48`, `docs/API.md:25`) while the app slug is `ng-election-dashboard`. Align the abbreviation so the key prefix and the project slug tell the same story.

### Top 3 things I would ask the original team before changing anything
1. **Is the root monolith bundle safe to delete?** — do the Phase-A parity tests, the live Caddy proxy, or any deploy still reference `election_dashboard.py` / `election_data.db` / the root `Procfile`? (F-802, F-805)
2. **Is `main` supposed to be red?** — the `e2e` job depends on a live DO deploy and its POST_DEPLOY seeds; what is the intended green state, and should the README badge track it? (F-808)
3. **What is the blast radius of a local `alembic upgrade head`?** — the DB is the *shared* `apcng-db` cluster (`.do/app.yaml:110-119`); the comment says apcng's data is isolated, but I want to confirm a misconfigured `DATABASE_URL` can't reach the shared cluster before I run migrations — plus the `deploy_on_push`-breaks-on-rename gotcha and why `SEED_USERS` is env-driven rather than a seed file.

---

## Onboarding verdict

**Realistic productive-newcomer ramp: 4–6 working days.** A capable engineer can get the *backend process* up in under an hour, but the documented path yields a **data-less dashboard** (F-803) that reads as broken, and the repo actively fights the newcomer's mental model with a **dead app at the root** (F-802), a **committed stale context file that is wrong on every fact** (F-801), and **contradictory DB config** (F-804). Days 2–4 go to reconciling those contradictions and reverse-engineering the undocumented auth and same-origin-gate behavior (F-806, F-807).

**Rate-limiting step:** not the code — it is *disambiguating which of the two apps in the repo is real, and why a by-the-book setup shows no data.* Fix F-801/F-802/F-803/F-804 (all Small effort, mostly deletions and README edits) and the ramp collapses to roughly **1 day**. The code itself is clean, typed (mypy strict), and blueprint-organized; the debt is entirely in onboarding surface, which is the highest-leverage thing to fix now that outside contributors are invited.
