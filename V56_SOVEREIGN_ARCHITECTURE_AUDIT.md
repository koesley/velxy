# VELXTRIA V56 — Project Sovereign: architecture audit and first milestone

## Scope and provenance
Inspected the actual **V55** source tree, rather than the previously packaged V56 Prometheus branch. Sovereign is an alternative V56 branch built on V55. This is a **local-studio foundation release**, not the completed 27-part directive or production certification.

## 1. Inventory and reusable infrastructure
- `portal.py`: Python standard-library HTTP server, cookie sessions, CSRF, existing public/customer portal, workspace navigation, report uploads and local studio route guards.
- `persistent.py`: SQLite for local development; optional PostgreSQL wrapper for remote deployments.
- `empire_v19.py`: workspace membership and owner/editor/viewer roles, invitation mechanism, existing tenant-scoped workspace records.
- `omega_intelligence_v55.py`, `aegis_v54.py`, `titan_intelligence_v52.py`, `singularity_v50.py`: read-only evidence, knowledge summaries, deterministic findings and hypothetical capacity scenarios.
- `autonomous_core_v43.py`, `hyperion_v47.py`, `evolution_engine_v46.py`: earlier experiment, planning and approval infrastructure.
- Payment/licensing: `payhip_integration.py`, `btcpay_integration.py`, `subscriptions.py`, `license_verification.py`; preserved unchanged.
- Existing test modules: extensive `unittest` suite with inheritance across releases. Historical full-suite runs timed out; focused test runs passed.

## 2. Working versus incomplete
Working in V55: local login, report processing, scoped Empire workspace records, read-only intelligence reports, local studio features, deterministic evidence analysis. No evidence of production-grade autonomous agents, verified third-party CRM execution, full multi-tenant isolation across every legacy module, or validated live revenue forecasting. The old portal explicitly warns that some older modules are account-scoped, not workspace-scoped.

## 3. Technical debt and risks
- Large monolithic HTTP route handler; risk of route and CSRF regressions.
- Local SQLite and optional remote PostgreSQL paths are not interchangeable for all older modules; new Sovereign module intentionally restricted to local SQLite.
- Many existing `db()` setup calls on each request; potential performance overhead.
- The existing multipart parser originally accepted only `csrf`, `email_report`, and `file`, so Sovereign extends it for `workspace` and `action` with field bounds.
- No demonstrated complete suite, browser end-to-end coverage, load tests, penetration tests, secret-management audit, or production readiness.
- New CSV fields are aggregated monthly totals only; never upload personal customer or bank data.

## 4. Recommended architecture and milestone dependencies
1. **Foundation vertical slice (implemented):** tenant-scoped metrics imports, source hashes, audit records, deterministic opportunities, what-if calculation, owner-approved internal review tasks, outcome capture, web UI and JSON export.
2. **Intelligence core:** shared typed evidence and permissions interfaces, policy engine, contradiction checks and bounded agent orchestration.
3. **Digital twin expansion:** typed entity graph, source metadata, conflict resolution and authorized connectors.
4. **Council and opportunities:** independently testable bounded specialists and configurable prioritization.
5. **Futures:** cash-flow and capacity modeling, data sufficiency gates and calibrated uncertainty.
6. **Action engine:** tool registry, idempotency keys, timeout/retry, explicit authorization and kill switch; start with one supported internal tool.
7. **Executive UX:** accessible integrated panels, searchable decision history and controlled natural language parsing.
8. **Hardening:** full test suite, HTTP browser journey, security isolation matrix, performance and deployment staging.

## 5. Migration and rollback
- Back up `VELXTRIA_DATA_DIR/portal.sqlite3` while the app is stopped before upgrade.
- `sovereign_v56.setup(c)` uses `CREATE TABLE IF NOT EXISTS` and indexes; no legacy table or data is dropped. New tables: `sv56_imports`, `sv56_metrics`, `sv56_actions`, `sv56_audit`.
- Rollback: stop server, restore the backed-up database and V55 source directory together. Avoid mixing code and schema versions. Sovereign tables can remain unused on rollback, but a clean restore is safest.
- No new Python packages or paid services required.

## 6. Limitations and release blockers
- Only local, user-supplied CSV data; no OAuth connector or live synchronization.
- Simple month-to-month observed changes; not causal attribution, statistical learning or financial advice.
- The internal approval workflow records an approved task, **not** an external CRM or email operation.
- No automated background workers, model usage metering, Monte Carlo engine, full graph UI, or production-grade multi-agent reasoning.
- No production deployment performed. Full suite, HTTP integration, and load/security testing are outstanding.

## 7. Sample CSV
```csv
period,revenue,expenses,leads,customers
2026-01,1000,400,100,20
2026-02,800,500,100,10
```
Start with `VELXTRIA_LOCAL_STUDIO=1`, `VELXTRIA_DEPLOYMENT_MODE=local`, `python portal.py`. Open `/empire` to create workspace, then `/sovereign-v56`.
