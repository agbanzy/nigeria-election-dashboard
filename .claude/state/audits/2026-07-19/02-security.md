# Security audit — Nigeria Election Dashboard — 2026-07-19

**Persona:** Security (F-201…) · **Auditor lens:** senior appsec, production-realistic risk

## Executive summary

The dashboard's public read surface is largely sound: queries are parameterized (no SQL injection reachable from request data), there is no unsafe deserialization (`raw_json` is JSONB, no `pickle`/`eval`/`yaml.load`), Next.js 14.2.35 already patches the middleware-auth-bypass CVE, and no live secrets are committed to the tree. The paramount trust property — election-result integrity — is **not** adequately protected, however. The admin write API (`/api/admin/*`) is routed **directly to Flask on the public internet** by `.do/app.yaml`, and its only guard, `_require_admin()`, **fails open**: when `ADMIN_TOKEN` is unset it authorizes everyone — and the committed deploy spec neither sets nor documents that secret. That single combination lets an unauthenticated remote caller falsify vote tallies. Secondary issues compound it: an unauthenticated SSRF in the OCR endpoint, zero rate-limiting on the internet-reachable admin login (unbounded brute force), wildcard CORS on all `/api/*`, and plaintext API-key storage. **The free-API gate is bypassable** — it trusts client-controlled `Sec-Fetch-Site`/`Origin`/`Referer` headers — but this is Low severity because the gated data is free by design and the gate does not protect admin.

## Severity counts

| Severity | Count | IDs |
|---|---|---|
| Critical | 1 | F-201 |
| High | 2 | F-202, F-203 |
| Medium | 3 | F-204, F-205, F-206 |
| Low | 4 | F-207, F-208, F-209, F-210 |
| **Total** | **10** | |

---

### F-201: Fail-open admin auth + publicly-routed `/api/admin/*` → unauthenticated remote election-result falsification
- **Severity**: Critical
- **Persona**: Security
- **Surface**: backend + infra
- **Files**: `backend/app/api/admin.py:43-51`, `112-197` (submit_results), `252-314` (import_results), `330-382` (api-clients read + decision); `.do/app.yaml:18-20` (route `/api` → Flask, `preserve_path_prefix`); `backend/app/api_gate.py:28-34` (`/api/admin` is gate-exempt)
- **Problem**: `_require_admin()` returns `True` when `ADMIN_TOKEN` is empty (`admin.py:44-47` — "not configured → allow"). `.do/app.yaml` sets **no** `ADMIN_TOKEN` on the `web` service (envs are only DATABASE_URL, IREV_API_BASE, SCRAPER_DEFAULT_STATE_ID, ENV, LOG_LEVEL) and — unlike `NEXTAUTH_SECRET` and `SEED_USERS`, which carry explicit "set via console" reminders — gives no hint the operator must inject it. The DO ingress routes `/api/*` (which includes `/api/admin/*`) straight to Flask, so the Next.js proxy's session check in `admin-api/[...path]/route.ts` is not in the path at all — an attacker simply calls Flask directly. The result: if `ADMIN_TOKEN` is unset, `POST /api/admin/results` and `/api/admin/import` accept arbitrary per-party vote tallies with no authentication, and both flip `election.status` to `live` so the falsified rows surface on the choropleth/comparison (`admin.py:194-197, 312-313`). `test_developer_api.py:63` confirms the fail-open ("ADMIN_TOKEN unset in tests → admin endpoints open").
- **Impact**: Full remote compromise of the project's core trust property. An unauthenticated attacker can inject, overwrite, or (via the pre-insert `delete`, `admin.py:160-167, 280-285`) wipe vote tallies for any election, auto-create junk parties/sources (`resolve_party(..., autocreate=True)`), read every API applicant's email + plaintext key (`GET /api/admin/api-clients`), and revoke legitimate keys (`/api/admin/api-clients/<id>/decision`). Falsified "certified" civic data is the highest-impact failure mode named in the brief.
- **Repro / Evidence**:
  ```python
  def _require_admin() -> bool:
      expected = os.environ.get("ADMIN_TOKEN", "")
      if not expected:
          return True  # not configured → allow  ← fail-OPEN
      return request.headers.get("X-Admin-Token", "") == expected
  ```
  ```
  # No token needed when ADMIN_TOKEN is unset; /api/admin is gate-exempt and publicly routed:
  curl -s https://elections.innoedgetech.com/api/admin/api-clients            # dumps emails + keys
  curl -s -X POST https://elections.innoedgetech.com/api/admin/results \
       -H 'Content-Type: application/json' \
       -d '{"election_id":<id>,"scope":"state","results":[{"party_code":"XYZ","votes":49999999}]}'
  # → {"ok":true,"inserted":1,"scope":"state"} ; election flips to "live", choropleth updates
  ```
