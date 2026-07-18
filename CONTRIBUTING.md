# Contributing

Issues and PRs are welcome — bug reports, data corrections, new historical
datasets, and features alike.

## Dev setup

Follow the **Local dev** section of the [README](README.md). Backend deps are
pinned in `backend/requirements-dev.txt`; the frontend uses `npm ci`.

## Quality gates

CI runs on every PR and must pass:

- **Backend:** `ruff check .`, `mypy app`, `pytest` (integration tests boot a
  real Postgres via testcontainers — no mocked database).
- **Frontend:** `next lint` and a production build.

Run them locally before pushing. New behavior needs a test; bug fixes need a
regression test.

## Data contributions

Historical results go through the importer, not raw SQL:

1. Every row must conform to `app.importer.schemas.ResultRow`.
2. Cite the source (`--source`, `--url`) and its license (`--license`).
3. Unmapped party codes abort the import — extend
   `app.importer.normalizers.HISTORICAL_MAPPING` in the same PR.
4. Only INEC-certified totals; note provenance caveats in the PR description
   so `/methodology` can be updated.

## Ground rules

- No credentials in code or fixtures — not even bcrypt hashes. Auth users come
  from the `SEED_USERS` env var (see `backend/.env.example`).
- Keep PRs focused; one concern per PR.
- The scraper is deliberately polite (token-bucket rate limiting against INEC
  IReV). Don't raise default rates in a PR.
