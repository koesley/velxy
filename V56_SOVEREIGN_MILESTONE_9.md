# VELXTRIA V56 — Sovereign Milestone 9: Business Future Simulator

## Scope
A deterministic, local-only 1–36 month hypothetical cash-flow simulator. It reads the latest unconflicted, workspace-scoped imported monthly metrics. No predictive model, financial attribution, live accounting sync, or external action is performed.

## Features
- Adjustable monthly compounded revenue/expense change (-50% to +50%), first-month revenue shock (0–90%), opening cash (0 to 1 trillion), and horizon (1–36 months).
- Month-by-month revenue, expenses, net cash flow proxy, cash balance, and first negative-cash month.
- Immutable saved scenario snapshots and source-import provenance; stale detection when the latest valid baseline changes.
- Workspace member read access; owner/editor write access. Existing portal session, CSRF, and local-studio restrictions apply.
- Dashboard `/sovereign-future-v56` and JSON history `/sovereign-future-v56.json?w=WORKSPACE_ID`.

## Start
Back up the existing SQLite database and preserve `VELXTRIA_DATA_DIR`. Extract ZIP and from `velxy-main`:

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python portal.py
```

Create a workspace and import monthly metrics first, then open `http://127.0.0.1:8878/sovereign-future-v56`.

## Schema and rollback
`sovereign_future_v56.setup(c)` creates `sv56_future_runs` and `sv56_future_scope` using `IF NOT EXISTS`. Back up DB before migration. To remove only this milestone's saved data after verifying backups: `DROP TABLE sv56_future_runs;` (its index is removed with the table); revert `portal.py` and remove module/test. Other Sovereign data is untouched.

## Verification
`python -m unittest test_sovereign_future_v56 -q` — 102 tests passed (inherited test classes are included). `python -m unittest test_sovereign_future_v56 test_sovereign_memory_v56 -q` — 228 test executions passed, with duplicated inherited cases. `python -m compileall -q portal.py sovereign_future_v56.py test_sovereign_future_v56.py` passed. Full application/browser/production deployment not verified.

## Limitations
- The cash proxy is `revenue - expenses`, not actual bank cash flow, accounting net income, or cash runway.
- No tax, accounts receivable, debt service, financing, inventory, seasonality, or business-day timing.
- Revenue and expense changes are manually supplied hypothetical assumptions and compound each month; no confidence intervals or predictions.
- This feature runs only in local SQLite studio mode; production tenant isolation and PostgreSQL compatibility need separate verification.
- The new module does not automatically connect to or update Strategy, Execution, or Organizational Memory records.