- **CVSS estimate**: ~9.1 Critical (est.) — `AV:N/AC:L/PR:N/UI:N/S:C/C:L/I:H/A:L`. Scope=changed because falsified data misleads downstream consumers/newsrooms.
- **Exploit scenario**: On election night a bad actor scripts `POST /api/admin/import` across the live governorship elections, seeding a fabricated lead for one party. The dashboard — presented as certified aggregation — renders the fake margins; screenshots circulate as "official results," creating a real-world disinformation incident. No credential, no session, no phishing required.
- **Remediation snippet**:
  ```python
  # 1) Fail CLOSED — never authorize when the token is absent/misconfigured.
  def _require_admin() -> bool:
      expected = os.environ.get("ADMIN_TOKEN", "")
      if not expected:
          app.logger.error("ADMIN_TOKEN unset — refusing admin write")
          return False
      given = request.headers.get("X-Admin-Token", "")
      return bool(given) and hmac.compare_digest(given, expected)  # constant-time
  ```
  ```yaml
  # 2) .do/app.yaml — make it a required SECRET on the web service (and keep the frontend copy in sync):
  - key: ADMIN_TOKEN
    scope: RUN_TIME
    type: SECRET
  ```
  Defense-in-depth: have the Caddy front-proxy (or DO ingress) block public `/api/admin` and `/api/scrape` so those blueprints are reachable only via the authenticated Next.js proxy. Apply the same fail-closed fix to `scrape.py` (see F-209).
- **Detection signal**: Alert on any `POST /api/admin/*` whose source IP is not the frontend service's internal address; alert on `elections.status` transitions `historical→live` outside a scheduled window; alert on startup when `ADMIN_TOKEN` is empty in `production`.
- **Effort**: S (code) / M (infra route lockdown)
- **Tags**: auth, broken-access-control, fail-open, data-integrity, quick-win, infra

---

### F-202: Unauthenticated SSRF (+ image/memory DoS) via `POST /api/admin/ocr` `image_url`
- **Severity**: High
- **Persona**: Security
- **Surface**: backend
- **Files**: `backend/app/api/admin.py:204-245` (esp. `219` validation, `222` fetch, `225` error echo); sink also at `backend/app/ocr/batch.py:129`
- **Problem**: `ocr_ec8a` server-side-fetches a caller-supplied URL with only `str(url).startswith("http")` as validation — no host allow-list, no private-IP/DNS-rebinding guard, no redirect cap. `requests.get(str(url), timeout=30)` will happily reach `http://169.254.169.254/…` (cloud metadata), `http://web:8080/…` (the internal Flask service), `http://localhost`, and RFC1918 hosts. The fetched bytes are then handed to Pillow `Image.open` (`ocr/ec8a.py:75`) with no `MAX_IMAGE_PIXELS` cap, and `resp.content` buffers the whole body with no size limit. Gated only by `_require_admin()` → unauthenticated whenever F-201 holds. The endpoint also echoes the raw exception (`f"image fetch failed: {exc}"`), turning it into an SSRF oracle (connection-refused vs. timeout vs. resolved distinguishes live internal hosts/ports).
- **Impact**: Internal network reconnaissance and reach into services never meant to be internet-facing; potential retrieval of instance metadata / internal config depending on the DO App Platform network posture; memory-exhaustion DoS via a decompression bomb or multi-GB response.
- **Repro / Evidence**:
  ```
  curl -X POST https://elections.innoedgetech.com/api/admin/ocr \
       -H 'Content-Type: application/json' \
       -d '{"image_url":"http://169.254.169.254/metadata/v1.json"}'
  # error text distinguishes reachable vs unreachable internal targets (SSRF oracle)
  ```
