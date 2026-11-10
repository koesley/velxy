# VELXTRIA V56 Sovereign — Milestone 5: Opportunity Discovery

## Implemented
- Read-only, deterministic opportunity triage built on existing validated monthly CSV evidence.
- Only opportunities supported by *both* unconflicted monthly metrics and synchronized Digital Twin source links qualify.
- Labels high/moderate/low describe relative magnitude of observed changes (20%+, 5%+, below 5%); they are not statistical confidence, financial impact, or expected return.
- Source references, exclusion reasons, conflict periods, and limitations in every saved result.
- Immutable historical run snapshots and staleness checks based on source facts, synchronization links, and rules version.
- Workspace-scoped read/write permissions, local SQLite-only route guard, existing session and CSRF protections.
- GET /sovereign-opportunities-v56 and GET /sovereign-opportunities-v56.json?w=<workspace-id>; POST /sovereign-opportunities-v56.

## Launch
Back up portal.sqlite3 first. Preserve VELXTRIA_DATA_DIR. From velxy-main:

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python portal.py
```

Visit http://127.0.0.1:8878/sovereign-opportunities-v56. First import monthly metrics under Sovereign V56, then sync under Sovereign Sync, then run opportunity discovery.

## Verification
`python -m unittest test_sovereign_opportunities_v56 -q`: 71 tests passed (includes inherited prior milestone tests). Python compileall passed. ZIP integrity verified. Full application regression, live HTTP browser, remote deployment, and production hardening were not verified.

## Limitations
No LLM or independently acting agents. No live third-party connectors. No real-time sync, attribution, prediction, ROI estimates, or external execution. The data model covers manually supplied aggregate monthly CSV data only. Severity labels are heuristic. Results should be reviewed against original records. Prior overlapping source conflicts must be resolved outside this module.

## Rollback
Stop server, restore backed-up DB and previous application package. New additive table `sv56_opportunity_runs` is otherwise isolated; do not delete database tables without backups.
