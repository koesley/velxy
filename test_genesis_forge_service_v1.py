"""Genesis Forge service tests: authorization before data access."""
import sqlite3
import unittest
from unittest.mock import patch
import genesis_forge_service_v1 as service


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_authorized_lifecycle(self):
        with patch.object(service.business_os.core, "access") as access:
            result = service.create_preview(self.conn, 7, "tenant_a", "My Operations")
            record = service.get_preview(self.conn, 7, "tenant_a", result["id"])
            self.assertEqual(record["manifest"]["name"], "My Operations")
            self.assertIn("My Operations", service.get_preview_html(
                self.conn, 7, "tenant_a", result["id"]))
            self.assertEqual(len(service.get_previews(self.conn, 7, "tenant_a")), 1)
            updated = service.update_preview(
                self.conn, 7, "tenant_a", result["id"], 1, "New Name")
            self.assertEqual(updated["revision"], 2)
            self.assertEqual(access.call_count, 5)
            self.assertEqual(access.call_args.kwargs, {"write": True})

    def test_denied_access_has_no_side_effects(self):
        with patch.object(service.business_os.core, "access",
                          side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                service.create_preview(self.conn, 7, "tenant_a", "Unauthorized")
            with self.assertRaises(PermissionError):
                service.get_previews(self.conn, 7, "tenant_a")
        row = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='genesis_previews'"
        ).fetchone()
        self.assertIsNone(row)

    def test_other_owner_cannot_read(self):
        with patch.object(service.business_os.core, "access"):
            result = service.create_preview(self.conn, 7, "tenant_a", "Private")
            with self.assertRaises(ValueError):
                service.get_preview(self.conn, 8, "tenant_a", result["id"])
            with self.assertRaises(ValueError):
                service.get_preview_html(self.conn, 8, "tenant_a", result["id"])

    def test_stale_revision_rejected(self):
        with patch.object(service.business_os.core, "access"):
            result = service.create_preview(self.conn, 7, "tenant_a", "First")
            service.update_preview(self.conn, 7, "tenant_a", result["id"], 1, "Second")
            with self.assertRaises(ValueError):
                service.update_preview(self.conn, 7, "tenant_a", result["id"], 1, "Stale")


if __name__ == "__main__":
    unittest.main()
