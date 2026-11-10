# VELXTRIA V54 — Project Aegis

## New capabilities
- Read-only, per-experiment evidence dossiers, combining V50 workflow records and V53 data-quality checks.
- Severity-ranked issues for overdue work, blocked dependencies, missing baseline and follow-up values, missing plans, and unverified outcomes.
- Workspace-scoped dashboard at `/aegis-v54`, JSON at `/aegis-v54.json`, and CSV at `/aegis-v54.csv`.
- CSV formula-injection protection and escaped customer text in HTML.
- Conservative labels: `ready_for_review` never implies verified success.

## Upgrade
Back up the SQLite database and preserve `VELXTRIA_DATA_DIR`. Extract the full archive and open `velxy-main` in Cursor. In PowerShell:

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python portal.py
```

Sign in, then visit http://127.0.0.1:8878/aegis-v54.

## Limitations
This is a deterministic, read-only analysis of bounded internal reports, not a trained AI model, independent audit, causal analysis, or guarantee of business outcomes. Production deployment requires additional browser and security testing.
