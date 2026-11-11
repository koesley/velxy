# VELXTRIA Business OS V59 — integration and release plan

## Implemented in this branch
- `business_os_v59.py`: workspace-isolated lead pipeline, opportunity values, manual status changes, draft follow-ups, owner approval and rejection, audit hooks, HTML dashboard, CSV export.
- `test_business_os_v59.py`: isolation, validation, approvals, metrics and HTML escaping.
- No autonomous external sends, purchases or claims of verified revenue.

## Integration still required before launch
1. Import `business_os_v59` into `portal.py`.
2. In authenticated GET routing, implement `/business-os-v59` and `/business-os-v59.csv`. Resolve workspace using existing access rules; pass the active session's uid and csrf to `render`, or call `export_csv` with correct content type and attachment headers.
3. In authenticated POST routing, implement actions `add`, `status`, `propose`, `review` after validating the existing session and CSRF token. Call corresponding module functions with the authenticated user ID; never accept a user ID from form input. Redirect to the workspace-scoped page.
4. Add the new navigation entry and confirm UI styles work on mobile.
5. Confirm behavior under Render's actual database backend. Current implementation uses SQLite-compatible SQL and needs review for PostgreSQL adapter compatibility.
6. Run `python -m unittest test_business_os_v59 -v` and existing full suite. Perform staging security and permissions tests.
7. Never deploy to production until review, backup, migrations and rollback are ready.

## Subsequent complete platform tracks
- Intelligence: import authorized data, provenance, evidence labels, deduplication, confidence and anomaly checks.
- Agent workforce: persistent jobs, idempotency, queue, retry limits, permissions, cost budgets, explicit human approvals, no default outbound side effects.
- Revenue recovery: real connector ingestion, consent and opt-out handling, messaging integration behind approval, outcome reconciliation.
- Website agent: isolated embeddable widget, knowledge ingestion, safe lead capture, privacy controls, rate limits.
- Simulation lab: reuse V57 lab, improve sensitivity analysis, distinguish projections from verified observations.
- Command center: unify V56/V57 metrics, queues, audit trails, agent status and cost tracking.
- Billing: connect a verified payment provider, avoid marking payments complete from user input.
- Security: secret management, role boundaries, tenant isolation, backups, retention and monitoring.

This document describes outstanding work; it is not a claim that all six systems are implemented or deployed.
