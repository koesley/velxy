"""Regression tests: PostgreSQL may run without Supabase, object storage fails closed."""
import os
import subprocess
import sys
import unittest

class PersistenceConfigurationTests(unittest.TestCase):
    def run_isolated(self, code, **settings):
        env = dict(os.environ)
        for key in ("VELXTRIA_DATABASE_URL", "VELXTRIA_REQUIRE_PERSISTENCE",
                    "VELXTRIA_SUPABASE_URL", "VELXTRIA_SUPABASE_SERVICE_KEY"):
            env.pop(key, None)
        env.update(settings)
        return subprocess.run([sys.executable, "-c", code], env=env,
                              capture_output=True, text=True, timeout=10)

    def test_postgres_without_supabase_can_import(self):
        p = self.run_isolated(
            "import persistent; assert persistent.REMOTE; "
            "assert persistent.DATABASE_URL == 'postgresql://example.invalid/test'",
            VELXTRIA_DATABASE_URL="postgresql://example.invalid/test",
            VELXTRIA_REQUIRE_PERSISTENCE="1")
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_report_storage_stays_fail_closed(self):
        p = self.run_isolated(
            "import persistent; "
            "persistent.store(1,'r',b'payload','/tmp/never-write')")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("Supabase Storage is not configured", p.stderr)

    def test_required_persistence_without_database_rejected(self):
        p = self.run_isolated("import persistent",
                              VELXTRIA_REQUIRE_PERSISTENCE="1")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("VELXTRIA_DATABASE_URL", p.stderr)

if __name__ == "__main__":
    unittest.main()
