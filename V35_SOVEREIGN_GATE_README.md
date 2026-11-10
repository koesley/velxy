# VELXTRIA V35 — Sovereign Gate

## Significant changes
- Release candidates now require a recent, passing, checksum-verified Sentinel V34 regression report attached to that exact candidate before the portal permits owner approval.
- Evidence is workspace-scoped, and only owners/editors can attach it. Review decisions remain owner-only.
- The report must have been completed within 24 hours, have a complete output capture, and pass the SHA-256 integrity check.
- The gate is enforced on the portal's V33 approval path, not merely presented as UI text.
- A new `/sovereign-gate` dashboard lists eligible reports, candidate gate status, evidence attachment forms, and review/attachment audit events.
- New SQLite tables are created automatically without deleting existing records.
- Four dedicated tests cover integrity checks, expiration, workspace isolation and output escaping. The full bundled regression suite also runs.

## Local operator workflow
1. Back up your existing SQLite database. Keep `VELXTRIA_DATA_DIR` pointing to its current directory.
2. Launch the local portal with `VELXTRIA_LOCAL_STUDIO=1` and `VELXTRIA_DEPLOYMENT_MODE=local`.
3. Create a Horizon improvement and V33 release candidate, record human test notes, and verify the Horizon plan.
4. In a separate terminal, run `python sentinel_v34.py run` to execute the bundled regression tests in a temporary database directory.
5. Visit `/sovereign-gate` to attach the recent passing report to the correct release candidate.
6. The workspace owner can approve from `/evolutionary-core` while evidence remains valid.

## Important limitations
- Existing approvals are not retroactively revoked.
- The test suite is primarily unit/integration tests; this is **not** browser end-to-end testing.
- SHA-256 checksums are not cryptographic signatures and do not protect against a malicious local operator.
- Human-recorded test notes and verified Horizon status remain separate requirements.
- No automatic deployment, production certification, or database restore is performed.
- The local Python API's optional `data_root` argument is for backward compatibility; the **web approval route** passes the data root and enforces the gate.
- This version remains a local development build, not production hardened.
