# VELXTRIA V56 — Workflow Nexus 2

Built on Workflow Nexus Expansion. Adds three local, human-controlled workflow planning capabilities without external services or paid APIs.

## Features

1. Reusable step recipes: create named, workspace-isolated recipes of 1–12 supported module step keys. These are references for designing future workflows, not executable imports.
2. Schedule board: workspace editors can record a future reminder (up to 366 days) for an approved workflow and cancel it. These records **do not** trigger background jobs or notifications automatically.
3. Conditional review: for an active run, a workspace editor can record an observed outcome for a checkpoint; the system evaluates the blueprint's rule (`always`, `on_success`, `on_blocked`, `manual_review`) and records a guidance decision. Manual-review rules require workspace-owner authorization. This **does not** advance or execute a checkpoint.
4. Audit events, workspace scoping, input validation, JSON overview, HTML-escaped UI, responsive dark-purple panels.

## Launch

Set `VELXTRIA_LOCAL_STUDIO=1`, `VELXTRIA_DEPLOYMENT_MODE=local`, then run `python portal.py`. Open `/sovereign-nexus-v56` (requires authentication and a workspace). JSON: `/sovereign-nexus-v56.json?w=<workspace-id>`.

## Validation

Run `python -m unittest discover -p 'test_sovereign*.py' -q` from the project directory. Run `python -m py_compile sovereign_nexus_v56.py portal.py`.

## Limitations

- The existing canvas is a horizontally scrollable planner, **not drag-and-drop**.
- Conditional reviews are persisted guidance only, not executable transitions.
- Schedules are saved intentions, not automatic reminders or scheduled execution.
- Recipes are reusable planning data, not auto-inserted workflow fragments.
- Local SQLite studio only; production deployment, browser QA, security audit and external automation are not verified.
- Back up the database before upgrading; schema additions are additive.