- **CVSS estimate**: ~7.7 High (est.) — unauth path `AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:L` ≈ 8.2; if `ADMIN_TOKEN` is set (PR:H) ≈ 6.5. Range 6.5–8.2.
- **Exploit scenario**: Attacker enumerates `http://web:8080/api/...`, `http://localhost:5432`, `169.254.169.254`, and RFC1918 space using error-timing, mapping the internal topology; then feeds a 50k×50k PNG to spike the OCR worker's memory and knock the web dyno over during a live election.
- **Remediation snippet**:
  ```python
  import ipaddress, socket
  from urllib.parse import urlparse

  ALLOWED_HOSTS = {"www.inecelectionresults.ng", "lv001-r.inecelectionresults.ng"}

  def _safe_public_url(raw: str) -> str:
      u = urlparse(raw)
      if u.scheme != "https" or u.hostname not in ALLOWED_HOSTS:
          raise ValueError("image_url host not allowed")
      for res in socket.getaddrinfo(u.hostname, 443):
          ip = ipaddress.ip_address(res[4][0])
          if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
              raise ValueError("resolves to non-public address")
      return raw
  # fetch with allow_redirects=False, stream=True + byte cap; set Image.MAX_IMAGE_PIXELS.
  # Return a generic error string, not exc, to close the oracle.
  ```
- **Detection signal**: Egress from the web/worker container to RFC1918/169.254.0.0/16/loopback; spikes in `/api/admin/ocr` 502s; OCR worker OOM/restart events.
- **Effort**: M
- **Tags**: ssrf, A10, dos, input-validation, info-disclosure

---

### F-203: No rate-limiting / anti-automation on the internet-reachable admin login → unbounded credential brute force
- **Severity**: High
- **Persona**: Security
- **Surface**: backend
- **Files**: `backend/app/api/auth.py:18-48`; reachable because `api_gate.py:28-34` exempts `/api/auth` and `.do/app.yaml:18-20` routes `/api/*` straight to Flask
- **Problem**: `POST /api/auth/login` has no attempt throttling, no account lockout, no exponential backoff, no CAPTCHA, and no IP budget anywhere in the stack (no `flask-limiter`, no proxy-level limit observed). Although NextAuth normally calls it server-side over the internal `http://web:8080`, the same endpoint is also directly reachable at `https://elections.innoedgetech.com/api/auth/login`. bcrypt slows each guess but is not a substitute for anti-automation, and commit `861b6e9` ("reset both passwords to clean alphanumeric") suggests admin passwords are simple.
- **Impact**: An attacker can run an unlimited online dictionary/credential-stuffing attack against admin accounts. A cracked admin password yields a legitimate `role=admin` NextAuth session → full result-falsification via the intended admin path (independent of the F-201 fail-open).
- **Repro / Evidence**: `for pw in wordlist: POST /api/auth/login {email, password} → 200 on hit`. No 429 is ever returned (`auth.py` returns only 400/401/200).
- **CVSS estimate**: ~7.3 High (est.) — `AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N`; strongly dependent on password strength.
- **Exploit scenario**: Attacker scrapes the admin email from git history / OSINT, runs a 10k-password run against `/api/auth/login`, lands a "clean alphanumeric" password, signs into `/admin`, and edits tallies through the sanctioned UI — indistinguishable from a legitimate admin in logs.
- **Remediation snippet**:
  ```python
  from flask_limiter import Limiter
  limiter = Limiter(key_func=lambda: request.remote_addr)
  @bp.post("/api/auth/login")
  @limiter.limit("5 per minute; 30 per hour")
  def login(): ...
  # + lockout after N failures per account, enforce strong admin passwords, add MFA for admin.
  ```
- **Detection signal**: Burst of 401s from one IP/subnet on `/api/auth/login`; logins from new ASNs/geos; velocity alerts on distinct emails tried per IP.
- **Effort**: M
- **Tags**: auth, A07, brute-force, rate-limiting, missing-control

