# VELXTRIA V26 — Project Foundation (first milestone)

Local-only Business Command Center at `/foundation`. Includes tenant-scoped counts for existing workspace applications, automations, goals, strategies; SQLite integrity and readiness checks; owner-only online SQLite backup with integrity validation and SHA-256 sidecar. Backups stored under `VELXTRIA_DATA_DIR/foundation_backups/`, outside the project source ZIP. No automatic restore or deployment.

Start with `VELXTRIA_LOCAL_STUDIO=1`, `VELXTRIA_DEPLOYMENT_MODE=local`, and an existing `VELXTRIA_DATA_DIR`; run `python portal.py`. Back up the original DB before any upgrade.

**Not yet included:** full cross-module integration/security suite, migration/restore wizard, customer onboarding, reliability monitoring, and production certification. Older modules have not all been audited for tenant isolation. Do not expose the local portal publicly or accept sensitive customer data.
