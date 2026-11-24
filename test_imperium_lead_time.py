import unittest
from unittest.mock import Mock, patch
import revenue_priority_live as live

class LeadTimeTests(unittest.TestCase):
    def test_future_and_negative_timestamps_excluded(self):
        conn = Mock()
        conn.execute.return_value.fetchall.return_value = [
            ('future', '100', 'new', 100001),
            ('negative', '100', 'new', -1),
            ('valid', '100', 'new', 99999),
        ]
        with patch.object(live.business_os_v59.core, 'access'), patch.object(live.business_os_v59, 'init'), patch.object(live.time, 'time', return_value=100000):
            result = live.live_rankings(conn, 1, 'workspace')
        self.assertEqual([item['identifier'] for item in result], ['valid'])
