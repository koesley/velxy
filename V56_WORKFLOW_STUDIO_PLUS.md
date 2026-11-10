# VELXTRIA V56 — Workflow Studio Plus

Adds two new templates (product launch and business resilience), duplicate-as-draft, per-workflow decision journals, review counters, and approval-gate readiness indicators. All notes and counts are workspace-scoped. Journal writes require owner/editor membership and use existing CSRF-protected portal forms. Only owners can approve workflows. No workflow executes external actions.

## Local launch
Set `VELXTRIA_LOCAL_STUDIO=1` and `VELXTRIA_DEPLOYMENT_MODE=local`, then run `python portal.py` and open `/sovereign-workflows-v56`.

## Limitations
This remains a human-operated planning tool, not an event-driven automation engine. Notes are not a substitute for validated business data. Production browser and deployment validation are outstanding.
