# VELXTRIA V56 — Workflow Nexus

## Added
- Premium horizontal workflow canvas with per-step conditional planning annotations.
- Workspace-scoped operational attention derived from blocked checkpoints, overdue manual deadlines, and owner approval gates.
- Local notification inbox storage with read status, auditable changes, and scoped access.
- JSON read-only overview endpoint `/sovereign-nexus-v56.json`.
- Primary navigation link and responsive styles.

## Important limitations
Conditions are **annotations only**, not executable branches. The canvas is horizontally scrollable, not drag-and-drop. There is no background scheduler, external integration, push/email notification delivery, or automatic execution. The existing Workflow Operations manual approval flow is unchanged.

## Start
`VELXTRIA_LOCAL_STUDIO=1 VELXTRIA_DEPLOYMENT_MODE=local python portal.py` then open `/sovereign-nexus-v56`. Back up the SQLite database before upgrading.
