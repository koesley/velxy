# VELXTRIA V57.4 — Omniverse Decision Laboratory

## Features
Workspace-isolated scenario studies linked to existing Council investigations; numerical baseline, metric, units, horizon and explicit assumptions; up to 12 alternatives with change %, cost and risk sensitivity; deterministic projections; owner-only approval/rejection; recorded observed metrics and evidence; historical measurements; audit events; read-only JSON overview; integrated local dashboard.

## Launch
From `velxy-main` on local SQLite: set `VELXTRIA_LOCAL_STUDIO=1` and `VELXTRIA_DEPLOYMENT_MODE=local`; run `python portal.py`; visit `/sovereign-lab-v57` after signing in and creating a workspace/investigation.

## Safety and limitations
The scenario calculation is baseline × (1 + percentage / 100). The risk-adjusted display is scenario × (1 - assumed risk percentage / 100); this is not a statistically calibrated forecast. Observations are self-reported, not independently verified; differences do not establish causation. Review is approval of the *plan record*, not authorization to spend or execute actions. No external integrations or autonomous execution. Only local studio mode is supported. Production browser and security testing remain necessary. Back up your database before upgrading.
