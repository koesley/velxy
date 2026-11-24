import unittest
from unittest.mock import Mock, patch

import revenue_priority_live as live


class InvalidLeadTests(unittest.TestCase):
    def test_invalid_values_do_not_block_valid_rankings(self):
        conn = Mock()
        conn.execute.return_value.fetchall.return_value = [
            (1, 'not money', 'new', 100),
            (2, None, 'new', 100),
            (3, 'NaN', 'new', 100),
            (4, 'Infinity', 'contacted', 100),
            (5, '1250.50', 'contacted', 100),
        ]
        with patch.object(live.business_os_v59.core, 'access') as access, patch.object(live.business_os_v59, 'init'), patch.object(live.time, 'time', return_value=100):
            result = live.live_rankings(conn, 7, 9)
        access.assert_called_once_with(conn, 7, 9)
        self.assertEqual([row['identifier'] for row in result], ['5'])
        self.assertEqual(result[0]['estimated_value'], '1250.50')
        self.assertEqual(conn.execute.call_args.args[1], (9,))
