import unittest
from unittest.mock import patch
import revenue_priority_live as live

class MonarchSummaryTests(unittest.TestCase):
    def test_summary_counts_displayed_opportunities(self):
        item = dict(title='Review new lead', priority_score=1, estimated_value='500',
                    confidence=.35, effort_hours=1, evidence='Manual value',
                    explanation='Heuristic', identifier='lead1')
        with patch.object(live, 'live_rankings', return_value=[item]):
            page = live.render(None, 1, 'workspace')
        self.assertIn('1 ranked opportunities displayed', page)
        self.assertIn('not collected revenue', page)
        self.assertIn('require approval', page)

    def test_empty_summary_is_not_shown(self):
        with patch.object(live, 'live_rankings', return_value=[]):
            page = live.render(None, 1, 'workspace')
        self.assertNotIn('Opportunity overview', page)
