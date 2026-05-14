# CONTEXT — current state, gotchas, recent findings

## Repo at clone time (2026-05-14)

- Default branch: `main`. Last push: 2026-02-22 (post-FCT 2026 Area Council election).
- Backend: single file `election_dashboard.py` (2441 lines), Flask + SQLite + background scraper thread + optional pytesseract OCR.
- Frontend: Next.js 14 + Tailwind + recharts + SWR. ~12 components, ~5 routes. No map library. No global filter state.
- Data: `election_data.db` (~25 MB SQLite, FCT-only); `FCT_2026_Area_Council_Elections.xlsx` (candidate reference).

## Upstream IReV proxy

- URL: `https://dolphin-app-sleqh.ondigitalocean.app/api/v1`
- Auth: `x-api-key` header. Key in legacy file at line 39. Move to env var `IREV_API_KEY` for the new app — never re-commit the legacy literal.
- Election type IDs known: `CHAIRMAN=5f129a04df41d910dcdc1d55`, `COUNCILLOR=5f129a04df41d910dcdc1d56`. Presidential/Gov/Senate/Reps/State HoA IDs need discovery (Phase B).
- State IDs: numeric `state_id`, FCT=15. Need full 1..37 mapping (Phase B seed).

## Local SQLite snapshot

`election_data.db` ships in the repo (committed). Used by the legacy app and by Phase A parity tests as the fixture source. Do NOT delete until parity is verified.

## Hardcoded FCT references requiring frontend refactor (from Phase 1 exploration)

| File | Symbol | Replacement |
|---|---|---|
| `frontend/src/app/layout.tsx:6-8` | metadata title/desc | `lib/branding.ts` |
| `frontend/src/components/layout/Header.tsx:81` | `<h1>FCT 2026 Area Council Elections</h1>` | `<DynamicHeader />` reading `useFilters()` |
| `frontend/src/components/layout/Sidebar.tsx:65-68` | "FCT 2026" / "Area Council Elections" | branding lookup |
| `frontend/src/app/page.tsx:66,82-83,94,113,120,129,259,297,303` | hardcoded counts, "Area Council", "Chairmanship/Councillorship" | from `/api/overview` response |
| `frontend/src/app/analytics/page.tsx:88-89,210-213,236-238` | hardcoded tab labels | from election type config |

## Existing chart inventory (all data-driven, generic, port-safe)

LineChart, BarChart, PieChart, RadarChart from recharts. Custom ProgressBar / MiniProgress. ResponsiveContainer wrapping all.

## Known gotchas

- Legacy scraper uses `sqlite3.Connection` per call (`get_db()` line 101) with no pooling. Postgres switch requires `SQLAlchemy` session lifecycle.
- Legacy `raw_json` columns are TEXT in SQLite, will be `JSONB` in Postgres.
- `OCR_LOCK` (line 621 in monolith) appears unused/vestigial.
- `CORS(*)` in legacy — keep behavior in new app but tighten to allow-list before public deploy.
- No auth on any endpoint. Phase A: leave open; Phase B: add admin auth header for `/api/force-*` routes.

## Deploy targets

- DO App Platform, region `nyc`, spec at `.do/app.yaml`.
- Components: `web` (Flask), `worker` (scraper daemon), `static_site` (Next.js), `db` (managed PG15 dev tier $15/mo).
- Estimated total: $25–35/mo until traffic grows.
- Custom domain: deferred.
