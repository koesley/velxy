# VELXTRIA V57.1 — Project Omniverse Foundation

## Included
- Persistent workspace-scoped event log and indexed job ledger.
- Allowlisted internal read-only capabilities: workspace metrics, workflow readiness, Guardian alert count.
- Manual job queue, due-time validation, idempotency, explicit dispatch, cancellation, owner-only recovery, maximum three attempts.
- Permission checks, audit trail, HTML dashboard, JSON endpoint.
- Local SQLite studio mode only. No paid API dependency.

## Start
Set `VELXTRIA_LOCAL_STUDIO=1` and `VELXTRIA_DEPLOYMENT_MODE=local`, run `python portal.py`, and visit `/sovereign-omniverse-v57`.

## Limitations / next phase
This is a **foundation**, not a fully autonomous operating system. No background worker, drag-and-drop editor, third-party integrations, automatic notifications, AI agents, distributed locking, or production deployment validation. Job leases are persisted but dispatch is synchronous and manually invoked; a crashed run needs owner recovery after lease expiry. SQLite is appropriate for local single-process development, not an at-scale distributed queue.
