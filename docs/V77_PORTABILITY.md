# VELXTRIA V77 — Portable Export Manifest

A standalone, standard-library-only integrity manifest for customer data exports. It creates a record-count and SHA-256 inventory of caller-provided files and detects modified, omitted or extra files during verification. It does **not** export live data, prove completeness, authenticate users, delete accounts, or change billing.

Run: `python -m unittest -v test_portability_v77.py`

## Production integration required
1. Authenticate and authorize the workspace owner/admin, including scope and download permission.
2. Enumerate all permitted datasets, attachments, and relationships; document exclusions.
3. Generate files privately with row and size limits, CSV injection protections, retention expiry, and an audit log.
4. Deliver via an authenticated expiring download; validate the manifest against generated files.
5. Add an authenticated UI, end-to-end tests, and deletion/retention workflows separately.
6. Do not call an export complete until independently reconciled with the authoritative source.
