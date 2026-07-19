# Audit — Persona 6: Test & CI — Nigeria Election Dashboard — 2026-07-19

## Executive summary

CI is decorative. The GitHub Actions workflow is **`disabled_manually`**, so nothing
has run since **2026-05-16**. Every commit in the entire open-sourcing + free-API-gate
effort (2026-07-18: the login gate, the apply-and-approve key lifecycle, the new
`test_developer_api.py`) has **zero CI validation** — `check-runs` on HEAD `a0847f4` = **0**.
And in the era when CI *did* run, **every single run failed** at the lint step (74 recorded
runs, all red, ~30s each — they never reached the tests), yet PRs kept merging to `main`
(#33, #35, #36 all landed red). So CI has never gated a merge and currently does not run
at all.

Underneath the pipeline problem sits a coverage problem on the paths that matter most:

- **Auth login** (`/api/auth/login`) — the admin authentication path — has **zero tests**.
- **Result-integrity validators** (`schemas.ResultRow`, the code the file's own docstring
  calls the guard against "bad data into the dataset") have **zero direct tests**.
- The **only vote-total-correctness assertions** in the repo (INEC-certified national
  totals, `e2e.py`) live in an `e2e` job that is **gated behind backend+frontend passing —
  which never happens — and has therefore never executed**.
- **Frontend has zero tests** and a structurally broken lint step (no ESLint config).

The statistical-math layer (ENP/swing/competitiveness) and the developer-key lifecycle are
genuinely well-tested with known-value assertions — but they are islands in a pipeline that
reports nothing.

## What CI actually gates today

**Nothing.** The `CI` workflow (id 276963495) is `disabled_manually` — GitHub is not
running it on pushes or PRs, so HEAD carries no status at all. Before it was disabled it
still gated nothing: there is no evidence of required status checks on `main`, and merge
commits #33/#35/#36 landed on `main` while their runs were red. The `backend` job dies at
`ruff check` (84 violations) before `mypy`/`pytest` execute, and the `frontend` job dies at
`next lint`, so the test suite and the integrity-checking `e2e` probe have not run in CI in
living memory. A "green checkmark" is not available to be trusted because there is no check.

## Why CI is red (confirmed, not inferred)

Two independent causes, both verified against the live Actions API and the last real run
(`25956451061`, `main`, 2026-05-16):

1. **The workflow is turned off.** `gh workflow list` → `CI  disabled_manually`. No runs
   since 2026-05-16 despite 40+ commits through 2026-07-18. HEAD check-runs = 0.
2. **When it last ran, both lint steps failed** (e2e consequently `skipped`):
   - `backend` → `Lint` step: `ruff check .` reported **84 violations** — `F401` unused
     imports (`app/__init__.py:6`, `app/models.py:12,20`, `app/ocr/batch.py:23,26,30`,
     `app/api/overview.py:5,11`, several loaders…), `E741` ambiguous variable `l`
     (`app/api/elections.py:178`, `app/api/states.py:64`), `F841` unused local
     (`app/importer/loaders/candidate_csv.py:52`).
   - `frontend` → `Run npm run lint`: `next lint` finds **no ESLint config**, emits the
     interactive "How would you like to configure ESLint?" prompt, and exits 1 in the
     non-TTY runner. There is no `.eslintrc*` in `frontend/`.

## Severity table

| ID | Severity | Title |
|----|----------|-------|
| F-601 | Critical | CI workflow `disabled_manually` — zero signal on HEAD; July work never validated |
| F-602 | Critical | Auth login (`/api/auth/login`) has zero tests |
| F-603 | Critical | Result-integrity schema validators (`ResultRow`) have no direct test |
| F-604 | High | Backend lint red (84 ruff violations) — blocks the whole suite from running |
| F-605 | High | Frontend lint structurally broken — no ESLint config, `next lint` exits 1 |
| F-606 | High | No merge gate — PRs merged to `main` while CI red; no required status checks |
| F-607 | High | Only vote-total-correctness checks live in an `e2e` job that never executes |
| F-608 | Medium | Scraper `IrevClient` token-bucket + retry untested |
| F-609 | Medium | `resolve_party` normalizer untested (only the static dict is asserted) |
| F-610 | Medium | API-gate negative/bypass branches untested |
| F-611 | Medium | Frontend has zero tests (middleware gate, NextAuth, admin proxy uncovered) |
| F-612 | Low | Integration suite silently skips when Docker absent → false green |
| F-613 | Low | No coverage gate despite `pytest-cov` installed |
| F-614 | Low | No security scanning in CI (secrets / deps / SAST / container) |

---

## Findings

### F-601: CI workflow is `disabled_manually` — HEAD has zero CI signal
- **Severity**: Critical
- **Persona**: Test/CI
- **Surface**: infra
- **Files**: `.github/workflows/ci.yml:1-69` (workflow id 276963495)
- **Problem**: The `CI` workflow is disabled in GitHub Actions (`gh workflow list` →
  `CI  disabled_manually`). No runs have executed since 2026-05-16, while commits continued
  through 2026-07-18. `check-runs` on HEAD `a0847f4` returns `total_count: 0`. The entire
  open-source hardening and free-API-gate effort — including the trust-critical login gate
  and the new `test_developer_api.py` key-lifecycle tests — has never run through CI.
- **Impact**: The project's paramount property is result integrity, and there is currently
  **no automated signal at all** on the deployed code. A regression in the gate, the
  importer, the analysis math, or a migration would ship undetected. The tests that *do*
  exist provide false comfort: they are not being executed.
- **Repro / Evidence**: `gh workflow list --all` → `CI\tdisabled_manually\t276963495`;
  `gh api repos/{owner}/{repo}/commits/$(git rev-parse HEAD)/check-runs` → `total_count: 0`;
  `gh run list` newest entry is `2026-05-16`, HEAD commit is `2026-07-18`.
- **Recommended fix**: Re-enable the workflow (`gh workflow enable CI`), but only after
  F-604/F-605 are fixed so the first run can go green; otherwise it re-enables into red.
  Sequence: fix lint → enable → confirm a full green run on `main` → then make checks
  required (F-606).
- **Effort**: S (to re-enable) / M (to make it meaningfully green)
- **Tags**: ci, false-green, quick-win-blocked-by-F604/F605

### F-602: Auth login endpoint has zero tests
- **Severity**: Critical
- **Persona**: Test/CI
- **Surface**: backend
- **Files**: `backend/app/api/auth.py:18-48`; no test references `/api/auth/login` anywhere
  in `backend/tests/`
- **Problem**: `/api/auth/login` is the admin authentication path — the credential check
  NextAuth calls to grant the `admin` role that unlocks `/admin` and (with `X-Admin-Token`)
  the write endpoints. It has no test. Nothing asserts: valid credentials return the correct
  `role`; a wrong password returns 401; an inactive user (`is_active=False`) is rejected;
  missing fields return 400; the `bcrypt.checkpw` comparison actually runs. The
  password-rotation incident (commit `861b6e9` "reset both passwords") left no regression
  test behind.
- **Impact**: Auth is the one boundary between the public dashboard and the admin
  result-ingestion surface. A refactor that inverts a condition (e.g. dropping the
  `is_active` filter, or returning `role` from the wrong column) would grant admin access
  and no test would catch it. For a civic-data project this is a result-integrity exposure,
  not just an access one.
- **Repro / Evidence**: `grep -r "auth/login" backend/tests` → no matches. The endpoint's
  branches at `auth.py:24` (400), `:30` (401 no user), `:32` (401 bad password), `:41`
  (200 with role) are all uncovered.
- **Recommended fix**: Add an integration test class (uses the existing `db_engine`
  fixture): seed one active admin + one inactive user via `flask auth create-user` /
  `User(...)`, then assert 200+role on good creds, 401 on bad password, 401 on inactive,
  400 on missing fields. ~5 assertions, mirrors the `test_developer_api.py` pattern.
- **Effort**: S
- **Tags**: auth, critical-path, regression-gap

### F-603: Result-integrity schema validators have no direct test
- **Severity**: Critical
- **Persona**: Test/CI
- **Surface**: backend
- **Files**: `backend/app/importer/schemas.py:17-47`; `backend/tests/test_importer.py:1-64`
  (only happy-path + unknown-state through `load_csv`)
- **Problem**: `ResultRow` is the schema every imported vote row must pass, and its
  docstring states the intent explicitly: *"Validation errors abort the import — silent
  skips would let bad data into the dataset."* Yet the validators are never exercised
  directly: `votes: Field(ge=0)` (reject negatives), `state_code min/max_length=2`, `cycle
  ge=1999 le=2050`, and the `check_aggregation_consistency` model_validator
  (`schemas.py:38-47`, which requires `pu_code`/`ward_name`/`lga_name` at the right
  aggregation levels) have zero tests. `test_importer.py` only feeds well-formed rows plus
  one unknown state code; it never drives a negative vote, an out-of-range cycle, a
  1-char state code, or an aggregation/field mismatch.
- **Impact**: This is the guard on the project's paramount trust property. If a validator is
  weakened or a malformed-row path silently coerces bad data, corrupted vote counts enter
  the certified dataset and there is no test to stop it. Malformed-row handling — explicitly
  called out as a critical path — is untested.
- **Repro / Evidence**: `test_importer.py` asserts only `rows_imported`/`rows_skipped`
  counts on clean input; no test constructs a `ResultRow` with bad fields or asserts a
  `ValidationError`/`ValueError`. The `check_aggregation_consistency` raises at
  `schemas.py:42,44,46` — all uncovered.
- **Recommended fix**: Add `test_schemas.py` (pure, no DB): parametrized cases asserting
  `pydantic.ValidationError` for negative votes, cycle 1990/2100, 1-char and 3-char
  `state_code`, and each `aggregation` level missing its required lower field; plus one
  positive case per aggregation. Add one `load_csv` case with a malformed numeric `votes`
  cell to prove the loader rejects (not coerces) it.
- **Effort**: M
- **Tags**: result-integrity, importer, critical-path

### F-604: Backend lint is red (84 ruff violations) and blocks the entire test suite
- **Severity**: High
- **Persona**: Test/CI
- **Surface**: backend
- **Files**: `.github/workflows/ci.yml:23-28`; violations across `app/__init__.py:6`,
  `app/models.py:12,20`, `app/ocr/batch.py:23,26,30`, `app/api/overview.py:5,11`,
  `app/api/elections.py:178`, `app/api/states.py:64`, `app/importer/loaders/*`
- **Problem**: The `backend` job runs `ruff check .` before `mypy` and `pytest`. Ruff
  reports 84 violations — mostly trivial `F401` unused imports, two `E741` ambiguous `l`
  variables, one `F841` unused local. Because the step fails, `mypy app` and `pytest -ra`
  **never run**. So even if the workflow were enabled, the well-built analysis, importer,
  gate, and key-lifecycle tests would still not execute — the pipeline stops at a wall of
  auto-fixable lint noise.
- **Impact**: The whole point of the backend job — running the tests — is unreachable. The
  volume and triviality of the violations (mostly `ruff check --fix`-able) indicates the
  pipeline has been red so long that no one is watching it.
- **Repro / Evidence**: CI run `25956451061`, step `Lint`: `app/__init__.py:6:8: F401 'os'
  imported but unused` … 84 total lint diagnostics; step exits 1; `mypy`/`Tests` steps show
  as not-run.
- **Recommended fix**: `cd backend && ruff check --fix .` clears the `F401`/`F841`
  mechanically; rename the two `l` variables by hand. Then keep it green by making `ruff`
  a pre-commit hook. (Separately, `mypy --strict` will likely surface real issues once
  reachable — treat that as a follow-up once lint is green.)
- **Effort**: S
- **Tags**: ci, lint, quick-win

### F-605: Frontend lint is structurally broken — no ESLint config
- **Severity**: High
- **Persona**: Test/CI
- **Surface**: web
- **Files**: `.github/workflows/ci.yml:45` (`npm run lint`);
  `frontend/package.json` (`"lint": "next lint"`, `eslint-config-next` present but no
  `.eslintrc*` / `eslint.config.*` in `frontend/`)
- **Problem**: `next lint` with no ESLint config launches the interactive setup prompt
  ("How would you like to configure ESLint?"). In the non-TTY CI runner it prints the prompt
  and exits 1. There is no `.eslintrc.json`, so the frontend lint step has never passed —
  it is not catching lint issues, it is failing on a missing config.
- **Impact**: The `frontend` job is red on every run for a configuration reason, which
  (together with F-604) keeps the `e2e` job permanently `skipped` (it `needs:
  [backend, frontend]`). No frontend static analysis runs at all.
- **Repro / Evidence**: CI run `25956451061`, step `Run npm run lint`: emits the
  `nextjs.org/docs/basic-features/eslint` setup prompt, then `##[error]Process completed
  with exit code 1`. `ls frontend/.eslintrc*` → no matches.
- **Recommended fix**: Add `frontend/.eslintrc.json` = `{ "extends": "next/core-web-vitals" }`
  (the config `eslint-config-next` already provides), then verify `npm run lint` exits 0
  locally. Consider `next lint --max-warnings=0` to make warnings blocking once clean.
- **Effort**: S
- **Tags**: ci, lint, web, quick-win

### F-606: No merge gate — PRs merged to main while CI was red
- **Severity**: High
- **Persona**: Test/CI
- **Surface**: infra
- **Files**: `.github/workflows/ci.yml` (no `required` semantics); repo branch settings
- **Problem**: Merge commits `#33` (Liquid UI), `#35` (sync coverage), `#36` (coverage
  counts) all landed on `main` while their CI runs were `failure`. There is no evidence of
  required status checks protecting `main` (`gh api …/branches/main/protection` returns no
  required-checks payload). CI is therefore advisory, not blocking — a red pipeline never
  stopped a merge.
- **Impact**: Even after F-601/F-604/F-605 are fixed and the workflow is green, nothing
  enforces that state. The next red PR merges just as easily. A pipeline that can be ignored
  provides governance theatre, not a gate — especially damaging for a public civic-data
  project where a bad merge corrupts published results.
- **Repro / Evidence**: `gh run list` shows `#36`/`#35`/`#33` as `push`/`main` runs with
  `conclusion: failure`, i.e. the PRs merged despite red checks.
- **Recommended fix**: After a green run exists, enable branch protection on `main`
  requiring the `backend` and `frontend` checks (and `e2e` once it's reworked per F-607),
  plus "require branches up to date." Block direct pushes.
- **Effort**: S
- **Tags**: ci, governance, merge-gate

### F-607: The only vote-total-correctness checks never execute in CI
- **Severity**: High
- **Persona**: Test/CI
- **Surface**: infra
- **Files**: `.github/workflows/ci.yml:50-69`; `backend/tools/e2e.py:196-206`
  (`t_pres_standings_match_inec`)
- **Problem**: The strongest integrity assertions in the repo — 2023 Presidential national
  totals matching INEC-certified figures (APC 8,794,726 / PDP 6,984,520 / LP 6,101,533 /
  NNPP 1,496,687) and ENP in the academic 3.2–3.4 band — live only in `e2e.py`, run by the
  `e2e` CI job. That job `needs: [backend, frontend]` (both always fail → `e2e` is
  perpetually `skipped`) and additionally only runs `if push && ref == main`. It has never
  executed. Worse, it probes the **live production deployment** (`E2E_URL`) after a
  `sleep 360`, so even when green it validates prod-at-probe-time, not the merged code, and
  couples `main`'s CI health to a running droplet.
- **Impact**: Result integrity — the paramount trust property — has no automated regression
  gate. The certified-total assertions exist but are inert. Any importer or query regression
  that changed a national total would not be caught pre-merge.
- **Repro / Evidence**: e2e conclusion across recent runs = `skipped`; job condition
  `ci.yml:55` + `needs` at `:56`; probe hits `https://…ondigitalocean.app` at `ci.yml:68`.
- **Recommended fix**: Extract the certified-total assertions into an **integration** test
  that seeds the fixtures and calls the Flask test client (like `test_api_health.py`), so
  correctness is checked against the code under test, pre-merge, with no live dependency.
  Keep the live `e2e` probe as a separate post-deploy smoke job that does not gate the code
  merge.
- **Effort**: M
- **Tags**: result-integrity, e2e, flaky-by-design

### F-608: Scraper IrevClient token-bucket and retry logic untested
- **Severity**: Medium
- **Persona**: Test/CI
- **Surface**: backend
- **Files**: `backend/app/scraper/irev_client.py:48-119`; no test imports `IrevClient` or
  `TokenBucket`
- **Problem**: `TokenBucket.acquire` (refill math, `time.sleep` throttle, `_lock`) and the
  `Retry(total=4, backoff_factor=5, status_forcelist=[429,500,502,503,504])` adapter are the
  scraper's politeness and resilience contract with INEC's live API, and neither is tested.
  `test_calendar.py` covers `decide_mode` (the wake policy) but nothing exercises the client
  itself. A regression that neuters the bucket (hammering INEC on election day) or drops the
  retry list (silent scrape gaps) would ship unseen.
- **Impact**: On election day this is the live data path. Over-requesting risks getting the
  scraper blocked by INEC; lost retries mean missing results during the highest-stakes
  window. Both fail silently.
- **Repro / Evidence**: `grep -r "TokenBucket\|IrevClient" backend/tests` → no matches.
- **Recommended fix**: Unit-test `TokenBucket` with a monotonic-clock monkeypatch: assert
  N+1 rapid `acquire()`s block until refill; assert capacity cap. Test `IrevClient.get`
  against a mocked `requests` transport (e.g. `responses`/`requests_mock`) asserting a 429
  triggers retry and a 200 body returns parsed JSON. Do not mock `IrevClient` itself.
- **Effort**: M
- **Tags**: scraper, reliability, election-day

### F-609: resolve_party normalizer untested — only the static dict is asserted
- **Severity**: Medium
- **Persona**: Test/CI
- **Surface**: backend
- **Files**: `backend/app/importer/normalizers.py:31-58`; `backend/tests/test_normalizers.py:1-19`
- **Problem**: `test_normalizers.py` asserts only the static `HISTORICAL_MAPPING` dict
  (uppercase keys, cycle range, APC-predecessor distinctness). The function that actually
  maps a raw party code to a DB `Party` — `resolve_party`, with its `active_from`/`active_to`
  windowing, `.order_by(...nullslast())` tie-break, and `autocreate` branch — has no test,
  nor does `find_unmapped`. Party-code mapping is a named critical path; the mapping *table*
  is tested but the mapping *logic* is not.
- **Impact**: A party-resolution regression (wrong active window, autocreating a duplicate,
  resolving a reused acronym like CPC/ANPP to the wrong era) silently misattributes votes.
- **Repro / Evidence**: `test_normalizers.py` imports only `HISTORICAL_MAPPING`; no
  reference to `resolve_party`/`find_unmapped`. The `autocreate` branch (`normalizers.py:45-49`)
  and windowing (`:37-40`) are uncovered.
- **Recommended fix**: Add integration tests (uses `db_engine` + `seed`): resolve a code
  valid only in a given cycle window; assert `None` outside the window; assert `autocreate`
  inserts exactly one row; assert a cross-era reused acronym resolves to the correct
  `active_from` record.
- **Effort**: M
- **Tags**: importer, result-integrity

### F-610: API-gate negative / bypass branches untested
- **Severity**: Medium
- **Persona**: Test/CI
- **Surface**: backend
- **Files**: `backend/app/api_gate.py:39-44,70`; `backend/tests/test_developer_api.py:21-37`
- **Problem**: `test_gate_blocks_keyless_but_not_browser_or_exempt` asserts the **pass**
  cases (keyless → 401; `Sec-Fetch-Site: same-origin` passes; matching-host `Referer`
  passes) but never the **block** cases: a `Referer`/`Origin` whose host differs from
  `request.host` must *not* pass, and the `OPTIONS` early-return (`api_gate.py:70`) is
  untested. So `_is_same_origin`'s discriminating behaviour — the whole point of the check —
  is only tested in the direction that returns `True`.
- **Impact**: A regression that makes `_is_same_origin` match too liberally (e.g. substring
  instead of exact host) would let all programmatic traffic bypass the attribution gate, and
  no test would notice. (The gate is documented as an access-management, not security,
  boundary — so this is a correctness/coverage gap, not an auth-bypass claim; the security
  lens is the Adversary/Security persona's.)
- **Repro / Evidence**: The test asserts `.status_code == 200` for same-origin headers but
  has no assertion that a foreign-host `Referer` yields 401; no `client.options(...)` case.
- **Recommended fix**: Add cases: `Referer: http://evil.example/...` (host ≠ request host) →
  401; `Origin` present but mismatched → 401; `OPTIONS /api/states` → not 401. Cheap, pure
  additions to the existing test.
- **Effort**: S
- **Tags**: gate, coverage, quick-win

### F-611: Frontend has zero tests
- **Severity**: Medium
- **Persona**: Test/CI
- **Surface**: web
- **Files**: `frontend/` (no `*.test.*` / `*.spec.*`; no jest/vitest/playwright config —
  only `next.config.mjs`, `postcss.config.mjs`, `tailwind.config.ts`)
- **Problem**: There is no frontend test of any kind. Trust-relevant frontend code ships
  unverified: `src/middleware.ts` (the `/admin` role gate), `src/lib/auth.ts` (NextAuth
  credentials → Flask `/api/auth/login`), and `src/app/admin-api/[...path]/route.ts` (the
  server proxy that injects `X-Admin-Token`). The `frontend` job is build + lint only, and
  lint is broken (F-605) — so build is the sole real check.
- **Impact**: A regression in the admin gate or the admin-token proxy — the frontend half of
  the write-path protection — has no automated catch. `next build` proves it compiles, not
  that the gate gates.
- **Repro / Evidence**: `find frontend -name '*.test.*' -o -name '*.spec.*'` (excl.
  node_modules) → empty; no test runner in `package.json` scripts.
- **Recommended fix**: Add a minimal Playwright (or Vitest + next-test-utils) suite covering
  the two journeys that matter: unauthenticated `/admin` redirects to login; the admin-api
  proxy injects the token and rejects when unauthenticated. Wire it as a CI job.
- **Effort**: M
- **Tags**: web, auth, coverage

### F-612: Integration suite silently skips when Docker is absent → false green
- **Severity**: Low
- **Persona**: Test/CI
- **Surface**: backend
- **Files**: `backend/tests/conftest.py:22-33`
- **Problem**: The session-scoped `pg_url` fixture does `pytest.skip("testcontainers not
  installed")` on `ImportError`, and testcontainers itself skips/errize if the Docker daemon
  is unreachable. A developer (or a misconfigured runner) without Docker gets a **green**
  `pytest` run in which the *entire* `integration`-marked suite — health, gate, apply/approve
  key lifecycle, importer, scraper calendar — is skipped. Nothing asserts a minimum number
  of integration tests actually ran.
- **Impact**: "Tests pass" locally can mean "the trust-critical tests didn't run." Combined
  with `-ra` (which reports skips), the skip is visible but not enforced — easy to miss.
- **Repro / Evidence**: `conftest.py:24-25` `pytest.skip(...)`; all integration test files
  carry `pytestmark = pytest.mark.integration` and depend on `db_engine` → `pg_url`.
- **Recommended fix**: In CI, run integration explicitly and fail if zero ran, e.g.
  `pytest -m integration --strict-markers` in a job that guarantees Docker, and/or a
  session-finish hook asserting `collected integration > 0`. Document that Docker is required
  locally.
- **Effort**: S
- **Tags**: false-green, integration, ci

### F-613: No coverage gate despite pytest-cov being installed
- **Severity**: Low
- **Persona**: Test/CI
- **Surface**: backend
- **Files**: `.github/workflows/ci.yml:27-28`; `backend/requirements-dev.txt:3`
  (`pytest-cov==6.0.0`); `backend/pyproject.toml:26-32`
- **Problem**: `pytest-cov` is a dev dependency but CI runs `pytest -ra` with no `--cov` /
  `--cov-report` / `--cov-fail-under`. Coverage is measured nowhere and enforced nowhere, so
  the critical-path gaps in F-602/F-603/F-608/F-609 could be quantified but aren't. (Note
  commits #35/#36 concern *election-data* "coverage," not test coverage — genuine test
  coverage is unmeasured.)
- **Impact**: New untested code lands without any coverage signal; regressions in coverage
  are invisible.
- **Repro / Evidence**: `ci.yml:28` `run: pytest -ra` — no cov flags; `pyproject.toml`
  `addopts = "-ra --strict-markers"` — no cov config.
- **Recommended fix**: Add `--cov=app --cov-report=term-missing --cov-fail-under=<baseline>`
  once the suite runs green; start the floor at the current measured number and ratchet up.
- **Effort**: S
- **Tags**: coverage, ci

### F-614: No security scanning in CI
- **Severity**: Low
- **Persona**: Test/CI
- **Surface**: infra
- **Files**: `.github/workflows/ci.yml:1-69` (no scan jobs)
- **Problem**: The pipeline has no dependency audit (`pip-audit` / `npm audit`), no secret
  scanning (gitleaks/trufflehog), no SAST (Semgrep/CodeQL), and no container/IaC scan. This
  is a public, open-sourced civic-data repo where committed bcrypt password hashes were
  rotated on 2026-07-18 but **remain in git history** — exactly the class of issue a secret
  scanner is for. New CVEs in Flask/SQLAlchemy/Next.js dependencies would go unflagged.
- **Impact**: Security regressions and leaked-secret patterns land without a tripwire. For a
  public repo, absence of secret + dependency scanning is a notable gap.
- **Repro / Evidence**: No scan steps anywhere in `ci.yml`; brief notes hashes committed
  then rotated 2026-07-18 (still in history).
- **Recommended fix**: Add a lightweight `security` job: `pip-audit` + `npm audit
  --audit-level=high` on PRs, gitleaks on push (full history once), and enable GitHub code
  scanning (CodeQL) for JS/Python. Non-blocking to start, then block on new criticals.
- **Effort**: M
- **Tags**: security, ci, secrets

---

## Test posture verdict

**Would I ship to production on a Friday afternoon based on a green build alone? No — and
here the question is moot, because there is no build to be green.** CI is disabled, HEAD
carries zero checks, and the last time the pipeline ran it was red at lint on every commit
while merges sailed through anyway. The analysis math and the developer-key lifecycle are
genuinely well-tested with real known-value assertions against a real Postgres (testcontainers,
not mocks) — that part is good engineering. But the trust-critical paths this project exists
to protect are exposed: admin login has no test, the result-integrity validators have no
direct test, and the only certified-vote-total assertions live in a job that has never
executed. The fastest path back to a trustworthy signal is mechanical: `ruff --fix` +
add a Next ESLint config (both S), re-enable the workflow, then close the auth and
result-integrity coverage gaps (F-602, F-603) before making the checks a required merge gate.
