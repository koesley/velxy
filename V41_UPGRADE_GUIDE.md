# VELXTRIA V41 — Project Nexus Reforged

## Major changes
- New unified `/nexus-reforged` command center organized into Operate, Understand, Grow and Trust.
- Dramatically simplified global navigation (8 links instead of 40+). All prior modules remain accessible through the command center or their original URLs.
- Workspace-aware links, tenant permission checks, escaped labels, searchable tool directory, progress, and live metrics.
- Responsive, accessible dashboard and read-only operations; no customer records are changed by viewing the hub.
- Six regression tests for workspace isolation, escaping, data safety, search and navigation.

## Upgrade
1. Back up `VELXTRIA_DATA_DIR` and preserve the existing database.
2. Extract the full archive to a new project folder and keep your environment configuration.
3. From `velxy-main`, run `python -m unittest discover -p 'test_*.py'`.
4. Run with `VELXTRIA_LOCAL_STUDIO=1`, `VELXTRIA_DEPLOYMENT_MODE=local` and `python portal.py`.
5. Sign in and visit `http://127.0.0.1:8878/nexus-reforged`.

This remains a local preview. Browser execution, security audit, billing and production deployment are not certified.
