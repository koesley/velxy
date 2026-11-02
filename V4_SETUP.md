# VELXY V4 — Free persistent storage test

This package was upgraded from the uploaded V3 repository. It retains the V3 UI, CSV processing, account login, Payhip staging (no automatic paid access), and optional SMTP delivery.

## Before deploying

**Keep your current V3 service as a backup.** Prefer a new `v4-test` GitHub branch and a separate Render free web service, if your free service allowance permits. Do not overwrite `main` until tests pass. Existing V3 SQLite accounts and report ZIPs are NOT automatically migrated.

1. In Supabase VELXY-V4, confirm Storage bucket `velxy-reports` exists and is **private**.
2. In the V4 Render test service, set the following environment variables using Render's secret settings (never commit them):
   - `VELXTRIA_DATABASE_URL`: Supabase **Session pooler** PostgreSQL URI with a properly percent-encoded password.
   - `VELXTRIA_SUPABASE_URL`: `https://<project-ref>.supabase.co`
   - `VELXTRIA_SUPABASE_SERVICE_KEY`: Supabase **server-side secret key** (`sb_secret_...`) or supported legacy service_role key.
   - `VELXTRIA_REQUIRE_PERSISTENCE`: `1`
   - `VELXTRIA_SUPABASE_BUCKET`: `velxy-reports` (optional; this is the default).
   - `VELXTRIA_DEPLOYMENT_MODE`: `render-preview`
   - `VELXTRIA_PREVIEW_PASSWORD`: strong private preview password.
3. Build command: `pip install -r requirements.txt && python -m compileall -q .`
4. Start command: `python portal.py`.
5. Deploy V4 and inspect Render logs. It should say `database=postgresql; storage=private-supabase`. If credentials are missing or the DB cannot be reached, the service should fail startup instead of using SQLite.
6. In Supabase Table Editor (`public`), confirm `users`, `sessions`, `reports`, `deliveries`, `payhip_events` appear.
7. Create a NEW test account (the previous SQLite users were not migrated), upload a non-sensitive test CSV, and download the ZIP. Confirm a file is in the private `velxy-reports` bucket and the report metadata is in `reports`.
8. Redeploy V4; sign in and download the SAME report again. This is the persistence acceptance test.

## Security and limits

- Keep the bucket private; do not add public-read policies. The backend reads ZIPs using the server-only key and checks the authenticated report owner before downloads.
- Keep the preview behind its existing Basic Auth password. This is a **test prototype**, not audited production software; do not use real customer data.
- Free Render services sleep, and free Supabase projects can pause or hit storage/database limits. No zero-cost platform guarantees permanent availability or unlimited retention. Keep independent backups.
- PostgreSQL is selected whenever `VELXTRIA_DATABASE_URL` is configured. SQLite remains only for local development without a database URL. With `VELXTRIA_REQUIRE_PERSISTENCE=1`, missing credentials stop startup.
- Payhip events remain staging-only and never grant paid access automatically.
- `requirements.txt` adds the free open-source psycopg PostgreSQL driver.
- No database or files from your existing V3 installation are automatically transferred.

## Rollback

Repoint the test deployment to the saved V3 commit or stop the test service. Do not delete Supabase data during rollback. The old V3 service and its existing SQLite data should be treated as separate from the V4 project.

## Verification scope

Locally verified: Python compilation, SQLite schema, basic record insertion, local ZIP store/retrieve. **Not verified:** a real Supabase PostgreSQL connection, private Storage API calls, full browser end-to-end flow, and persistence across Render redeploys. These require your live environment.
