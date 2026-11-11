"""Explicit V59-V62 PostgreSQL migration runner for VELXTRIA OMEGA.

Default is dry-run. Requires --apply to write. Use a staging database first.
Never runs during import, application startup, or deployment build.
"""
import argparse
import hashlib
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FILES=[f"migrations/v{n}_001_postgres.sql" for n in (59,60,61,62)]

def main():
    parser=argparse.ArgumentParser(description="Review or apply OMEGA schema migrations")
    parser.add_argument("--apply",action="store_true",help="Apply schema changes to the configured PostgreSQL database")
    args=parser.parse_args()
    scripts=[]
    for name in FILES:
        sql=(ROOT/name).read_text(encoding="utf-8")
        if not sql.strip().startswith("--") or "CREATE TABLE" not in sql:
            raise SystemExit(f"Invalid migration: {name}")
        scripts.append((name,sql,hashlib.sha256(sql.encode()).hexdigest()))
    print("Migrations in order:")
    for name,_,digest in scripts:print(f"  {name} sha256={digest}")
    if not args.apply:
        print("DRY RUN ONLY. No database connection or modifications were made.")
        print("To apply after staging verification and backup: python scripts/apply_omega_migrations.py --apply")
        return
    url=os.getenv("VELXTRIA_DATABASE_URL","")
    if not url.startswith(("postgresql://","postgres://")):
        raise SystemExit("PostgreSQL VELXTRIA_DATABASE_URL required; nothing applied")
    import psycopg
    # Migrations contain their own BEGIN/COMMIT; use autocommit for explicit boundaries.
    with psycopg.connect(url,connect_timeout=10,autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(621062)")
            try:
                cur.execute("""CREATE TABLE IF NOT EXISTS velxtria_schema_migrations (
                    name TEXT PRIMARY KEY, checksum TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
                for name,sql,digest in scripts:
                    cur.execute("SELECT checksum FROM velxtria_schema_migrations WHERE name=%s",(name,))
                    row=cur.fetchone()
                    if row:
                        if row[0]!=digest:raise RuntimeError(f"Migration content changed after application: {name}")
                        print(f"SKIP {name} (already applied)")
                        continue
                    # Preserve the migration's transaction and commit the ledger in the same transaction.
                    # Remove only its final COMMIT and append the ledger INSERT before committing.
                    trimmed=sql.strip()
                    if not trimmed.upper().endswith("COMMIT;"):
                        raise RuntimeError(f"Migration must end in COMMIT: {name}")
                    trimmed=trimmed[:-len("COMMIT;")]
                    try:
                        cur.execute(trimmed)
                        cur.execute("INSERT INTO velxtria_schema_migrations(name,checksum) VALUES (%s,%s)",(name,digest))
                        cur.execute("COMMIT")
                    except Exception:
                        cur.execute("ROLLBACK")
                        raise
                    print(f"APPLIED {name}")
            finally:
                cur.execute("SELECT pg_advisory_unlock(621062)")
    print("OMEGA migrations complete. Verify staging and application before enabling feature flags.")

if __name__=="__main__":main()
