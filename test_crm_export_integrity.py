"""Regression tests for complete, tenant-scoped, spreadsheet-safe CRM exports.

Run: python -m unittest test_crm_export_integrity -v
"""
import csv
import io
import sqlite3
import unittest
from unittest.mock import patch

import business_os_v59 as bos


class CRMExportIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        bos.init(self.db)
        self.addCleanup(self.db.close)

    def add(self, workspace, lid, name="Example", contact="example@example.test",
            source="Referral", value=42.5, created=100):
        self.db.execute(
            "INSERT INTO bos59_leads "
            "(id,workspace_id,name,contact,source,value,status,created,updated) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (lid, workspace, name, contact, source, value, "new", created, created))

    def export(self, workspace="tenant-a"):
        with patch.object(bos.core, "access", return_value="owner") as access:
            output = bos.export_csv(self.db, 7, workspace)
            access.assert_called_once_with(self.db, 7, workspace)
        return list(csv.DictReader(io.StringIO(output)))

    def test_exports_beyond_dashboard_preview_limit(self):
        for n in range(305):
            self.add("tenant-a", "lead-%03d" % n, created=n)
        rows = self.export()
        self.assertEqual(len(rows), 305)
        self.assertEqual(rows[0]["id"], "lead-304")
        self.assertEqual(rows[-1]["id"], "lead-000")

    def test_workspace_isolation(self):
        self.add("tenant-a", "mine")
        self.add("tenant-b", "secret", contact="private@example.test")
        rows = self.export()
        self.assertEqual([r["id"] for r in rows], ["mine"])
        self.assertNotIn("private@example.test", str(rows))

    def test_denied_authorization_does_not_export(self):
        with patch.object(bos.core, "access", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                bos.export_csv(self.db, 7, "tenant-b")

    def test_formula_values_are_neutralized_without_mutating_db(self):
        self.add("tenant-a", "formula", name=" =HYPERLINK(1)",
                 contact="\t@SUM(1)", source="-2+3")
        row = self.export()[0]
        self.assertEqual(row["name"], "' =HYPERLINK(1)")
        self.assertEqual(row["contact"], "'\t@SUM(1)")
        self.assertEqual(row["source"], "'-2+3")
        original = self.db.execute(
            "SELECT name FROM bos59_leads WHERE id='formula'").fetchone()[0]
        self.assertEqual(original, " =HYPERLINK(1)")

    def test_numeric_values_and_csv_quoting_remain_compatible(self):
        self.add("tenant-a", "safe", name='Acme, "Inc"', value=125.75)
        row = self.export()[0]
        self.assertEqual(row["name"], 'Acme, "Inc"')
        self.assertEqual(row["value"], "125.75")
        self.assertEqual(row["created"], "100")

    def test_over_limit_fails_instead_of_silent_truncation(self):
        self.add("tenant-a", "one")
        self.add("tenant-a", "two")
        with patch.object(bos, "CRM_EXPORT_LIMIT", 1):
            with self.assertRaisesRegex(ValueError, "exceeds"):
                self.export()

    def test_empty_workspace_has_headers(self):
        self.assertEqual(self.export(), [])


if __name__ == "__main__":
    unittest.main()
