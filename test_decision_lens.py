"""Decision Lens correctness, privacy and evidence regressions."""
import unittest
import decision_lens


def sample():
    return {
        'accepted': 7, 'rejected': 3,
        'monthly_rows': [['Month', 'Orders', 'Revenue'],
                         ['2026-09', '2', '200.00'],
                         ['2026-10', '5', '500.00']],
        'product_rows': [['Product', 'Orders', 'Revenue'],
                         ['Cleaning', '5', '600.00'],
                         ['Repairs', '2', '100.00']],
    }


class DecisionLensTests(unittest.TestCase):
    def test_evidence_and_actions_from_aggregates(self):
        result = decision_lens.recommendations(sample())
        self.assertEqual(len(result), 3)
        self.assertIn('3 of 10 rows flagged (30.0%)', result[0][1])
        self.assertIn('2026-10 revenue ($500.00) is higher', result[1][1])
        self.assertIn('Cleaning represents 85.7%', result[2][1])

    def test_does_not_claim_trends_from_one_month(self):
        report = sample()
        report['monthly_rows'] = report['monthly_rows'][:2]
        self.assertNotIn('Revenue movement', [x[0] for x in decision_lens.recommendations(report)])

    def test_escapes_untrusted_product_labels(self):
        report = sample()
        report['product_rows'][1][0] = '<script>alert(1)</script>'
        rendered = decision_lens.html_panel(report)
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;script&gt;', rendered)

    def test_invalid_revenue_is_ignored(self):
        report = sample()
        report['product_rows'][1][2] = 'NaN'
        report['monthly_rows'][2][2] = '-5'
        titles = [x[0] for x in decision_lens.recommendations(report)]
        self.assertNotIn('Revenue concentration', titles)
        self.assertNotIn('Revenue movement', titles)

    def test_zero_revenue_no_concentration_claim(self):
        report = sample()
        report['product_rows'][1][2] = '0'
        report['product_rows'][2][2] = '0'
        self.assertNotIn('Revenue concentration', [x[0] for x in decision_lens.recommendations(report)])

    def test_missing_data_yields_no_panel(self):
        self.assertEqual(decision_lens.html_panel({}), '')

    def test_capped_recommendations_and_no_pii(self):
        report = sample()
        report['customer_name'] = 'Secret Customer'
        panel = decision_lens.html_panel(report)
        self.assertEqual(panel.count('<li>'), 3)
        self.assertNotIn('Secret Customer', panel)
        self.assertIn('not an AI prediction', panel)


if __name__ == '__main__':
    unittest.main()
