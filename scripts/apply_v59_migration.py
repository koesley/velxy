"""Explicit V59 PostgreSQL migration runner. Never runs on import or app startup.

Usage:
    VELXTRIA_DATABASE_URL=... python scripts/apply_v59_migration.py --apply
Run against staging first. Existing database credentials are read only from environment.
"""
import argparse
import os
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Apply additive V59 PostgreSQL schema")
    parser.add_argument("--apply", action="store_true", help="Actually execute migration")
    args = parser.parse_args()
    sql_path = Path(__file__).resolve().parents[1] / "migrations" / "v59_001_postgres.sql"
    sql = sql_path.read_text(encoding="utf-8")
    if not args.apply:
        print("DRY RUN: migration exists; pass --apply to execute on the configured database.")
        print("File:", sql_path)
        return
    url = os.environ.get("VELXTRIA_DATABASE_URL", "")
    if not url.startswith(("postgresql://", "postgres://")):
        raise SystemExit("A PostgreSQL VELXTRIA_DATABASE_URL is required")
    import psycopg
    with psycopg.connect(url, connect_timeout=10) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
    print("V59 schema migration applied successfully.")

if __name__ == "__main__":
    main()