---

### F-204: Wildcard CORS on all `/api/*` (auth + admin included)
- **Severity**: Medium
- **Persona**: Security
- **Surface**: backend + infra
- **Files**: `backend/app/config.py:60` (`cors_origins` default `"*"`); `backend/app/__init__.py:23` (`CORS(app, resources={r"/api/*": {"origins": cfg.cors_origins}})`); `.do/app.yaml` sets no `CORS_ORIGINS`, so production runs with `*`
- **Problem**: The CORS origin allow-list defaults to `*` and is not overridden in the deploy spec, so every `/api/*` route — including `/api/auth/login`, `/api/developer/*`, and `/api/admin/*` — returns `Access-Control-Allow-Origin: *`. For the public read data this is acceptable, but applying it uniformly means any website can (a) read login/response JSON cross-origin and (b), combined with F-201's tokenless admin, drive a visitor's browser to `POST /api/admin/results` as a cross-origin request (no credentials needed, so `*` is honored). Because the admin guard is a custom header rather than a cookie, wildcard CORS is what turns the fail-open into a browser-drive-by rather than only a server-side call.
- **Impact**: Amplifies F-201 to a drive-by (any page a target visits can submit falsified results); leaks the shape/role of auth responses cross-origin.
- **Repro / Evidence**: `config.py:60 cors_origins=os.environ.get("CORS_ORIGINS", "*")`; no `CORS_ORIGINS` key anywhere in `.do/app.yaml`.
- **CVSS estimate**: ~5.8 Medium (est.) — `AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N` (UI:R because the victim must load a page).
- **Exploit scenario**: A viral "results tracker" blog embeds JS that fires cross-origin `POST`s to `/api/admin/import`; every reader silently contributes a falsification request.
- **Remediation snippet**:
  ```yaml
  - key: CORS_ORIGINS
    scope: RUN_TIME
    value: "https://elections.innoedgetech.com"
  ```
  Scope CORS to the public read blueprints only; never emit permissive CORS on `/api/admin` or `/api/auth`. Change the `config.py` default to the canonical origin, not `*`.
- **Detection signal**: `Origin` headers on `/api/admin` requests; cross-origin preflights (`OPTIONS`) hitting admin/auth paths.
- **Effort**: S
- **Tags**: cors, A05, misconfig, defense-in-depth

---

### F-205: API keys and application refs stored and served in plaintext; non-constant-time comparison
- **Severity**: Medium
- **Persona**: Security
- **Surface**: backend
- **Files**: `backend/app/models.py:60-61` (`api_key`, `application_ref` plain `Text`); `backend/app/api/developer.py:35-36` (`_new_key`), `96-98` (`/status` returns key), `admin.py:350` (list returns key); `api_gate.py:47-59` (`api_key == key` SQL equality)
- **Problem**: Issued keys (`ned_` + `secrets.token_hex(24)`, ~192-bit — entropy is fine) and the retrieval `application_ref` are persisted in cleartext on the **shared** `apcng-db` cluster and returned verbatim by `/api/developer/status` and `/api/admin/api-clients`. There is no hash-at-rest (should store only a SHA-256/HMAC and compare that). Lookup is a plain SQL equality (`ApiClient.api_key == key`), not an app-level constant-time compare; not practically exploitable at 192-bit but still a deviation. A DB backup leak, log capture, or the F-201 admin read exposes every key at once.
- **Impact**: Credential disclosure on data-at-rest compromise; keys grant only free data, so blast radius is attribution/abuse rather than confidentiality — hence Medium, not High.
- **Repro / Evidence**: `models.py:60 api_key: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)` — no hashing anywhere; `developer.py:98 out["api_key"] = client.api_key`.
- **CVSS estimate**: ~5.3 Medium (est.) — `AV:N/AC:H/PR:H/UI:N/S:U/C:H/I:N/A:N` (requires DB/admin access).
- **Exploit scenario**: A leaked nightly dump of the shared cluster hands an attacker every live API key and applicant email in cleartext, ready for immediate reuse/abuse under legitimate-looking identities.
- **Remediation snippet**:
  ```python
  # Store: key_hash = hashlib.sha256(raw_key.encode()).hexdigest(); show raw once.
  # Verify: where(ApiClient.key_hash == sha256(presented)) then hmac.compare_digest(...)
  ```
