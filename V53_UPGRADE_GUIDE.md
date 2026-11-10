# VELXTRIA V53 — Project Sentinel

V53 adds a read-only, workspace-scoped evidence integrity audit for existing experiment workflows. It checks sampled records for missing baselines, missing follow-ups, missing delivery plans, overdue milestones, and blocked milestones. Results are descriptive and may be incomplete due to upstream sampling limits.

## Upgrade
1. Back up your existing SQLite database and the `VELXTRIA_DATA_DIR` directory.
2. Extract the complete archive and open `velxy-main` in Cursor.
3. Preserve your existing environment variables and local SQLite data directory.
4. Run `$env:VELXTRIA_LOCAL_STUDIO="1"; $env:VELXTRIA_DEPLOYMENT_MODE="local"; python portal.py`.
5. Sign in and open `http://127.0.0.1:8878/sentinel-v53`.

The `/sentinel-v53.json` route exports the same workspace-scoped report. No automated business actions or database writes are performed by Sentinel. Do not treat a clear sampled check as proof of complete data coverage.
