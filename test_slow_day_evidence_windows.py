import unittest
from datetime import datetime, timezone
from unittest.mock import Mock
import slow_days


class EvidenceWindowTests(unittest.TestCase):
    def test_complete_weeks_and_full_customer_band(self):
        conn = Mock()
        rows = [('2026-11-10', 'Recent', 'Service', 1, 10)] * 10
        rows += [('2026-10-25', 'Boundary', 'Service', 1, 10), ('2026-11-24', 'Recent', 'Service', 1, 10), ('2026-12-01', 'Boundary', 'Service', 1, 10), ('invalid', 'Bad', 'Service', 1, 10)]
        conn.execute.return_value.fetchall.return_value = rows
        now = int(datetime(2026, 11, 24, tzinfo=timezone.utc).timestamp())
        result = slow_days.filler(conn, 1, now)
        self.assertEqual([c['customer'] for c in result['candidates']], ['Boundary'])
        self.assertNotIn('open slot', result['candidates'][0]['text'])
        conn.execute.return_value.fetchall.return_value = rows[1:10] + rows[10:]
        self.assertIsNone(slow_days.filler(conn, 1, now))
