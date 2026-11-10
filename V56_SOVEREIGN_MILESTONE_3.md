# V56 Sovereign Milestone 3 — Business Digital Twin 2.0

## Scope
Manual, sourced, typed business nodes and compatible directional relationships. Workspace-scoped graph JSON and traversal; revision-checked reconciliation in backend; audit events. No causal inference, automatic imports, external connectors, or inferred links.

## Files
- `sovereign_twin_v56.py`: schema, validation, graph operations, UI.
- `portal.py`: local-studio routes `/sovereign-twin-v56`, `.json`, navigation, schema setup.
- `test_sovereign_twin_v56.py`: tenant, types, revisions, provenance, escaping, traversal tests.

## Database and migration
Three additive SQLite tables: `sv56_twin_nodes`, `sv56_twin_edges`, `sv56_twin_changes`; scoped indexes. Existing records are preserved. Backup the DB before running. Rollback: restore backup and prior application version; dropping the new tables is optional and destroys new graph data.

## Security
All graph operations call existing workspace role checks. POST routes use the portal's existing CSRF guard. Inputs validated and HTML encoded. No credentials or network access. SQLite foreign keys should be enabled in connection configuration.

## Limitations / next milestone
Manual source references are descriptive, not cryptographically verified. No user-facing reconciliation form; backend API supports optimistic revisions. Existing monthly metrics are not yet mapped into the new graph. Next: validated data-source mapping, conflict resolution and sync-job tracking; then richer intelligence integration.
