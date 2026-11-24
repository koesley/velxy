import unittest
import demo_shares

class EmptyDemoTests(unittest.TestCase):
    def test_empty_input_does_not_claim_perfect_quality(self):
        self.assertEqual(demo_shares.scorecard({})['clean_pct'], 0)
        self.assertEqual(demo_shares._scorecard_from_stored(0, 0, '', [])['clean_pct'], 0)

    def test_nonempty_input_preserves_quality(self):
        self.assertEqual(demo_shares.scorecard({'accepted': 3, 'rejected': 1})['clean_pct'], 75)
