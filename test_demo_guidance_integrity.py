import unittest

from demo_guidance import recommend


class GuidanceIntegrityTests(unittest.TestCase):
    def test_invalid_counts_fail_closed(self):
        for channel in ('web', 'email'):
            for invalid in (-1, True, False, 1.5, '2', None, float('nan')):
                for accepted, rejected in ((invalid, 1), (1, invalid)):
                    with self.subTest(channel=channel, accepted=accepted, rejected=rejected):
                        self.assertIn('Report counts are invalid', recommend(accepted, rejected, channel=channel))

    def test_valid_counts_preserve_guidance(self):
        for channel in ('web', 'email'):
            for accepted, rejected, expected in ((0, 0, 'Upload'), (0, 2, 'No rows passed'), (2, 2, 'At least half'), (3, 1, 'totals incomplete'), (3, 0, 'Compare monthly')):
                with self.subTest(channel=channel, accepted=accepted, rejected=rejected):
                    self.assertIn(expected, recommend(accepted, rejected, channel=channel))


if __name__ == '__main__':
    unittest.main()
