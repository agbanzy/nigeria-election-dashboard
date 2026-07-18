# Security Policy

## Reporting a vulnerability

Email **godwin@innoedgetech.com** with details and, if possible, a
reproduction. Please do **not** open a public issue for security reports.
You'll get an acknowledgement within 72 hours.

In scope: this codebase and the live deployment at
https://elections.innoedgetech.com (read-only probing only — no destructive
testing, no denial-of-service, no access attempts against other tenants of
the hosting infrastructure).

## Design notes

- The dashboard is login-gated (NextAuth credentials → Flask `/api/auth/login`
  → bcrypt against the users table). No credentials are stored in this repo;
  users are provisioned via the encrypted `SEED_USERS` env var or the
  `flask auth create-user` CLI.
- Admin write endpoints are gated by `X-Admin-Token` (`ADMIN_TOKEN` env),
  injected server-side by a Next.js proxy that first verifies the NextAuth
  admin session — the token never reaches the browser.
- The INEC IReV "API key" in `backend/app/scraper/irev_client.py` is INEC's
  public Angular SPA client key, not a secret.
