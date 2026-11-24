import unittest
from demo_guidance import recommend

class SeverityTests(unittest.TestCase):
    def test_severity_across_channels(self):
        for channel in ('web','email'):
            for accepted,rejected,phrase in [(0,4,'No rows passed'),(2,2,'At least half'),(9,1,'totals incomplete')]:
                self.assertIn(phrase,recommend(accepted,rejected,channel=channel))
            self.assertNotIn('At least half',recommend(3,0,channel=channel))
