# VELXTRIA V48 — Quantum Command

## Install
Back up your existing SQLite database. Extract this full project over a copy of your existing code, retaining the same `VELXTRIA_DATA_DIR` environment variable. Do not overwrite your data directory.

In PowerShell:
```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python portal.py
```
Visit `http://127.0.0.1:8878/quantum-command` after logging in. Create approved experiments and Hyperion plans first.

## New features
- Workspace-level available hours per week (defaults to a *clearly labeled assumption* of 40).
- Estimates for unfinished Hyperion milestones, validated to finite positive hours.
- Conservative (50% capacity), baseline (100%), and accelerated (150%) what-if scenarios.
- Missing-estimate counts, overdue and blocked milestones, and dependency-chain workload.
- JSON report export at `/quantum-command.json` with workspace authorization.
- No automatic execution, external API calls, or customer record modification.

## Validation
`python -m unittest discover -p 'test_*.py' -q`
`python apex_v37.py run`

## Limitations
Forecasts are simple capacity lower bounds and omit unestimated work. Dependencies and staffing constraints mean completion can take longer. No claims of guaranteed delivery dates or profit. Browser and production validation remain necessary.
