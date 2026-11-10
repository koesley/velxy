# VELXTRIA V11 — Titan Recovery Foundation

This release builds on V10 Trinity without replacing its database or mission history.

## New features

- Authenticated `/recovery` portal page with local database integrity status, data directory, and backup inventory.
- `python recovery_v11.py backup` creates a consistent SQLite snapshot using SQLite's backup API, checks database integrity, writes a checksum manifest, verifies the archive, and atomically publishes it in `VELXTRIA_DATA_DIR/velxtria_backups`.
- `python recovery_v11.py verify "path/to/backup.zip"` validates backup checksum and size.
- `python recovery_v11.py check` checks live SQLite database integrity.
- PostgreSQL deployments fail closed for SQLite backup commands and direct users to provider-managed backups.

## Important limits

- Back up your existing working database before installing new versions.
- The snapshot includes SQLite only, not uploaded report ZIPs, `.env` secrets, Supabase, or BTCPay configuration.
- Keep a second copy off-device. Backups in the same data directory are not disaster recovery.
- There is intentionally no automatic restore, deletion, or backup download endpoint.
- This release does NOT implement production-grade multi-tenant authorization, verified payment/subscription billing, or agent autonomy. Those require additional design, tests, and security review.
- For local use, ensure `VELXTRIA_DATA_DIR` points to the *existing* working data directory before launching.
