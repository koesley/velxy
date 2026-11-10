# VELXTRIA V43 — Project Autonomous Core

## What changed

- New `/autonomous-core` workspace dashboard and `/autonomous-core.json` scoped JSON export.
- Propose experiments against existing Nexus Intelligence goals using a measured baseline.
- Only workspace owners approve/reject experiments; editors may propose and record follow-up outcomes.
- Human-entered action plans and outcome notes; no automatic action execution.
- Explicit proposed → approved → completed lifecycle, rejection/cancellation, event history, and directional comparisons.
- Experiments use existing Nexus metric measurements (latest 500 records), so a change in the value is descriptive, not proof of causation.
- No existing V42 tables are deleted or overwritten. New SQLite tables and indexes are created when the portal starts.

## Upgrade

1. Back up your current SQLite database and project files.
2. Extract this ZIP. Keep the same `VELXTRIA_DATA_DIR` setting as your previous version.
3. In PowerShell:

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python portal.py
```

4. Open `http://127.0.0.1:8878/autonomous-core` after signing in.
5. Create a workspace, published application, and measurable Nexus goal if you don't have one.
6. Propose an experiment, approve it as workspace owner, manually perform the change, then record a follow-up measurement.

## Tests

```powershell
python -m unittest discover -p "test_*.py"
python apex_v37.py run
```

## Limitations

- This is not an autonomous business operator; no actions are executed on behalf of customers.
- No causal inference, randomized experiment assignment, forecast or guaranteed profitability.
- Browser, remote deployment, and independent security certification remain outstanding.
- Existing SQLite connection ResourceWarnings in legacy modules remain.
