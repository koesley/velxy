import unittest
from data_trust_v76 import assess

NOW = 2000000000
GOOD = {"connected": True, "token_status": "valid", "cadence": "hourly",
        "last_state": "success", "last_run": NOW - 60}

class TrustTests(unittest.TestCase):
    def test_recent_sync_does_not_authorize_automation(self):
        result = assess(GOOD, NOW)
        self.assertEqual(result["status"], "recent_sync_observed")
        self.assertFalse(result["safe_for_automation"])

    def test_disconnected(self):
        self.assertEqual(assess({"connected": False}, NOW)["status"], "disconnected")

    def test_stale(self):
        result = assess({**GOOD, "last_run": NOW - 7201}, NOW)
        self.assertEqual(result["status"], "untrusted")
        self.assertTrue(any("older" in r for r in result["reasons"]))

    def test_failure_blocks(self):
        self.assertEqual(assess({**GOOD, "last_state": "failed"}, NOW)["status"], "untrusted")

    def test_bad_timestamp_blocks(self):
        for value in (None, True, NOW+1, "123"):
            with self.subTest(value=value):
                self.assertEqual(assess({**GOOD, "last_run": value}, NOW)["status"], "untrusted")

    def test_disabled_schedule_blocks(self):
        self.assertEqual(assess({**GOOD, "cadence": "off"}, NOW)["status"], "untrusted")

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            assess([], NOW)

if __name__ == "__main__":
    unittest.main()
