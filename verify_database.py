"""Read-only database connectivity probe for VELXTRIA.

Run in the deployed service environment:
    python verify_database.py

Never prints connection strings, passwords, or exception details.
Exit 0: PostgreSQL SELECT 1 succeeded.
Exit 1: PostgreSQL not configured.
Exit 2: connection or query failed.
"""
import sys

def check(connect=None):
    import persistent
    if not persistent.REMOTE:
        return "not_configured"
    if connect is None:
        connect = persistent.PgConnection
    try:
        with connect() as conn:
            row = conn.execute("SELECT 1").fetchone()
            return "connected" if row == (1,) else "failed"
    except Exception:
        return "failed"

def main():
    result = check()
    print("VELXTRIA PostgreSQL probe:", result)
    return {"connected": 0, "not_configured": 1, "failed": 2}[result]

if __name__ == "__main__":
    sys.exit(main())
