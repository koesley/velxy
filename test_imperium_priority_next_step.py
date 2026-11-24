import unittest
from unittest.mock import patch
import revenue_priority_live as live

class NextStepTests(unittest.TestCase):
    def test_stage_guidance_visible_before_draft(self):
        base = dict(priority_score=1, estimated_value='100', confidence=.35,
                    effort_hours=1, evidence='Manual estimate', explanation='Heuristic')
        items = [dict(base, title='Review new lead', identifier='a'),
                 dict(base, title='Review contacted lead', identifier='b')]
        with patch.object(live, 'live_rankings', return_value=items):
            page = live.render(None, 1, 'workspace')
        self.assertIn('Confirm the customer', page)
        self.assertIn('Review prior replies', page)
        self.assertEqual(page.count('Suggested next step:'), 2)
