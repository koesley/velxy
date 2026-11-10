# VELXTRIA V42 — Infinity Engine

## What changed
- Workspace-scoped, read-only business decision board at `/infinity-engine`.
- Deterministic cross-app numeric summaries, record coverage warnings, goal gaps and snapshot trends.
- Downloadable, authenticated, workspace-scoped JSON export at `/infinity-engine.json`.
- Clear limits: recent 500 records per app; goals are not assumed to be maximize metrics.

## Run
Back up your database and retain `VELXTRIA_DATA_DIR`. In local mode:

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python portal.py
```

Open http://127.0.0.1:8878/infinity-engine.

## Safety
No new schema migrations, external AI requests, payments, automatic edits or deployments. Report exports contain business data: share them carefully. Existing security and production review requirements remain.