- **Detection signal**: Access to `api_clients` outside the admin proxy; the same key seen from many disparate IPs (shared/leaked key).
- **Effort**: M
- **Tags**: A02, crypto-at-rest, secrets, timing

---

### F-206: Committed bcrypt hashes of simple admin passwords remain in public git history
- **Severity**: Medium
- **Persona**: Security
- **Surface**: shared (repo)
- **Files**: `backend/app/seed_users.py` at commits `6be60a3` ("Add login-based auth system") and `861b6e9` ("seed_users: … reset both passwords to clean alphanumeric"), before the env-based refactor `5dd2b04`
- **Problem**: Admin/user bcrypt hashes were hardcoded in `seed_users.py` and committed. They were rotated 2026-07-18, but the repo is **public** and git history is permanent, so the old hashes remain fetchable by anyone (`git log -p`). The commit message states the passwords were "clean alphanumeric," i.e. low-entropy and realistically crackable offline. (Values not reproduced here per audit rules.)
- **Impact**: Offline cracking of the historical hashes; if any of those passwords were reused for the current admin, or elsewhere by the same operator, it becomes a live credential. Reduced from High to Medium by the rotation — contingent on true rotation to a strong, unique password.
- **Repro / Evidence**: `git log --all -S password_hash -- backend/app/seed_users.py` surfaces the commits; `git show 861b6e9` shows the hash literals in the diff.
- **CVSS estimate**: ~5.9 Medium (est.) — `AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N`, conditional on password reuse.
- **Exploit scenario**: Attacker pulls the old hash from history, cracks the alphanumeric password in minutes with hashcat, and tries it against `/api/auth/login` (which, per F-203, has no rate limit).
- **Remediation snippet**: Confirm the current admin password is strong, unique, and unrelated to any historical value. Optionally scrub history (`git filter-repo --path backend/app/seed_users.py --invert-paths` on the affected range, or BFG) and force-push — but treat all historical hashes as permanently disclosed regardless.
- **Detection signal**: Successful `/api/auth/login` following the brute-force pattern in F-203; leaked-credential monitoring on the admin email.
- **Effort**: S (rotate/verify) / M (history rewrite)
- **Tags**: secrets, A07, git-history, oss-hygiene

---

### F-207: Free-API gate is bypassable — it trusts client-controlled `Sec-Fetch-Site`/`Origin`/`Referer`
- **Severity**: Low
- **Persona**: Security
- **Surface**: backend
- **Files**: `backend/app/api_gate.py:39-44` (`_is_same_origin`), `62-100` (gate)
- **Problem**: `_is_same_origin()` returns `True` if `Sec-Fetch-Site: same-origin` is present, or if `Origin`/`Referer`'s host equals `request.host`. All three are request headers fully controlled by a non-browser client, so any programmatic caller sends one and skips the key requirement entirely. **The gate is therefore bypassable.** This is rated Low, not higher, because: the gate's own docstring calls it "an access-management signal, not a security boundary"; every endpoint behind it is free public election data; and `/api/admin` + `/api/auth` are gate-exempt, so the bypass grants nothing beyond what is already free. The only real loss is attribution/contactability, and any future abuse-control (rate-limit, quota) built on this gate would inherit the bypass.
- **Impact**: Anonymous unattributed API use; would become material only if rate-limiting/billing is ever layered on the gate.
- **Repro / Evidence**:
  ```
  curl -H 'Sec-Fetch-Site: same-origin' https://elections.innoedgetech.com/api/states   # 200, no key
  curl -H 'Origin: https://elections.innoedgetech.com' https://elections.innoedgetech.com/api/states  # 200
  ```
