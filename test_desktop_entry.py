import os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import desktop_entry

class DesktopEntryTests(unittest.TestCase):
    def test_configure_is_local_and_disables_cloud(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"LOCALAPPDATA": tmp, "VELXTRIA_DATABASE_URL": "postgres://example", "VELXTRIA_REQUIRE_PERSISTENCE": "1", "VELXTRIA_SMTP_HOST": "mail"}):
                desktop_entry.configure()
                self.assertEqual(os.environ["VELXTRIA_DEPLOYMENT_MODE"], "local")
                self.assertEqual(os.environ["VELXTRIA_LOCAL_STUDIO"], "1")
                self.assertTrue(Path(os.environ["VELXTRIA_DATA_DIR"]).is_dir())
                for key in ("VELXTRIA_DATABASE_URL", "VELXTRIA_REQUIRE_PERSISTENCE", "VELXTRIA_SMTP_HOST"):
                    self.assertNotIn(key, os.environ)
    def test_health_check_rejects_connection_failure(self):
        with self.assertRaises(Exception):
            desktop_entry.health_check("http://127.0.0.1:1/")
if __name__ == "__main__": unittest.main()
