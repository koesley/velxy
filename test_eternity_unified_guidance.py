import unittest
from demo_guidance import recommend

class UnifiedGuidanceTests(unittest.TestCase):
    def test_channel_policy(self):
        for channel in ('web', 'email'):
            self.assertTrue(recommend(3, 1, channel=channel).startswith('Review flagged'))
            self.assertTrue(recommend(3, 0, channel=channel).startswith('Compare monthly'))
            self.assertTrue(recommend(0, 0, channel=channel).startswith('Upload'))
