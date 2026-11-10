# VELXTRIA V28 — Ascension

## What's included
- A responsive, unified local workspace dashboard at `/ascension`.
- Workspace-scoped application, automation, goal, and strategy counts.
- Onboarding progress computed from actual Launchpad evidence.
- Shortcuts to Genesis Prime, Oracle, Autonomy, Nexus, Launchpad, and Foundation.
- A simplified top-level navigation entry while preserving all legacy routes.

## Run
Back up your existing database before upgrading. Preserve `VELXTRIA_DATA_DIR`.

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python portal.py
```

Visit `http://127.0.0.1:8878/ascension`.

## Boundaries
The dashboard is read-only, requires login, and checks Empire membership for each workspace. It does not imply production readiness, full security audit completion, or tested external customer deployment.
