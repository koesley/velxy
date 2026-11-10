# VELXTRIA V56.12 — Sovereign Business Guardian

## Delivered
- `sovereign_guardian_v56.py`: SQLite-backed deterministic alert engine.
- Workspace-scoped manual health scans of **approved** connector snapshots, grouped by source and month.
- Revenue decrease >20%, expense increase >25%, negative margin, gaps between recent observed periods, and latest-data staleness >2 calendar months.
- Idempotent alert keys (workspace, rule, subject), preserved acknowledgements when evidence is unchanged, reopen when evidence changes, audit events, JSON history, status lifecycle.
- Portal dashboard `/sovereign-guardian-v56`, JSON `/sovereign-guardian-v56.json`, manual scan and status updates via CSRF-protected POST.
- UI: grouped Explore Platform navigation, top-level Guardian link, accessible responsive dark-purple dashboard.
- Tests `test_sovereign_guardian_v56.py`.

## Run
Back up the database and your existing deployment before upgrading. Extract the complete archive into a separate directory and run from `velxy-main`:

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python portal.py
```

Visit `http://127.0.0.1:8878/sovereign-guardian-v56`. Create a workspace, register a connector source, stage and owner-approve a metrics CSV snapshot, then click **Run health scan**. Workspace members with write permissions can scan and change alert status; viewers can view alerts.

## Verification
`python -m unittest -q test_sovereign_guardian_v56` passed 134 inherited and new tests. `python -m py_compile portal.py sovereign_guardian_v56.py` passed. Full unittest discovery did not finish within the available time; full regression, interactive browser and production tests are outstanding.

## Limits and safety
- Local SQLite studio mode only. No background worker, scheduling, remote data connection, outbound notification, automatic business action, or LLM agent.
- Connector snapshots remain isolated from the core verified metrics pipeline.
- Monitoring uses the two most recent **observed** months; missing months can affect comparisons. Source data may be incomplete, revised, or stale.
- Alert statuses are operator annotations, not proof of remediation. Alerts are not causal claims or fraud detection.
- Existing older routes are not necessarily tenant-isolated; audit all legacy endpoints before a multi-tenant production launch.
- Manual scans intentionally do not auto-close alerts that are absent from a later scan.
