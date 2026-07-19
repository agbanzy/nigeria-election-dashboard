# Product / UX audit — Nigeria Election Dashboard — 2026-07-19

**Persona:** Product Engineer (UX + correctness). **Scope:** `frontend/src` — pages, shared components, layout, `globals.css`. Read-only; inferred from code.

## Executive summary

The product is feature-rich and its provenance *intentions* are good (a dedicated `/methodology` page, per-view `MethodologyDisclosure`, honest empty-state copy, a `prefers-reduced-motion` CSS block, proper `<html lang>`, and mostly non-blaming error strings). But the single most important property for a civic election product is broken: **live/partial and manually-keyed tallies are rendered with the exact same solid party colors, votes, and share percentages as certified historical results, with no "provisional", no "% of polling units reporting", and no "as of" timestamp anywhere on the public surface** — the completeness/recency fields that would carry that context (`upload_pct`, `results_synced_at`) exist in the data model but are shown only to admins. Accessibility is thin for a map- and chart-heavy product: both choropleths are mouse-only, party identity is encoded by color alone (PDP-red vs LP-green collide under red-green color blindness), there are zero `aria-live` regions on a "live" product, loading states are effectively absent app-wide (the skeleton components are dead code), and the pervasive `--text-dim` token fails WCAG AA contrast. Net: delightful on a mouse-driven desktop for a sighted analyst; merely functional on mobile; and genuinely risky wherever a casual visitor could read an in-progress count as a final result.

## Severity counts

| Severity | Count | Finding IDs |
|---|---|---|
| Critical | 1 | F-501 |
| High | 6 | F-502, F-503, F-504, F-505, F-506, F-507 |
| Medium | 6 | F-508, F-509, F-510, F-511, F-512, F-513 |
| Low | 5 | F-514, F-515, F-516, F-517, F-518 |
| **Total** | **18** | |

---

### F-501: Provisional / live / manually-keyed results are visually indistinguishable from certified final results
- **Severity**: Critical
- **Persona**: Product
- **Surface**: web
- **Files**: `frontend/src/components/shared/NigeriaLeafletMap.tsx:122-147,162-181,327-368`; `frontend/src/components/shared/StateDrillMap.tsx:119-131,271-287`; `frontend/src/app/elections/[lgaName]/page.tsx:109-167`; `frontend/src/app/admin/page.tsx:105-127,199-203`
- **Problem**: On the choropleth, a state gets the amber "counting" tint only while `isLive && !hasData` (`NigeriaLeafletMap.tsx:137`). The moment any tally arrives, the state is filled with the leading party's color at `fillOpacity 0.88` (line 145) — identical to a certified 2023 result; the only distinction is a thin amber border (line 143) that no legend explains. The detail panel then shows Votes / Share / Margin / Total (lines 341-368) with no "provisional", no "% of PUs reporting", and no timestamp. The completeness and recency signals that exist in the model — `upload_pct`, `uploaded_pus`, `results_synced_at` — are rendered **only in `/admin`** (`admin/page.tsx:247-252`), never on any public view. Admin-entered manual and OCR-derived tallies flow straight to the public map (`admin/page.tsx:120-121` "populate the map & comparison instantly") carrying none of the OCR-confidence / review caveat the admin sees. Meanwhile marketing copy promises "certified history back to 2015" (`layout.tsx:13`), yet the word "provisional"/"unofficial"/"preliminary" appears nowhere in the UI and "certified" never labels a specific number.
- **Impact**: The paramount trust failure named in the brief. During a live election a state with 2% of polling units reporting is painted the same solid party color as a final certified result; a journalist screenshotting the map, or any casual visitor, can broadcast an in-progress lean as a called result. This is an election-integrity and reputational risk for the whole product.
- **Repro / Evidence**: `NigeriaLeafletMap.tsx:145` `fillOpacity: dimmed ? 0.2 : isLive && !hasData ? 0.75 : 0.88` — once `hasData` is true a live state renders at 0.88 like any certified state; detail panel (lines 341-368) has no provisional/reporting field. `admin/page.tsx:32-34` shows `upload_pct`/`results_synced_at` are available but confined to admin.
- **Recommended fix**: Introduce an explicit result-status model surfaced on every public view: badge each result as Certified / Provisional / Live-counting; on live/provisional states use a visual treatment that cannot be mistaken for final (hatch/stripe fill, reduced saturation, or a persistent "PROVISIONAL — N% of PUs reporting" chip), and render "% reporting" + "as of <time>" in the map tooltip, detail panel, and standings table. Carry OCR/manual provenance and confidence through to the public row. Legend must explain the provisional treatment.
- **Effort**: L
- **Tags**: election-integrity, data-provenance, misleading-visualization, trust