- **CVSS estimate**: ~3.1 Low (est.) — `AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N`.
- **Exploit scenario**: A scraper bypasses key issuance forever by pinning one static header; usage is never attributable to a contactable party.
- **Remediation snippet**: Accept the design as "attribution, not security" (document it as such and drop the pretense), OR if attribution matters, require a key for all programmatic access and identify the dashboard by a server-injected shared secret the browser never sees (e.g. the Next.js data layer proxies read calls and adds an internal header), not by spoofable fetch metadata.
- **Detection signal**: High request volume carrying `Sec-Fetch-Site: same-origin` but lacking the browser's full header/TLS-fingerprint profile.
- **Effort**: S (accept/document) / M (real attribution)
- **Tags**: broken-access-control, spoofable-header, by-design, low-impact

---

### F-208: Applicant email enumeration + unauthenticated PII harvest; no rate-limit on `/api/developer/*`
- **Severity**: Low
- **Persona**: Security
- **Surface**: backend
- **Files**: `backend/app/api/developer.py:53-64` (409 leaks existence + status), `84-98` (`/status`), no throttle on `apply`/`status`; cross-ref `admin.py:330-359` (`/api/admin/api-clients` dumps all emails/use-cases/keys under F-201 fail-open)
- **Problem**: `POST /api/developer/apply` returns `409 {"error":"an application for this email already exists","status":...}`, confirming whether a given email has applied and its decision state — an enumeration oracle. Neither `apply` nor `status` is rate-limited, so an attacker can enumerate emails and spam junk pending rows (storage/DoS-lite). Under F-201, `GET /api/admin/api-clients` additionally exposes every applicant's email + use_case (PII) with no auth.
- **Impact**: Minor PII disclosure / applicant enumeration; junk-row flooding.
- **Repro / Evidence**: `developer.py:56-63` returns the existence + status; no limiter decorator anywhere.
- **CVSS estimate**: ~4.0 Low (est.) — `AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N`.
- **Exploit scenario**: Attacker probes a list of journalist/NGO emails to learn who has API access, then targets them; separately floods `apply` to bloat the pending queue.
- **Remediation snippet**: Return an identical `202 "if this email is new, an application was created"` for both new and duplicate; rate-limit `apply`/`status` per IP; never expose applicant emails outside an authenticated admin path.
- **Detection signal**: Many 409s from one IP; rapid growth of `pending` rows.
- **Effort**: S
- **Tags**: enumeration, pii, rate-limiting, A01

---

### F-209: Same fail-open `_require_admin` anti-pattern in the scrape operator endpoints
- **Severity**: Low
- **Persona**: Security
- **Surface**: backend
- **Files**: `backend/app/api/scrape.py:21-27` (fail-open), `29-62` (`/status` unauthenticated read), `65-83` (`/trigger`)
- **Problem**: `scrape.py` duplicates the fail-open guard (`if not expected: return True`). `/api/scrape/status` is unauthenticated regardless (leaks scrape mode, active states, next-event schedule, last-log). `/trigger` is fail-open but is a Phase-A no-op (returns 202 without acting), so impact is limited today — but the pattern is a latent hazard the moment it does real work, and it shares the F-201 root cause.
- **Impact**: Minor operational info disclosure now; latent unauth trigger if Phase B wires it up without fixing the guard.
- **Repro / Evidence**: `curl https://elections.innoedgetech.com/api/scrape/status` → mode/schedule JSON, no auth.
- **CVSS estimate**: ~3.5 Low (est.) — `AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N`.
- **Exploit scenario**: Attacker reads the wake schedule to time other actions; post-Phase-B, an unfixed guard allows anonymous scrape triggering.
- **Remediation snippet**: Apply the shared fail-closed `_require_admin` (F-201) here too; require admin for `/status` or strip sensitive fields.
- **Detection signal**: `/api/scrape/*` requests from non-internal IPs.
- **Effort**: S
- **Tags**: fail-open, info-disclosure, consistency, defense-in-depth

---

