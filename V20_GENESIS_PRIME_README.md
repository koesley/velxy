# VELXTRIA V20.1 — Genesis Prime

A **local-only pilot** building on V19 Empire, not a production-ready SaaS product.

## What works
- Workspace-bound app creation using four predefined schemas (inventory, appointments, CRM, projects)
- Add typed fields to drafts; owner-only publishing; read-only published schema
- Records scoped to workspace and app, role-checked server-side
- Immutable schema-version snapshots on edits and publication
- HTML-escaped UI at `/genesis-prime` and CSRF-protected POST forms through the existing portal
- Automated SQLite tests for tenant isolation, permissions, validation and records

## What is NOT included
- No AI schema generation or Ollama integration in this module
- No drag-and-drop visual editor, workflow automation, marketplace, payment collection, or external hosting
- No Infinity/Docker validation integration; publishing checks schema shape only
- Existing V19 and earlier modules remain account-scoped and are not automatically tenant-isolated
- Not audited for public multi-tenant hosting; do not expose this local pilot publicly

## Start
1. **Back up** your existing `portal.sqlite3` and preserve the value of `VELXTRIA_DATA_DIR`. Never copy an old database into a different location without confirming the active path.
2. Set `VELXTRIA_LOCAL_STUDIO=1` and `VELXTRIA_DEPLOYMENT_MODE=local` and use your existing SQLite persistence settings.
3. `python portal.py`; open `http://127.0.0.1:8878/genesis-prime`.
4. Create a workspace in Empire V19, then create an app in Genesis Prime.

Test: `python -m unittest -v test_genesis_prime_v20.py`
