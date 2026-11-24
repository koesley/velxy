import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, patch
import winback


class ObservationBoundaryTests(unittest.TestCase):
    def test_only_valid_observed_paid_revenue_counts(self):
        ts = lambda day: int(datetime(2026, 11, day, tzinfo=timezone.utc).timestamp())
        conn = Mock()
        conn.execute.return_value.fetchall.side_effect = [
            [('A', ts(10)), ('B', ts(25))],
            [('2026-11-11', 'A', 2, '50'), ('2026-11-26', 'A', 1, '999'), ('2026-11-12', 'A', 1, 'NaN'), ('2026-11-13', 'A', 1, 'bad'), ('2026-11-10', 'A', 1, '20'), ('2026-11-14', 'A', 1, '-10')],
        ]
        with patch.object(winback, 'setup'):
            self.assertEqual(winback.recovery(conn, 1, now=ts(24)), (1, 1, Decimal('100')))