---

### F-502: No data-recency ("as of") timestamp on any public results view
- **Severity**: High
- **Persona**: Product
- **Surface**: web
- **Files**: `frontend/src/app/live/page.tsx:13-23,231-261`; `frontend/src/components/layout/Header.tsx:66-68,158-160`; `frontend/src/components/shared/NigeriaChoropleth.tsx`; `frontend/src/app/states/[stateCode]/page.tsx`
- **Problem**: The Live page's payload includes `cache.last_fetched_at` (`live/page.tsx:22`) but it is never rendered. The only freshness indicator anywhere is the Header's "Updated Ns ago" (`Header.tsx:66-68`), which measures time since the *browser* fetched, not when the *data* was last synced from IReV — and it renders only inside the dashboard shell, so the public landing map (`app/page.tsx`) and every map tooltip show numbers with no recency context at all.
- **Impact**: Users cannot tell whether a figure is 30 seconds or 6 hours old. Combined with F-501, stale provisional data reads as current final data. "As of" is a baseline integrity requirement for published election numbers.
- **Repro / Evidence**: `grep results_synced_at|last_fetched_at` → present in payload types, absent from all rendering except admin. `Header.tsx:67` computes freshness from `Date.now() - lastDataUpdate` (client fetch time).
- **Recommended fix**: Surface a real data-`as of` timestamp (server-provided sync time, in the viewer's timezone with the zone shown) on the map, the standings tables, and the landing hero. Distinguish "data synced at" from "page loaded at".
- **Effort**: M
- **Tags**: data-provenance, trust, quick-win

---

### F-503: Interactive choropleth maps are keyboard- and screen-reader-inaccessible
- **Severity**: High
- **Persona**: Product
- **Surface**: web
- **Files**: `frontend/src/components/shared/NigeriaLeafletMap.tsx:183-208,285-303`; `frontend/src/components/shared/StateDrillMap.tsx:139-168,219-254`
- **Problem**: Both maps are the product's primary drill-in surface (the landing hero is a map). States/LGAs are Leaflet vector paths whose only interaction is a mouse `click`/`mouseover` handler (`NigeriaLeafletMap.tsx:196-206`); the paths are not focusable, there is no `tabIndex`, no `keydown`, no `role`, no text alternative, and tooltips are hover-only HTML strings (lines 162-181). Nothing about the map is announced to a screen reader. The national map has a partial mitigation — a keyboard-reachable "Direct nav grouped by zone" grid of `<Link>`s below it (`NigeriaChoropleth.tsx:174-210`) — but **`StateDrillMap` (LGA→ward results) has no such fallback**, so LGA/ward-level results are entirely mouse-only.
- **Impact**: Keyboard-only and blind users cannot reach state results via the headline UI, and cannot reach LGA/ward results at all. WCAG 2.1.1 (Keyboard) and 4.1.2 (Name, Role, Value) failures on the core task.
- **Repro / Evidence**: Only 12 `aria-label`s and 0 `role`s exist in the entire frontend (grep). Leaflet paths in `onEach`/`onEachLga` bind mouse events only.
- **Recommended fix**: Add a keyboard-accessible, screen-reader-friendly equivalent for every map (a visually-hidden or visible list of state/LGA results with the same links), give the map container a `role`/`aria-label` and a text summary, and mirror the zone-grid fallback into `StateDrillMap`.
- **Effort**: L
- **Tags**: accessibility, wcag-a, keyboard, maps

---

### F-504: No `aria-live` regions on a "live" product — result updates, connection status, and errors are silent to assistive tech
- **Severity**: High
- **Persona**: Product
- **Surface**: shared
- **Files**: `frontend/src/components/shared/ConnectionBanner.tsx:20-26`; `frontend/src/components/shared/AnimatedCounter.tsx`; `frontend/src/app/dashboard/page.tsx:60-64`; `frontend/src/app/live/page.tsx`
- **Problem**: There are zero `aria-live`/`role="status"`/`role="alert"` regions in the codebase (grep: only 12 `aria-label`, 0 `role`). SWR polls new numbers every 15–60s and the count-ups animate silently; the offline/reconnecting banner (`ConnectionBanner.tsx`) and the "Failed to load… Retrying" banners (`dashboard/page.tsx:61`) are visual-only. The entire live-election value proposition is unannounced to screen-reader users.
- **Impact**: Blind users get no notification that results changed, that the network dropped, or that a load failed — on the exact product whose headline feature is real-time updates. WCAG 4.1.3 (Status Messages) failure.
- **Repro / Evidence**: `grep -r "aria-live|role=\"status\"|role=\"alert\""` → none.
- **Recommended fix**: Wrap the connection banner and load-error banners in `role="status"`/`role="alert"`; add a polite `aria-live` region that announces material result changes (e.g., "Ekiti updated: APC 42%, 61% of PUs reporting"); ensure `AnimatedCounter` exposes the final value to AT, not the interpolating frames.
- **Effort**: M
- **Tags**: accessibility, wcag-aa, live

---

### F-505: Loading state missing app-wide — skeleton components are dead code; async views render blank while fetching
- **Severity**: High
- **Persona**: Product
- **Surface**: web
- **Files**: `frontend/src/components/shared/SkeletonLoader.tsx` (entire file unused); `frontend/src/hooks/useApiData.ts`; `frontend/src/app/live/page.tsx:97,131,177,202,232,245,263`; `frontend/src/app/dashboard/page.tsx:69-98`; `frontend/src/app/states/[stateCode]/page.tsx`; `frontend/src/app/analytics/page.tsx`; `frontend/src/app/insights/page.tsx`; `frontend/src/app/cycles/[year]/page.tsx`
- **Problem**: `SkeletonCard`/`SkeletonTable`/`SkeletonLine` are defined but imported by **zero** pages (grep). Every data view gates its content on `data &&` / `data?.…`, so while `useApiData` is loading, sections render nothing. On the Live page all six sections are wrapped in `cov && …` / `sync && …` (lines 97, 131, …) with no loading placeholder — during a slow fetch the flagship election-day view is a near-blank page with just a header. StatCards fall back to `"—"` (`dashboard/page.tsx:71`) rather than skeletons. Only `elections` and `candidates` show even a "loading…" text hint.
- **Impact**: The three-states "loading" rule fails across the product; on election day a blank live view reads as "the site is broken" at the moment traffic and stakes peak. The fix is cheap because the skeleton primitives already exist.
- **Repro / Evidence**: grep for `SkeletonCard|SkeletonTable|SkeletonLine` usage → none; `live/page.tsx` sections all `{cov && (…)}` with no `else`.
- **Recommended fix**: Render the existing skeleton components (or spinners) whenever `!data && !error`; prioritize the Live page, dashboard, state pages, analytics, insights, and cycle pages. Reserve layout height to avoid shift on resolve.
- **Effort**: M
- **Tags**: three-states, loading, dead-code, quick-win

---

### F-506: Party identity encoded by color alone; PDP-red and LP-green collide under red-green color blindness
- **Severity**: High
- **Persona**: Product
- **Surface**: shared
- **Files**: `frontend/src/lib/constants.ts:1-15`; `frontend/src/components/shared/NigeriaLeafletMap.tsx:122-147`; `frontend/src/components/shared/StateDrillMap.tsx:119-131`
- **Problem**: On both map faces the winning party is conveyed only by fill color; the state/LGA polygon carries no party-code label or pattern. The palette pairs `PDP:#c62828` (red) against `LP:#2e7d32` (green) and `APC:#1565c0` (blue) — red vs green being the classic deuteranope/protanope confusion pair, and these are the dominant national parties. Party codes appear in the legend, hover tooltip, and detail panel, but all require a mouse; the at-a-glance national read is color-only.
- **Impact**: ~8% of male viewers cannot reliably tell which of the two biggest parties won a state from the map — the product's central visualization. WCAG 1.4.1 (Use of Color, Level A) failure.
- **Repro / Evidence**: `constants.ts` party palette; map fills set purely from `winner_party_color`/`getPartyColor` with no secondary encoding.
- **Recommended fix**: Add a non-color channel on the map — party-code abbreviation label on/next to each polygon, or hatch/texture patterns per party — and choose a colorblind-safe palette (or run the current one through a CVD simulator and separate PDP/LP). Keep the legend but don't rely on it.
- **Effort**: M
- **Tags**: accessibility, wcag-a, color, maps

---

### F-507: `--text-dim` and raw white-opacity text fail WCAG AA contrast, including the provenance microcopy
- **Severity**: High
- **Persona**: Product
- **Surface**: shared
- **Files**: `frontend/src/app/globals.css:15,51`; `frontend/src/components/shared/MethodologyDisclosure.tsx:13`; `frontend/src/app/page.tsx:44,61,75,108`; `frontend/src/app/api-access/page.tsx:30`
- **Problem**: The pervasive secondary-text token `--text-dim: #6b7280` (`globals.css:15`) computes to ≈4.0:1 on `--bg (#0a0d14)` and ≈3.7:1 on `--card (#141821)` — below the 4.5:1 AA threshold for normal text — and it clothes nearly all captions, labels, table cells, timestamps, empty-state copy, and the `MethodologyDisclosure` provenance line, which is additionally set to 10px italic (`MethodologyDisclosure.tsx:13`). The public landing/login/api-access surfaces layer raw opacities `text-white/40 … /15` (`page.tsx:44,108`), the lowest of which (`text-white/15`, `/20`) render at roughly 1.3–1.5:1 — effectively invisible — on the first screen every visitor sees.
- **Impact**: Low-vision users, and most users in bright outdoor/mobile conditions (common in-country), cannot read secondary text — and the text that matters most for trust (sources, "as of", caveats, empty-state explanations) is exactly what's rendered in the least legible style.
- **Repro / Evidence**: Contrast math on `#6b7280` over `#141821` ≈ 3.7:1; `page.tsx:108` `text-white/15` over `#070d1a`.
- **Recommended fix**: Raise `--text-dim` to ≥4.5:1 (e.g. around `#9aa4b2`), replace ad-hoc `text-white/15…/40` with tokens that meet AA, and never render provenance/caveat copy below 4.5:1 or below ~12px.
- **Effort**: M
- **Tags**: accessibility, wcag-aa, contrast, trust

---

### F-508: Data tables lack semantics (no `scope`/`caption`); the only sortable table (`DataTable`) is mouse-only — and unused
- **Severity**: Medium
- **Persona**: Product
- **Surface**: shared
- **Files**: `frontend/src/components/shared/DataTable.tsx:92-113` (unused); `frontend/src/app/elections/page.tsx:49-88`; `frontend/src/app/candidates/page.tsx:151-196`; `frontend/src/app/states/[stateCode]/page.tsx:187-212`
- **Problem**: Every results table is hand-rolled `<table>` with `<th>` that has no `scope`, no `<caption>`, and index-based row keys — thin structure for screen-reader table navigation. The shared `DataTable` adds sortable headers but as `<th onClick>` with `cursor-pointer` and no `role`/`tabIndex`/`onKeyDown`/`aria-sort` (`DataTable.tsx:93-101`), so sorting is mouse-only and sort state is unannounced — and `DataTable` is imported by **zero** pages (grep), so this capability ships as dead code while the live tables have no sort at all.
- **Impact**: AT users get poorly-structured tables; the reusable accessible-sort affordance is both inaccessible and unwired. WCAG 1.3.1 / 4.1.2.
- **Repro / Evidence**: grep `DataTable` usage → none; hand-rolled `<th>` in `elections/page.tsx:51-57` have no `scope`.
- **Recommended fix**: Add `scope="col"`/`<caption>` to the live tables; either wire `DataTable` in and make its headers real `<button>`s with `aria-sort`, or delete it if sort isn't needed.
- **Effort**: M
- **Tags**: accessibility, tables, dead-code

---

### F-509: Internal / developer jargon and ops instructions leak onto public pages
- **Severity**: Medium
- **Persona**: Product
- **Surface**: web
- **Files**: `frontend/src/app/live/page.tsx:87-91`; `frontend/src/app/elections/[lgaName]/page.tsx:281-287,359-370`; `frontend/src/app/analytics/page.tsx:124`; `frontend/src/app/analytics/page.tsx:196`; `frontend/src/app/elections/[lgaName]/page.tsx:345`
- **Problem**: The public Live page instructs visitors to "Toggle `SCRAPER_BURST_FACTOR` in the DO console (1.0 default → 5.0 for full sync)" (`live/page.tsx:88-90`). Any election with scanned forms but no parsed tally renders a public `<details>` "How to add this data" containing a backend CLI command — `python -m app.importer.cli load --file data/historical/… --source …` and "re-deploy" (`elections/[lgaName]/page.tsx:281-287,359-370`). Analytics empty states say "Phase D will populate" (`analytics/page.tsx:124`). Raw values leak too: numeric `state_id` is shown where a state name belongs — "state 25" (`analytics/page.tsx:196`, `elections/[lgaName]/page.tsx:345`) — and raw status enums (`sync_complete`, `pending_structure`) appear in "Status" columns.
- **Impact**: Erodes credibility with the civic/journalist audience, exposes internal architecture, and confuses non-technical users. Not a security leak per se, but a clarity and trust cost.
- **Repro / Evidence**: `live/page.tsx:88`; `elections/[lgaName]/page.tsx:281`.
- **Recommended fix**: Move ops instructions and CLI snippets out of public views (admin-only or docs); map internal roadmap phases and status enums to plain-language labels; resolve `state_id` → state name everywhere it's shown.
- **Effort**: M
- **Tags**: copy, trust, jargon

---

### F-510: JS-driven motion ignores `prefers-reduced-motion`
- **Severity**: Medium
- **Persona**: Product
- **Surface**: shared
- **Files**: `frontend/src/components/shared/AnimatedCounter.tsx:29-52`; `frontend/src/app/insights/page.tsx:146-158`; `frontend/src/app/dashboard/page.tsx:109-118`; `frontend/src/app/globals.css:279-285`
- **Problem**: The `globals.css` reduced-motion block (lines 279-285) only neutralizes CSS animations/transitions. It cannot touch JS-driven motion: `AnimatedCounter` runs a `requestAnimationFrame` count-up on mount and on every value change with no `matchMedia('(prefers-reduced-motion)')` guard (`AnimatedCounter.tsx:29-52`), and it is used in every StatCard, coverage tile, and zone total. Recharts line/bar/scatter animations (`isAnimationActive`, `animationDuration={1200}` in `insights/page.tsx:155-156`) are SVG-attribute-driven and likewise unaffected. There is no `matchMedia`/`useReducedMotion` anywhere in the codebase (grep).
- **Impact**: Users who set reduced-motion (vestibular sensitivity) still get pervasive count-ups and animated charts. WCAG 2.3.3 (AAA) and a common accessibility-baseline expectation.
- **Repro / Evidence**: grep `matchMedia|useReducedMotion|prefers-reduced-motion` → only the CSS media query; `AnimatedCounter.tsx` has no guard.
- **Recommended fix**: Add a `useReducedMotion` hook; when set, have `AnimatedCounter` render the final value immediately and pass `isAnimationActive={false}` to recharts.
- **Effort**: S
- **Tags**: accessibility, reduced-motion

---

### F-511: Public API-access form fields have no `<label>` (placeholder-only) and low-contrast placeholders
- **Severity**: Medium
- **Persona**: Product
- **Surface**: web
- **Files**: `frontend/src/app/api-access/page.tsx:29-30,127-129,148`
- **Problem**: The four inputs (name, email, use-case, application reference) are labelled only by `placeholder` (`api-access/page.tsx:127-129,148`) with no `<label>`/`aria-label`; placeholders vanish on input and are unreliable accessible names, and the placeholder token is `placeholder-white/25` (`inputCls`, line 30) — very low contrast. The `/login` page does this correctly with real `<label>`s (`login/page.tsx:78,93`), so the codebase is inconsistent.
- **Impact**: Screen-reader users hear poorly-named fields; low-vision users can't read the only labels present. WCAG 1.3.1 / 3.3.2 / 4.1.2.
- **Repro / Evidence**: `api-access/page.tsx:127` `<input … placeholder="Your name or project" …>` with no associated label.
- **Recommended fix**: Add visible `<label>`s (or at minimum `aria-label`) to each field and raise placeholder contrast; mirror the `/login` pattern.
- **Effort**: S
- **Tags**: accessibility, forms, quick-win

---

### F-512: Inert "Top parties" buttons look interactive but do nothing
- **Severity**: Medium
- **Persona**: Product
- **Surface**: web
- **Files**: `frontend/src/app/candidates/page.tsx:129-141`
- **Problem**: The "Top parties by candidate count" tiles are `<button>`s whose `onClick` is an empty no-op with the comment "No party filter param yet; visual cue only" (`candidates/page.tsx:132-134`). Twelve controls render as clickable and focusable but do nothing on click or keyboard activation — while a separate, working Party dropdown exists a few lines above.
- **Impact**: Users (and keyboard/AT users) reasonably expect clicking a party to filter; nothing happens, which reads as a broken feature. Dead controls also add noise to the tab order.
- **Repro / Evidence**: `candidates/page.tsx:132` `onClick={() => { /* No party filter param yet; visual cue only */ }}`.
- **Recommended fix**: Either wire the tiles to set the existing party filter, or render them as non-interactive `<div>`/stat chips (not `<button>`).
- **Effort**: S
- **Tags**: dead-control, ux, a11y

---

### F-513: Error state missing on several core async views (inconsistent with the rest)
- **Severity**: Medium
- **Persona**: Product
- **Surface**: web
- **Files**: `frontend/src/app/states/page.tsx:33`; `frontend/src/app/states/[stateCode]/page.tsx:64-74`; `frontend/src/app/analytics/page.tsx:58-63`; `frontend/src/app/insights/page.tsx:69-80`; `frontend/src/app/cycles/[year]/page.tsx:18`
- **Problem**: These pages never destructure `error` from `useApiData`; on a failed fetch they render empty/blank indefinitely (SWR retries in the background, but the user sees no "couldn't load / retry"). The state detail page (`states/[stateCode]`) fetches five endpoints and handles the error of none. This is inconsistent with pages that *do* handle it (`dashboard`, `elections`, `cycles/compare`, `methodology`, `ElectionCountdown`), so the app's error behavior is a coin-flip per route.
- **Impact**: On backend trouble, half the product silently shows empty content that is indistinguishable from "no data exists" (see also F-505, where empty also can't be told from loading) — misleading and unactionable. The three-states "error" rule fails on these routes.
- **Repro / Evidence**: `states/[stateCode]/page.tsx:64-74` — five `useApiData` calls, no `error` read; contrast with `dashboard/page.tsx:44,60-64`.
- **Recommended fix**: Read and render `error` on every async view with a user-readable message and a retry affordance; consider a small shared `<AsyncBoundary>` wrapper enforcing loading/error/empty consistently.
- **Effort**: M
- **Tags**: three-states, error-handling, consistency

---

### F-514: No data export/download in the UI (export code shipped but unwired)
- **Severity**: Low
- **Persona**: Product
- **Surface**: web
- **Files**: `frontend/src/components/shared/ExportButton.tsx` (unused); `frontend/src/hooks/useExport.ts` (unused); `frontend/src/components/shared/Modal.tsx` (unused); `frontend/src/lib/constants.ts:47-52`
- **Problem**: `ExportButton` and `useExport` are imported by zero pages (grep), so there is no CSV/data-download affordance anywhere in the shipped UI. For an open-data civic product, non-developer users (journalists, researchers) have no one-click way to take the numbers — they must use the developer API. Alongside this sit other dead artifacts signalling drift: `Modal` (unused, and itself missing focus-trap/`role="dialog"`/Esc if ever wired) and a stale `NAV_ITEMS` in `constants.ts:47-52` still pointing at the retired `/messaging` route.
- **Impact**: Minor product gap (the free API mitigates it) plus maintenance noise; the missing export is the user-facing part.
- **Repro / Evidence**: grep `ExportButton|useExport|Modal|DataTable` usage → none; `constants.ts:50` `{ name: "Messaging", href: "/messaging" }`.
- **Recommended fix**: Wire `ExportButton` into the tables/analytics (CSV of the current view), or explicitly point users to the API; delete the stale `NAV_ITEMS` and unused components or track them.
- **Effort**: M
- **Tags**: product-gap, open-data, dead-code

---

### F-515: `StatCard` update-flash fires on first load (wrong sentinel), and `sub` uses `dangerouslySetInnerHTML`
- **Severity**: Low
- **Persona**: Product
- **Surface**: shared
- **Files**: `frontend/src/components/shared/StatCard.tsx:22-30,49-54`
- **Problem**: The "value changed" green flash is suppressed only when the previous value equals `"--"` (`StatCard.tsx:23`), but pages pass the loading placeholder as `"—"` (em-dash, e.g. `dashboard/page.tsx:71`). The sentinels don't match, so the guard never triggers and every StatCard flashes "updated" on its initial render even though nothing changed — a subtle false "this number just moved" cue on a results dashboard. Separately, `sub` is injected via `dangerouslySetInnerHTML` (line 52); it is static today ("of 36 + FCT") but is a latent XSS/foot-gun if `sub` ever becomes data-driven.
- **Impact**: Small credibility papercut (spurious change animation) plus a latent injection risk.
- **Repro / Evidence**: `StatCard.tsx:23` checks `"--"`; callers pass `"—"`.
- **Recommended fix**: Compare against the actual placeholder (or a dedicated `isLoading` prop) so the flash only fires on genuine change; replace `dangerouslySetInnerHTML` with plain children/JSX.
- **Effort**: S
- **Tags**: correctness, misleading-visualization, security-latent

---

### F-516: Timezone ambiguity — live clock and election dates carry no zone; potential hydration mismatch
- **Severity**: Low
- **Persona**: Product
- **Surface**: web
- **Files**: `frontend/src/hooks/useLiveClock.ts:5-27`; `frontend/src/components/shared/ElectionCountdown.tsx:79`; `frontend/src/components/layout/Header.tsx:92`
- **Problem**: `useLiveClock` formats `new Date()` with a hardcoded `en-GB` locale and no timezone label (`useLiveClock.ts:13-24`); the header clock and countdown therefore show a bare time with no indication whether it's WAT or the viewer's local zone. Election dates render as raw ISO date strings with no zone. Initializing `new Date()` in a client component without `suppressHydrationWarning` also risks a server/client hydration mismatch on the first render.
- **Impact**: A diaspora viewer can't tell if "18:00" or the countdown is Nigeria time or theirs — a real ambiguity for a cross-border civic audience. Low, but relevant to a "live" product.
- **Repro / Evidence**: `useLiveClock.ts:13` `toLocaleTimeString("en-GB", {…})` — no `timeZone`; no zone string rendered.
- **Recommended fix**: Show an explicit timezone next to the clock/countdown (e.g. "WAT"), pin server-side time arithmetic to UTC, and format dates with an explicit zone.
- **Effort**: S
- **Tags**: i18n, timezone, correctness

---

### F-517: No i18n readiness — strings inline, English-only
- **Severity**: Low
- **Persona**: Product
- **Surface**: web
- **Files**: `frontend/src/` (all pages/components); `frontend/src/app/layout.tsx:58`
- **Problem**: No i18n framework is present (no `next-intl`/`react-i18next`/`formatjs`; grep) and all user-facing copy is inline in JSX, including sentence assembly by concatenation (e.g. `Header.tsx:83` `{subtitle} • {date}`). English-only is defensible for a Nigerian civic product (English is the official lingua franca, and `<html lang="en">` is correctly set at `layout.tsx:58`), but Hausa/Yoruba/Igbo are unsupported and retrofitting later is costly because strings are scattered.
- **Impact**: Excludes non-English-comfortable citizens from a public-interest tool; forward-looking gap rather than a present blocker.
- **Repro / Evidence**: grep for i18n libraries → none.
- **Recommended fix**: If multi-language is on the roadmap, externalize strings now and adopt a lightweight i18n layer; otherwise record English-only as a conscious decision.
- **Effort**: L
- **Tags**: i18n, readiness

---

### F-518: Mobile — full-width 520px maps capture touch-drag and can trap page scroll
- **Severity**: Low
- **Persona**: Product
- **Surface**: web
- **Files**: `frontend/src/components/shared/NigeriaLeafletMap.tsx:285-290`; `frontend/src/components/shared/StateDrillMap.tsx:219-224`; `frontend/src/app/page.tsx:68-71`
- **Problem**: Both maps render at a fixed `height: 520` full-bleed (`NigeriaLeafletMap.tsx:288`) and the landing map fills the viewport (`page.tsx:68`). `scrollWheelZoom` is correctly disabled, but Leaflet touch drag/pan is still active, so on a phone a vertical swipe that starts on the map pans the map instead of scrolling the page — a scroll-trap on the tallest element on the landing screen, with no "use two fingers to move the map" hint. The rest of the app is otherwise responsive (mobile drawer, `overflow-x-auto` tables, responsive grids).
- **Impact**: Friction getting past the hero map on the device class most Nigerian users are on. Localized, not blocking.
- **Repro / Evidence**: `NigeriaLeafletMap.tsx:289` `scrollWheelZoom={false}` but no `dragging`/`tap` handling for touch; map is the full-height landing element.
- **Recommended fix**: Add a mobile affordance (require two-finger pan via `cooperativeGestures`, or a "tap to interact" overlay), and/or cap map height on small viewports so the page remains scrollable around it.
- **Effort**: M
- **Tags**: mobile, gesture-conflict, maps

---

## User experience verdict

**For the typical user on the typical device (an Android phone on a metered connection):**

- **Delightful** for a sighted analyst on a mouse-driven desktop: the choropleth drill-in, the live coverage matrix, the cross-cycle swing/ENP analytics, and the honest empty-state copy are genuinely strong, and the `/methodology` page plus per-view source lines show real intent toward transparency.
- **Merely functional** on mobile and on slow networks: responsive layout holds, but loading states are blank rather than skeletons (F-505), the hero map can trap scroll (F-518), and low-contrast dim text (F-507) is hard to read outdoors.
- **Broken** in two ways that matter most for this product's mission. First, for users with disabilities: the maps are mouse-only (F-503), party = color-only (F-506), nothing is announced live (F-504), and secondary/provenance text fails contrast (F-507) — an election tool that a blind or colorblind citizen largely cannot use. Second, and gravest, for *everyone*: the UI does not distinguish an in-progress or manually-keyed count from a certified final result — no "provisional", no "% reporting", no "as of" (F-501, F-502). On a public civic-data product, that is the one defect that can actively mislead the electorate, and it should be the first thing fixed.
