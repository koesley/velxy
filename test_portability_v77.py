import unittest
from datetime import datetime, timezone
from portability_v77 import ExportPart, build_manifest, verify_manifest
T = datetime(2026, 1, 1, tzinfo=timezone.utc)
class PortabilityTests(unittest.TestCase):
    def test_manifest_and_verify(self):
        parts = [ExportPart("contacts.json", b"[]", 0)]
        m = build_manifest("tenant-a", parts, T)
        self.assertTrue(verify_manifest(m, parts))
        self.assertEqual(m["total_bytes"], 2)
    def test_tampering_detected(self):
        parts = [ExportPart("contacts.json", b"[]", 0)]
        m = build_manifest("tenant-a", parts, T)
        self.assertFalse(verify_manifest(m, [ExportPart("contacts.json", b"{}", 0)]))
    def test_traversal_rejected(self):
        with self.assertRaises(ValueError):
            build_manifest("a", [ExportPart("../secrets", b"x", 1)], T)
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            build_manifest("a", [ExportPart("A.csv", b"x", 1), ExportPart("a.csv", b"x", 1)], T)
    def test_bad_count_rejected(self):
        with self.assertRaises(ValueError):
            build_manifest("a", [ExportPart("x.csv", b"x", True)], T)
    def test_missing_timezone_rejected(self):
        with self.assertRaises(ValueError):
            build_manifest("a", [ExportPart("x.csv", b"x", 1)], datetime(2026,1,1))
    def test_extra_part_rejected(self):
        p = [ExportPart("a.json", b"{}", 1)]
        m = build_manifest("a", p, T)
        self.assertFalse(verify_manifest(m, p + [ExportPart("b.json", b"{}", 1)]))
if __name__ == "__main__":
    unittest.main()
