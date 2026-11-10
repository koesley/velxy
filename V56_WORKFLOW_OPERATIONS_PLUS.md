# Workflow Operations Plus

Extends Workflow Operations with workspace-scoped run priority (low/normal/high/critical), due dates, human-readable responsibility labels, objectives, timestamped activity history, comments, overview KPIs, and a CSV export endpoint.

Routes: `/sovereign-workflow-runs-v56`, `.json`, `.csv`. The CSV export includes only the latest 60 runs returned by the overview; it is not a complete historical export. All routes require authentication, workspace membership, and local SQLite studio mode. Metadata changes and comments require owner/editor roles. Owner-only approval gates remain intact. Due dates are informational and do not schedule work or send reminders. Owner labels are free-form text, not authenticated assignments. Workflow progress remains human-reported, not verified external execution.

Use `$env:VELXTRIA_LOCAL_STUDIO="1"`, `$env:VELXTRIA_DEPLOYMENT_MODE="local"`, then `python portal.py`.

Back up the SQLite database before updating. Schema additions use CREATE TABLE IF NOT EXISTS. Do not deploy to production without independent security and browser testing.
