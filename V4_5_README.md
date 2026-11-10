# VELXTRIA V4.5 — Local Business Intelligence

Read-only business intelligence appears at the top of `/workspace`. It calculates 30-day recorded income/expenses, compares the prior 30 days, and highlights overdue invoices, leads, and open tasks. It uses existing tables and has no paid dependencies. No automated financial or website actions.

## Setup (PowerShell, inside velxy-main)

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
$env:VELXTRIA_REQUIRE_PERSISTENCE="0"
Remove-Item Env:VELXTRIA_DATABASE_URL -ErrorAction SilentlyContinue
python portal.py
```

Open `http://127.0.0.1:8878/workspace` and enter test income, expenses, contacts, or invoices. Reload to see suggestions. The startup now calls `business_v4.setup(c)` to prevent the missing invoices-table crash encountered in V4.4.

This archive does not include the user's existing SQLite database. To retain existing local data, back up the existing `portal.sqlite3` and copy it into this `velxy-main` folder while the server is stopped. Never overwrite the only copy of your database. This ZIP is for local testing, not production deployment.
