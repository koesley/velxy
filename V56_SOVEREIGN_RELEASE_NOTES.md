# Sovereign V56 — milestone 1 release notes

## Created
- `sovereign_v56.py`: schema setup, tenant-scoped CSV ingestion, source provenance, evidence-based change detection, deterministic scenario calculation, internal review workflow, audit log and HTML dashboard.
- `test_sovereign_v56.py`: 10 focused unit tests.
- `V56_SOVEREIGN_ARCHITECTURE_AUDIT.md`: inventory, gaps, migration/rollback and dependency-aware roadmap.
- `SOVEREIGN_SAMPLE_METRICS.csv`: clearly labeled sample data, not real business data.

## Modified
- `portal.py`: guarded GET `/sovereign-v56`, `/sovereign-v56.json`, CSRF-protected POST `/sovereign-v56`, CSS/nav integration, database schema setup, bounded multipart fields.

## Verification
- `python -m unittest test_sovereign_v56 -q`: 10 passed.
- `python -m unittest test_omega_intelligence_v55 -q`: 92 passed (inherited suite).
- `python -m compileall -q sovereign_v56.py portal.py test_sovereign_v56.py`: passed.
- Full application test discovery, real browser journey, remote deployment, security audit and performance testing **not verified**.

## Security and data
- Read endpoints require workspace membership; imports and proposals require owner/editor; approval and completion require owner; POST requests require existing session CSRF token.
- No new credentials or paid APIs. Only local SQLite studio mode. No external automated execution.
- CSV hashes and source IDs are retained. Conflicting periods are excluded from comparisons, not overwritten.
- Limits: 1 MB CSV, 5000 rows, bounded financial values, no PII fields.

## Next milestone
- Typed permission/evidence interfaces and a bounded orchestration core, then graph relationship expansion and validated local connector adapters.
