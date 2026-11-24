import unittest
from unittest.mock import patch
import revenue_priority_live as live

class CoverageTests(unittest.TestCase):
    def test_empty_batch_discloses_selection_limits(self):
        with patch.object(live, 'live_rankings', return_value=[]):
            page = live.render(None, 1, 'workspace')
        self.assertIn('300 oldest-updated', page)
        self.assertIn('top 20', page)
        self.assertIn('newer leads may not have been evaluated', page)
        self.assertIn('in the evaluated batch', page)
