# VELXTRIA V59 — Render deployment gate

Status: **NOT READY FOR PRODUCTION**. This branch is isolated from `main`; it does not deploy V59.

## Verified current configuration
- `render.yaml`: Python web service, `python portal.py`, `/healthz`, `render-preview`, free plan.
- The V59 ZIP supplied in chat is a **local-only** extension, not present in the repository's `main` branch.
- Its `ascension_suite_v59.py` uses SQLite-specific SQL and creates tables on first use.
- Its `portal.py` V59 GET and POST routes require `VELXTRIA_LOCAL_STUDIO=1` and reject `persistent.REMOTE`.
- `persistent.py` uses PostgreSQL when `VELXTRIA_DATABASE_URL` is configured, and requires private Supabase storage credentials for remote mode.
- Render Free filesystem is not an appropriate persistent production database for V59 customer data.

## Required before merge
1. Port V59 schema to PostgreSQL with versioned, tested migrations; avoid automatic SQLite DDL on request paths.
2. Preserve tenant membership checks for all V59 read/write operations and test cross-tenant access.
3. Remove V59's local-only gate **only after** PostgreSQL compatibility and production authorization tests pass.
4. Test the existing portal, login, payments/licensing, and current Render preview password behavior.
5. Confirm production database and storage are configured in Render; do not place secrets in GitHub.
6. Use a staging Render service or isolated database to test migration and rollback before deploying to the live service.
7. Configure an actual dependency install build command if required by the app; `compileall` only checks Python syntax.
8. Keep `main` unchanged until deployment verification and explicit approval.

## Current scope
This branch currently documents the deployment gate; **it does not contain the V59 application files** and is not deployable as V59. The source ZIP from the conversation must be integrated, adapted, and tested first.
