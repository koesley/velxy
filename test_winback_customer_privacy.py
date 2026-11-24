import unittest
from unittest.mock import patch
from decimal import Decimal
import winback

class WinbackCustomerPrivacyTests(unittest.TestCase):
    def test_draft_keeps_lifetime_value_internal(self):
        customer = dict(customer='Alex', last_product='Haircut',
                        last_date='2026-01-01', lifetime=Decimal('9876.54'),
                        days_quiet=100)
        with patch('money_report.quiet_customers', return_value=[customer]), patch('winback.setup'), patch('winback.sent_for_spell', return_value=None):
            draft = winback.drafts(None, 1)[0]
        self.assertEqual(draft['lifetime'], Decimal('9876.54'))
        self.assertIn('Alex', draft['text'])
        self.assertIn('Haircut', draft['text'])
        self.assertNotIn('9876', draft['text'])
        self.assertNotIn('9,876', draft['text'])
        self.assertIn('another visit', draft['text'])
