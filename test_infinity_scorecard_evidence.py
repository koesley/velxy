import unittest
import demo_shares

class ScorecardEvidenceTests(unittest.TestCase):
    def test_empty_and_rejected_only_are_distinct(self):
        self.assertFalse(demo_shares.scorecard({})['has_data'])
        self.assertTrue(demo_shares.scorecard({'rejected': 3})['has_data'])
        self.assertFalse(demo_shares._scorecard_from_stored(0, 0, '', [])['has_data'])
        self.assertTrue(demo_shares._scorecard_from_stored(0, 3, '', [])['has_data'])
