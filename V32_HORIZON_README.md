# VELXTRIA V32 — Horizon

Local pilot improvement planning layered on V31. Open `/horizon` after running `python portal.py` with `VELXTRIA_LOCAL_STUDIO=1` and `VELXTRIA_DEPLOYMENT_MODE=local`.

- One workspace-scoped improvement plan per pilot issue.
- Priority, proposed fix, metric, baseline, target, measured result and reviewer status.
- Owners/editors can create and update; viewers read only.
- Workspace-scoped SQL queries and CSRF-protected POST forms via portal.py.
- No external integrations, deployments, automated fix execution, or causal attribution.

Back up your SQLite database before updating. Preserve `VELXTRIA_DATA_DIR`.
