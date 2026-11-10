# VELXTRIA V56 — Workflow Operations Upgrade

Extends Workflow Studio Plus with manually operated run tracking.

## Features
- Start a run only from an owner-approved blueprint. Snapshot the approved steps so later changes cannot silently rewrite run history.
- Workspace-scoped run history and per-step progress, blocking, reset, pause, resume, cancellation, and completion.
- Sequential checkpoints prevent marking later steps complete while earlier ones remain pending.
- Human approval checkpoints require the workspace owner and a recorded reason.
- Every mutation is recorded in the existing Sovereign audit trail.
- JSON read endpoint at `/sovereign-workflow-runs-v56.json?w=WORKSPACE_ID`.
- HTML interface at `/sovereign-workflow-runs-v56`.

## Limitations
No timers, triggers, integrations, outbound requests, automated tasks, financial transactions, or evidence verification. A marked checkpoint reflects a human report only. This is not production-hardened or a replacement for business audit controls. Local SQLite Studio only.

## Launch
```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python portal.py
```

Test: `python -m unittest -q test_sovereign_workflow_runtime_v56`