### F-210: Verbose exception strings returned to callers (SSRF / DB oracle)
- **Severity**: Low
- **Persona**: Security
- **Surface**: backend
- **Files**: `backend/app/api/admin.py:225` (`f"image fetch failed: {exc}"`), `backend/app/analysis/refresh.py:56` (`f"skipped: {exc}"`), `backend/app/db.py:91` (`healthcheck` returns `str(exc)`)
- **Problem**: Several paths surface raw exception text to the client. The OCR one (`admin.py:225`) is the sharpest — it powers the F-202 SSRF oracle — but returning DB/driver error strings anywhere risks leaking schema, host, or path detail. Health-check error text (`db.py:91`) is exposed via `/api/health`.
- **Impact**: Internal detail disclosure aiding recon; SSRF target discrimination.
- **Repro / Evidence**: `admin.py:224-225 except Exception as exc: return jsonify({"error": f"image fetch failed: {exc}"}), 502`.
- **CVSS estimate**: ~3.5 Low (est.) — `AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N`.
- **Exploit scenario**: Attacker reads driver/connection errors to fingerprint internal hosts, ports, and the DB stack.
- **Remediation snippet**: Return generic client messages; log the detail server-side with a correlation id. `return jsonify({"error": "image fetch failed"}), 502`.
- **Detection signal**: Spikes of 502/500 with distinct internal error signatures.
- **Effort**: S
- **Tags**: info-disclosure, A09, hardening

---

## What is NOT vulnerable (verified negatives)

- **SQL injection**: none reachable from request data. All request-driven queries use SQLAlchemy ORM / bound parameters (`analysis.py:67-78` uses `:cycle`/`:etype` bind params with constant column/table names). The two f-string SQL spots interpolate only trusted, non-request values — `db.py:52` uses the operator-set `DB_SCHEMA` env, `refresh.py:46` uses the `EXPECTED_MVS` constant tuple — so they are not remotely injectable (still worth switching to identifier quoting for hygiene).
- **Unsafe deserialization**: none. No `pickle`/`marshal`/`yaml.load`/`eval`/`exec` in the backend; `raw_json`/cache bodies are JSONB parsed via `resp.json()`.
- **Mass assignment**: not present. `submit_results`/`import_results` construct `ElectionResult` from explicitly named, `_as_int`-coerced fields with a `VOTE_CEILING` guard — no `**body` splat. (Auto-creation of parties/sources is a data-pollution vector, but only behind the F-201 hole.)
- **Importer SSRF (Wikidata/Stears/Dataphyte/INEC-PDF)**: not live — all four loaders are stubs that `raise NotImplementedError` (`loaders/{wikidata,stears,dataphyte,inec_pdf}.py`); `/api/admin/import` takes inline `rows`, not a URL. The only request-driven server-side fetch is the OCR endpoint (F-202).
- **Next.js middleware-auth-bypass CVE-2025-29927**: patched — `next 14.2.35` (> 14.2.25). The admin proxy (`route.ts`) also re-checks the session with `getServerSession`, so admin does not rely on middleware alone.
- **Committed live secrets**: none found in the working tree; no `.env` (non-example) ever tracked; no API keys/AWS keys/private keys in history (only the bcrypt hashes of F-206). INEC `x-api-key` in `irev_client.py:33` is INEC's public SPA key, correctly documented as non-secret.

## Threat-model verdict

**Resilient to:** SQL injection, unsafe deserialization, mass assignment, importer SSRF, the Next.js middleware CVE, and casual secret leakage from the tree. The public read API is safe to expose.

**NOT resilient to:** a network attacker targeting result integrity. The combination of a **fail-open admin guard**, `/api/admin/*` **routed directly to the public internet**, a deploy spec that **does not set `ADMIN_TOKEN`**, **wildcard CORS**, an **unauthenticated OCR SSRF**, and an **unthrottled admin login** means an unauthenticated (or lightly-motivated) remote actor can falsify or destroy election tallies — the single worst outcome for a civic-data project. Even granting that `ADMIN_TOKEN` may be set in the DO console today, the design is fail-open by default and one misconfiguration away from full compromise; it must be made fail-closed and network-isolated before this is trustworthy. Fixing F-201 (fail-closed + route lockdown), F-202 (SSRF allow-list), and F-203 (login rate-limit) collapses the critical attack surface; F-204–F-206 close the amplifiers.
