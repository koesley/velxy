# VELXTRIA V55 — Project Omega Intelligence

## Scope
V55 adds `omega_intelligence_v55.py`, an explainable local business analysis dashboard built from V50 Singularity, V52 Titan, and V54 Aegis workspace reports.

Features: five guided question categories, evidence-backed findings, strategy counterarguments, sampled knowledge graph, illustrative capacity scenarios, and JSON exports. The module is read-only, rule-based and does not run an LLM, perform background work, change customer data, or guarantee results.

## Upgrade
1. Back up the current SQLite database and the entire data directory.
2. Extract the archive and open `velxy-main` in Cursor.
3. Preserve `VELXTRIA_DATA_DIR` and any local environment settings.
4. Start the local studio:

```powershell
$env:VELXTRIA_LOCAL_STUDIO="1"
$env:VELXTRIA_DEPLOYMENT_MODE="local"
python portal.py
```

5. Sign in and open `http://127.0.0.1:8878/omega-v55`.
6. Export a report using `/omega-v55.json` from the dashboard.

## Verification
Run `python -m unittest -q test_omega_intelligence_v55` for focused and inherited tests. Run `python -m unittest discover -q` for the full suite.

## Limitations
- Report data is sampled by existing modules; a clean result does not establish completeness.
- Graph goal nodes use goal names and may merge identically named goals.
- Capacity scenarios are hypothetical and do not calculate delivery dates.
- All proposed actions require human review; no execution automation is added.
- Local testing is not a production security certification.
