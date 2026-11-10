# VELXTRIA V46 — PROJECT EVOLUTION ENGINE

## Major features
- Tenant-scoped, explainable opportunity-to-experiment proposal generation from V45 evidence.
- Deduplicated draft proposals with traceable source evidence and immutable decision events.
- Human-controlled dismiss or submit. Submission creates a V43 **proposed** experiment, which still requires owner approval.
- Cross-workspace permission enforcement, escaped HTML, JSON evidence export, and no automatic customer-record mutations.
- Existing V1–V45 modules remain included.

## Upgrade
1. Back up the existing SQLite database before extracting the upgrade.
2. Extract the archive and open `velxy-main` in Cursor.
3. Preserve `VELXTRIA_DATA_DIR`; never overwrite the existing database with a blank one.
4. Set `VELXTRIA_LOCAL_STUDIO=1` and `VELXTRIA_DEPLOYMENT_MODE=local`.
5. Run `python portal.py` and open `http://127.0.0.1:8878/evolution-engine`.
6. Complete measurable experiments in Synapse/Autonomous Core, then click **Generate reviewable proposals**.
7. Inspect and submit drafts. Workspace owner must separately approve in `/autonomous-core`.

## Verification
Run `python -m unittest discover -q`. Browser and production deployment certification remain outstanding.

## Limitations
- Rule-based suggestions, not a trained ML system.
- Observational changes cannot establish causality or predict profit.
- No external API or customer action is executed automatically.
- Proposal generation considers up to 25 current opportunities; displayed history is bounded.
