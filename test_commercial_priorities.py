import unittest
from commercial_priorities import commercial_priorities, commercial_priority_html, STAGES
from site_stats import stats_html

class CommercialPriorityTests(unittest.TestCase):
    def test_errors_first(self):
        rows = commercial_priorities([(0, {'checkout_failed': 2}), (1, {'checkout_failed': 3, 'checkout_unavailable': 1})])
        self.assertEqual(rows[0][:3], ('Observed event', 'Payment availability', 1))
        self.assertEqual(rows[1][:3], ('Observed event', 'Payment reliability', 5))
    def test_empty_is_gap(self):
        self.assertTrue(all(r[0] == 'Evidence gap' for r in commercial_priorities([])))
    def test_complete_requires_reconciliation(self):
        rows = commercial_priorities([(0, {key: 1 for key, _, _ in STAGES})])
        self.assertEqual(rows[0][0], 'Verification')
    def test_optional_email_not_gate(self):
        self.assertNotIn('email', str(commercial_priorities([])).lower())
    def test_founder_integration(self):
        self.assertIn('Commercial action queue', stats_html({}, [], []))
    def test_limitations(self):
        self.assertIn('not unique buyers', commercial_priority_html([]))
        self.assertIn('No actions are executed automatically', commercial_priority_html([]))

    def test_checkout_follow_through(self):
        rows = commercial_priorities([(0, {'checkout_started': 3})])
        self.assertEqual(rows[0][:3], ('Verification', 'Checkout follow-through', 3))
    def test_coverage_snapshot(self):
        page = commercial_priority_html(iter([(0, {'checkout_started': 2}), (86400, {'pro_activated': 1})]))
        self.assertIn('2 UTC dates with recorded activity; 2 checkout starts; 1 PRO activation events', page)
    def test_no_telemetry_snapshot(self):
        self.assertIn('No recent telemetry available', commercial_priority_html([]))
