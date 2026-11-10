# VELXTRIA V56 — Workflow Nexus 3: Due Queue and Controlled Dispatch

## What changed
- Due queue for scheduled, approved workflow blueprints.
- Explicit human-initiated dispatch starts a real manual checkpoint run, not external execution.
- Idempotent dispatch ledger connects schedule IDs to run IDs.
- Persistent local notification and audit entry after dispatch.
- Workspace membership, editor/owner permissions, due-time checks, approval-gate checks.
- JSON overview now includes `due_queue` and `dispatches`.

## Limits
No background scheduler, email/push, drag-and-drop editor, external task execution, or automated branching. The server uses local wall-clock time for due checks. Do not use as a production scheduling service without timezone, concurrency, database transaction, and integration testing.

## Run
`$env:VELXTRIA_LOCAL_STUDIO="1"` then `$env:VELXTRIA_DEPLOYMENT_MODE="local"` and `python portal.py`; open `/sovereign-nexus-v56`.
