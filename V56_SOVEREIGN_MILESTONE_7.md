# VELXTRIA V56 — Sovereign Milestone 7: Execution Center

## Scope
Local SQLite studio only. Implements an owner-approved, persistent **internal review task** action. It does not call external APIs, send messages, charge cards, or make business changes. "Autonomous" here means deterministic dispatch of an explicitly queued internal action, initiated by an owner; it is **not** an unattended background agent.

## Workflow
1. Import and reconcile monthly CSV metrics, discover an opportunity, and simulate a strategy in Milestone 6.
2. Open `/sovereign-execution-v56`, choose a strategy run, enter a valid scenario code (e.g. `retention_review`) and a unique idempotency key (8–128 ASCII alphanumeric/`-_:`, unique per workspace).
3. An editor or owner can propose; only a workspace owner can approve, reject, queue, pause, resume, or dispatch.
4. Owner approves then queues, then presses **Dispatch next approved task**. A transaction claims the job, creates one internal task, and records completion.
5. Review task and event history on the dashboard or `/sovereign-execution-v56.json?w=<workspace_id>`.

## Persistence and migration
`sovereign_execution_v56.setup(c)` creates `sv56_exec_policy`, `sv56_exec_jobs`, `sv56_exec_tasks`, `sv56_exec_events` and an index using idempotent SQLite DDL. Existing tables are not dropped or altered. Back up the SQLite database and keep `VELXTRIA_DATA_DIR` unchanged before upgrading. To roll back code, restore the previous ZIP; new tables can remain unused. Restore a database backup to reverse stored Milestone 7 data.

## State machine
`proposed → approved → queued → running → succeeded` with `proposed → rejected/cancelled` and `queued → expired/failed`. Approval expires (default 24h). Dispatch is explicitly owner-initiated and transactional. Job `attempts` are bounded to 3 in the schema, but this milestone deliberately has no automatic retry worker. A process crash during the transaction rolls back task creation and state changes; task uniqueness by job ID prevents duplicate side effects. The emergency pause blocks new dispatch and approval/queue transitions, not an already executing transaction.

## Security and boundaries
All queries and mutations scope by authenticated workspace membership. Owner-only approvals and dispatch. Existing portal authentication and CSRF checks protect POST requests. Existing local-studio and SQLite-only guards remain. No secrets or external integrations. History is tenant scoped. Audit events persist. Imported business data is untrusted and escaped when rendered.

## Verification
Run `python -m unittest test_sovereign_execution_v56 -q`. The module inherits prior milestone tests. `python -m compileall -q portal.py sovereign_execution_v56.py test_sovereign_execution_v56.py` checks syntax. Full app/browser/security/deployment tests are **not** established by this focused suite.

## Known limitations / next steps
- No automatic background worker, external side effects, scheduled retries, or lease recovery. The schema reserves `lease_until` for future use.
- Only one allowlisted internal task type is supported.
- No task-assignee or due-date integration with external task managers.
- SQLite-only; PostgreSQL compatibility, load testing, full browser flows, production readiness, and end-to-end restoration tests remain outstanding.
- For production, add job worker ownership, robust lease recovery, operational monitoring, and stronger cross-module migration controls.
