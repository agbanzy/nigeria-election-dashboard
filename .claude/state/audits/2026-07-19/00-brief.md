# Audit brief — Nigeria Election Dashboard — 2026-07-19

**READ THIS FIRST. The committed `.claude/state/CONTEXT.md` is STALE (pre-refactor). Audit the CURRENT code, described below.**

## What this project is
Pan-Nigeria, multi-cycle election-results dashboard. Live at https://elections.innoedgetech.com.
Scrapes INEC IReV on election day, serves certified historical results (2015–present) otherwise,
and computes descriptive + advanced stats (ENP, swing, competitiveness). **Public civic-data project**
— election-result integrity is the paramount trust property. Falsified or corrupted results are the
highest-impact failure mode.

## Current architecture (NOT the stale CONTEXT.md)
- **Backend**: Python 3.11 + Flask app-factory (`backend/app/__init__.py`) + SQLAlchemy 2 + Alembic.
  - API blueprints in `backend/app/api/*.py` (health, states, elections, candidates, results, analysis,
    calendar, methodology, overview, live/SSE, scrape, auth, admin, developer, sync).
  - `backend/app/api_gate.py` — the free-API gate (programmatic /api/* needs an approved key; dashboard
    same-origin traffic passes). **Look hard at how it decides "same-origin".**
  - Scraper: `backend/app/scraper/*` — IReV HTTP client w/ token-bucket, calendar-driven wake policy,
    daemon, discovery, phases, backfill, sync.
  - Importer: `backend/app/importer/*` — Pydantic schemas, party-code normalizers, CSV/Excel/PDF/Stears/
    Dataphyte/Wikidata loaders.
  - Analysis: `backend/app/analysis/*` — enp, swing, competitiveness, descriptive, refresh (materialized views).
  - OCR: `backend/app/ocr/*` — EC8A form parsing.
  - Auth: DB-backed users (`models.User`), bcrypt, `api/auth.py` login endpoint. `models.ApiClient` for API keys.
- **Frontend**: Next.js 14 App Router + Tailwind + recharts + SWR + react-leaflet.
  - `frontend/src/middleware.ts` — gates ONLY `/admin/:path*` (role=admin). Everything else public.
  - `frontend/src/lib/auth.ts` — NextAuth v4 credentials provider → calls Flask `/api/auth/login`.
  - `frontend/src/app/admin-api/[...path]/route.ts` — server-side admin proxy, injects `X-Admin-Token`.
  - `frontend/src/app/api-access/page.tsx` — public developer-key application form.
  - `frontend/src/components/admin/ApiClientsPanel.tsx` — admin approves/revokes keys.
- **Infra**: DO App Platform (`.do/app.yaml`) — services: web (Flask), frontend (Next.js);
  worker: scraper; jobs: migrate (PRE_DEPLOY), seed / seed-historical / discover-headers / seed-users (POST_DEPLOY).
  DB: managed Postgres 16 on the SHARED `apcng-db` cluster. A separate Caddy reverse-proxy droplet
  (`elections-proxy`, ~$4/mo) fronts the custom domain. App id `d71eb896-bf3e-4d14-830e-2930ecc48c37`.

## Access model (intended)
- Dashboard + all election data: FREE, no login.
- Programmatic API: FREE but requires an approved key (apply at /api-access → admin approves → key issued).
- `/admin`: login-gated, role=admin. Admin write endpoints also require `X-Admin-Token`.
- INEC IReV "API key" in `scraper/irev_client.py` is INEC's PUBLIC Angular SPA key — not a secret.

## Recent history worth knowing
- Repo was public from early on; open-sourced properly 2026-07-18 (MIT LICENSE, README, API.md, SECURITY.md).
- Old bcrypt password hashes were committed then rotated 2026-07-18 (hashes still in git history).
- Repo renamed fct-election-dashboard → nigeria-election-dashboard 2026-07-18.
- Pre-existing RED CI on main (mentioned by user; confirm what's failing).

## Finding format (use EXACTLY this, one block per finding)
```
### F-<NNN>: <one-line title>
- **Severity**: Critical | High | Medium | Low
- **Persona**: <your persona>
- **Surface**: web | backend | infra | shared
- **Files**: `path:line-range`
- **Problem**: 2–4 sentences
- **Impact**: blast radius
- **Repro / Evidence**: code excerpt / steps
- **Recommended fix**: approach
- **Effort**: S | M | L | XL
- **Tags**: e.g. auth, quick-win, migration-required
```

## Finding-number blocks (avoid collisions across parallel personas)
- Architect: F-101… | Security: F-201… | Performance: F-301… | Reliability: F-401… |
  Product: F-501… | Test/CI: F-601… | Adversary: F-701… | Newcomer: F-801… | Cost: F-901…

## Safety rules (hard)
- NEVER paste secrets, real credential values, real PII, or production DB rows into audit files.
- NEVER read `.env`, `.env.*`, kubeconfig, or Terraform state. `.env.example` files are fine.
- NEVER run remediations. Audit produces findings only.
- NEVER access production. Infer from code.
- Ground every finding in a real file:line. No generic "consider adding tests" filler — cite the gap.
