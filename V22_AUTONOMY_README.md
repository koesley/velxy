# VELXTRIA V22 — Project Autonomy (pilot)

Local-only deterministic workflows for Genesis Prime published apps. Open `/autonomy` with `VELXTRIA_LOCAL_STUDIO=1` and the existing `VELXTRIA_DATA_DIR`. Back up the database before upgrading.

Create a numeric threshold rule, review the dry-run results, and have a workspace owner activate it. When a new Genesis Prime record is added, an active rule creates one tenant-scoped review task if its numeric field is below the threshold. Owners and editors can manually run a rule on existing records. Viewer cannot execute or create rules. Every execution is recorded; tasks are idempotent per rule/record. No external network calls, arbitrary AI code, payments, or scheduled triggers.

This is V22.1/V22.2 foundation, not a full natural-language AI workflow designer. Live browser and existing-database compatibility require local testing.
