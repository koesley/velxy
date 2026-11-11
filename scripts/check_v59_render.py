"""Read-only V59 Render readiness checks.

Usage: python scripts/check_v59_render.py
No schema changes, writes, or deployment actions are performed.
"""
import os
import sys

TABLES = (
    "v59_contacts", "v59_deals", "v59_audits",
    "v59_workflows", "v59_runs", "v59_agents", "v59_agent_runs",
)

def main():
    url = os.getenv("VELXTRIA_DATABASE_URL", "")
    if not url.startswith(("postgresql://", "postgres://")):
        print("BLOCKED: PostgreSQL VELXTRIA_DATABASE_URL is not configured.")
        return 2
    if not (os.getenv("VELXTRIA_SUPABASE_URL") and os.getenv("VELXTRIA_SUPABASE_SERVICE_KEY")):
        print("BLOCKED: remote storage credentials are missing.")
        return 2
    try:
        import psycopg
        with psycopg.connect(url, connect_timeout=10) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = current_schema() AND table_name = ANY(%s)",
                    (list(TABLES),),
                )
                present = {row[0] for row in cursor.fetchall()}
                cursor.execute(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = current_schema() AND table_name = 'empire_members'"
                )
                membership = cursor.fetchone() is not None
            conn.rollback()  # read-only; no changes
    except Exception as exc:
        print("BLOCKED: database verification failed:", type(exc).__name__)
        return 2
    missing = sorted(set(TABLES) - present)
    if not membership:
        print("BLOCKED: existing empire_members authorization table missing.")
    if missing:
        print("BLOCKED: missing V59 tables:", ", ".join(missing))
    if not membership or missing:
        print("Do not enable remote V59 routes. Apply and test migrations in staging first.")
        return 1
    print("PASS: PostgreSQL connectivity and expected V59 tables verified.")
    print("NOTE: this does not verify V59 application integration, tests, or production readiness.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
