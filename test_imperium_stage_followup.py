import unittest
from unittest.mock import Mock, patch
import revenue_priority_live as live

class ImperiumFollowupTests(unittest.TestCase):
    def test_stage_specific_review(self):
        for status, expected in [('new', 'discovery question'), ('contacted', 'prior contact')]:
            with self.subTest(status=status):
                conn = Mock()
                conn.execute.return_value.fetchone.side_effect = [(status,), None]
                with patch.object(live.business_os_v59.core, 'access') as access, patch.object(live.business_os_v59, 'init'), patch.object(live.business_os_v59, 'propose') as propose:
                    live.propose_followup(conn, 1, 'w', 'l')
                    access.assert_called_once_with(conn, 1, 'w', write=True)
                    message = propose.call_args.args[-1]
                    self.assertIn(expected, message)
                    self.assertIn('contact permission', message)
                    self.assertIn('Do not send automatically', message)
