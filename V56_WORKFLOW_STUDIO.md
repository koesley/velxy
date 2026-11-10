# VELXTRIA V56 — Workflow Studio

Local-only, workspace-isolated visual workflow planner.

## Features
- Three curated blueprints: Discover, Plan, Monitor.
- Add, remove, reorder steps in draft plans.
- Owner approval of plans requiring a Human Approval step.
- Manual preview snapshots and audit trail.
- Links to existing business modules; no automatic execution.
- GET `/sovereign-workflows-v56` and `.json`, POST same path.

## Launch
Set `VELXTRIA_LOCAL_STUDIO=1` and `VELXTRIA_DEPLOYMENT_MODE=local`, then run `python portal.py` and visit `http://127.0.0.1:8878/sovereign-workflows-v56`.

## Limitations
This is a workflow **designer**, not a background job runner, connector automation, drag-and-drop canvas, or production-certified system. Approval is for a plan, not approval of each execution job. Each module must still be operated separately with its own permission checks. Do not upload sensitive data.
