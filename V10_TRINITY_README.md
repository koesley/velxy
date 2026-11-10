# VELXTRIA V10 — PROJECT TRINITY

Three working local-first modules, integrated into the existing portal:

- **Genesis** (`/trinity?tab=genesis`): Create schema-driven private mini-apps with up to 12 custom text fields, store and delete records.
- **Nexus** (`/trinity?tab=nexus`): Create internal collaboration proposals and track draft/ready/archived status. No external sharing or messaging.
- **Aether** (`/trinity?tab=aether`): Interactive perspective-styled spatial navigation for apps, proposals, missions, and dossiers. Not a full 3D engine.

Requires `VELXTRIA_LOCAL_STUDIO=1` and a local SQLite database. Existing tables remain unchanged; new tables are `vx10_apps`, `vx10_records`, and `vx10_nexus`. Back up your working database and point `VELXTRIA_DATA_DIR` at the verified existing data folder before starting. No database is included in this ZIP.

This is not an LLM-based app generator or multi-tenant collaboration network. Those require further design, permissions and security review.
