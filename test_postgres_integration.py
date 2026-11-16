"""Real PostgreSQL smoke test, using a disposable CI database only.

Requires VELXTRIA_TEST_DATABASE_URL. Never connects to production by default.
"""
import os
import unittest

class PostgreSQLIntegrationTests(unittest.TestCase):
    def test_real_postgres_connection(self):
        url = os.environ.get("VELXTRIA_TEST_DATABASE_URL")
        if not url:
            self.skipTest("Disposable integration database not configured")
        import psycopg
        # Use the real production adapter but override its module-level URL
        # only for this isolated test process.
        import persistent
        original = persistent.DATABASE_URL
        try:
            persistent.DATABASE_URL = url
            with persistent.PgConnection() as conn:
                self.assertEqual(conn.execute("SELECT 1").fetchone(), (1,))
        finally:
            persistent.DATABASE_URL = original

if __name__ == "__main__":
    unittest.main()
