import unittest
from unittest.mock import patch
import revenue_priority_live as live

def item(value):
    return dict(title='Review lead', priority_score=1, estimated_value=value,
                confidence=.35, effort_hours=1, evidence='Manual value',
                explanation='Heuristic', identifier='lead')

class PipelineValueTests(unittest.TestCase):
    def test_decimal_total(self):
        with patch.object(live, 'live_rankings', return_value=[item('100.10'), item('200.20')]):
            page = live.render(None, 1, 'workspace')
        self.assertIn('$300.30', page)
        self.assertIn('unweighted estimates; not collected revenue', page)

    def test_extreme_value(self):
        with patch.object(live, 'live_rankings', return_value=[item('1E+1000000')]):
            page = live.render(None, 1, 'workspace')
        self.assertIn('Estimated total unavailable', page)
