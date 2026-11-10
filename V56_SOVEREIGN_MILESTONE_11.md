# V56 Milestone 11 — Universal Business Connectors (local foundation)

## Delivered
Read-only CSV metrics adapter registry, workspace-scoped source registration, strict parsing, SHA-256 deduplication, staged immutable snapshots, owner approval, fail-closed external ID conflict checks, audit log, dashboard, JSON history. No paid services required.

## Local setup
Back up your database. Set `VELXTRIA_LOCAL_STUDIO=1` and `VELXTRIA_DEPLOYMENT_MODE=local`; run `python portal.py` and visit `/sovereign-connectors-v56`. Register a source and paste CSV using the header `external_id,period,revenue,expenses,leads,customers`. Review staged batches and approve as owner.

## Security and limitations
Workspace authorization is checked on every operation; editor may stage, owner must approve; viewer read-only. External identifiers cannot silently change existing applied values. No network calls, OAuth, secrets, background polling, external writes, or remote sync are implemented. Staged and applied snapshots are kept in connector-specific tables and do not automatically change the Sovereign metrics evidence or digital twin. No guarantee of accounting correctness or business profit. Only the local SQLite studio mode is supported.

## Tests
`python -m unittest -q test_sovereign_connectors_v56`
