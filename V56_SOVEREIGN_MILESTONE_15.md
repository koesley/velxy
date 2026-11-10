# VELXTRIA V56 — Milestone 15: Sovereign Unified Command

A unified read-only entry point to the existing Project Sovereign modules. New routes: `/sovereign-unified-v56` and `/sovereign-unified-v56.json`. Primary navigation now includes Command; prior modules and integrations remain in place.

## Features
- Five pathways: Discover, Observe, Decide, Act, Learn.
- Workspace-scoped counts for allowlisted tables, links retaining the workspace selector, and role-checked access.
- Readiness and evidence cards, including explicit **production readiness not verified** status.
- Responsive dark-purple design, accessible keyboard focus, escaped user-controlled strings.
- No third-party API, autonomous execution, spending, or writes in this overview.

## Local launch
```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python portal.py
```
Sign in, create or join a workspace, and open `http://127.0.0.1:8878/sovereign-unified-v56`.

## Limits / release gate
This milestone does **not** certify production security, deployability, customer data protection, or full workflow interoperability. Prioritize a full regression run, authenticated browser testing, workspace-boundary review across legacy routes, backup/restore rehearsal, payment and entitlement verification, deployment secret review, and accessibility testing before public launch. Counts represent recorded data, not outcomes.
