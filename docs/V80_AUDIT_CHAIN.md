# VELXTRIA V80 — Audit Chain Verifier

Standalone hash-chained, tenant-scoped audit event integrity helper. Each event records a workspace, sequence, actor, action, target and timestamp. A digest commits to the previous digest and canonical event payload.

Run: `python -m unittest -v test_audit_chain_v80.py`.

**Not yet production integrated.** To detect a deleted tail or full history rewrite, anchor the expected head independently in trusted storage. Enforce append-only writes, per-workspace serialized sequencing, authenticated actor attribution, trusted server timestamps, access controls, secret redaction, retention, and same-transaction writes with actual business changes. Verify complete ordered history before displaying a trusted status. Hashes alone do not establish authenticity or regulatory compliance.
