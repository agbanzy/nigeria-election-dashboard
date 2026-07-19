# CONTEXT — current state, gotchas, recent findings

_Last reconciled 2026-07-19 against live code + the live `.do/app.yaml`. This
file was rewritten wholesale — the previous version described the retired
single-file monolith and was wrong on every architectural fact._

## What this is now

A two-service Nigeria-wide election dashboard: a **Flask app-factory package**
under `backend/app/` (blueprints for health/calendar/states/elections/
candidates/results/analysis/scrape/methodology/live/overview/developer/admin/
auth), a **Next.js 14 App Router** frontend, and a background **scraper worker**
that follows INEC IReV on election day. The pre-refactor `election_dashboard.py`
monolith, root `Procfile`/`requirements.txt`, and the committed 26 MB
`election_data.db` are deleted/untracked as of this branch.

## Stack

- Backend: Python **3.11** + Flask + SQLAlchemy 2 + Alembic (gunicorn). Config is
  strict/env-driven in `backend/app/config.py`; `runtime.txt`, `pyproject.toml`,
  README and CI all pin 3.11.
- Frontend: Next.js 14 (App Router) + Tailwind + recharts + SWR + react-leaflet;
  NextAuth for the admin session.
- Data: managed **Postgres 16** in production. Local dev is a docker Postgres;
  `config.py` default DB name is `elections` (`.env.example` matches).

## Deploy target

- **DigitalOcean App Platform**, region **`fra`**, spec `.do/app.yaml`
  (app name `ng-election-dashboard`).
- **App ID:** `d71eb896-bf3e-4d14-830e-2930ecc48c37`
- **Domain:** https://elections.innoedgetech.com
- **Repo:** `agbanzy/nigeria-election-dashboard` (branch `main`, `deploy_on_push`).
- Components: `web` (Flask), `frontend` (Next.js), `scraper` (worker), `db`
  (managed PG16). Jobs: `migrate` (PRE_DEPLOY, `alembic upgrade head`) +
  `seed` / `discover-headers` / `seed-historical` / `seed-users` (POST_DEPLOY).

## Shared apcng-db cluster (gotcha)

The `db` reuses the existing managed cluster **`apcng-db`** (account hit its
cluster cap; user-authorized 2026-06-17). App Platform provisions a dedicated
database + owner role inside it, so DDL rights are clean and apcng's data is
isolated — but there is **no CPU/IOPS/connection isolation**. An election-day
write burst can starve the sibling app and vice-versa. Cap the SQLAlchemy pool,
keep `SCRAPER_BURST_FACTOR` sane, and consider a dedicated cluster before a major
election. See audit Cluster E.

## Auth model — public dashboard, admin-only writes

The dashboard **and** the read API are public with no account. Only `/admin`
(results ingestion: manual entry, OCR-assist, bulk import) requires a signed-in
admin — enforced by the Next.js middleware gate on `/admin/:path*` (role=admin).
Backend write routes require an `ADMIN_TOKEN` that the authenticated Next.js
proxy injects server-side; it is an encrypted App Platform env var, never
committed. `NEXTAUTH_SECRET` and `SEED_USERS` are likewise secret-only.

## Free API by application (gate)

The programmatic API is free but gated behind issued keys: apply at
`/api-access` → admin approves → key. Same-origin dashboard traffic always
passes (Sec-Fetch-Site / Origin match — an attribution signal, **not** a
security boundary). Enforcement defaults on when `ENV=production`
(`API_KEY_ENFORCEMENT` overrides). Gate-exempt: auth/admin/developer/health/
methodology.

## IReV upstream

`IREV_API_BASE` = `https://dolphin-app-sleqh.ondigitalocean.app/api/v1`.
`IREV_API_KEY` is intentionally **unset** — `IrevClient` falls back to INEC's
public Angular SPA client key (not a secret). No API-key literal lives in the
code (the old "line 39 secret" claim is obsolete).

## Full audit

Nine-persona code audit + Chief Auditor synthesis (108 findings, 4-sprint plan):
**`.claude/state/audits/2026-07-19/10-synthesis.md`**. This branch
(`fix/audit-2026-07-19-sprint1`) is working the quick-wins and Sprint-1 items.
