# VELXTRIA V44 — Project Synapse

## What's new

- `/synapse`: workspace-scoped task and measurement dashboard.
- Approved experiments can contain manually executed tasks with status and completion evidence.
- On-demand goal measurement snapshots with sample counts and contextual notes.
- Completion of an experiment is blocked while its tasks remain open, including through the V43 portal action.
- Read-only JSON evidence export at `/synapse.json?w=<workspace-id>`.
- Permission checks, CSRF protection through the existing portal, and escaped HTML output.
- No scheduled jobs, external integrations, or automatic writes to business records.

## Upgrade safely

1. Back up your current `portal.sqlite3` and preserve `VELXTRIA_DATA_DIR`.
2. Extract the ZIP and open `velxy-main` in Cursor.
3. Set `VELXTRIA_LOCAL_STUDIO=1` and `VELXTRIA_DEPLOYMENT_MODE=local`.
4. Run `python portal.py` and open `http://127.0.0.1:8878/synapse`.
5. Propose and approve an experiment under `/autonomous-core`, then add tasks and capture measurements under `/synapse`.

## Verify

`python -m unittest discover -p 'test_*.py' -q`

`python apex_v37.py run`

## Limitations

No real-world tasks are executed by VELXTRIA. Goal snapshots are observational, not causal. No scheduled recurring collection or notification is installed. Browser-based tests and independent production security assessment remain outstanding. Existing SQLite resource warnings persist in older modules.
