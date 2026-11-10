# VELXTRIA V13 — Singularity X (local software creation laboratory)

This release builds on V12 and preserves its earlier modules. It adds `/singularity-x`, a safe declarative app builder that selects an app schema from a description (appointments, inventory, customer tracker, invoice ledger, or project tracker), runs four validation simulations, and requires owner approval before local publication. Published apps store tenant-scoped records, support deletion, and export app structure plus records to JSON.

## Run
1. Back up the working `portal.sqlite3` database first. Never overwrite it with files from the ZIP.
2. Extract ZIP and open `velxy-main` in Cursor.
3. Point `VELXTRIA_DATA_DIR` to your actual existing data directory. Set `VELXTRIA_LOCAL_STUDIO=1`, `VELXTRIA_DEPLOYMENT_MODE=local`, `VELXTRIA_REQUIRE_PERSISTENCE=0` as in previous versions.
4. `python portal.py` and open `http://127.0.0.1:8878/singularity-x` after logging in.
5. Create a draft, run simulation tests, approve local publication, and add records.

## Scope and security
- No arbitrary code execution, AI-written source code, sandbox runtime, network access, live deployment, external integrations, or multi-agent execution is provided by V13. The description is matched to fixed local templates, not interpreted by an LLM.
- Simulations validate sample data and schema constraints; they are not security penetration tests or comprehensive software tests.
- Local publishing enables an app within the portal; it does not deploy to a public website.
- JSON export contains app data: handle securely.
- No changes to the existing Bitcoin address or Supabase project.
- V13 is local SQLite only. The rest of the existing app is unchanged.
