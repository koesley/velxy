"""Regression tests for Revenue Scenario Lab."""
import unittest
from decimal import Decimal
import revenue_scenario_lab as lab


def report():
    return {'monthly_rows': [['Month', 'Orders', 'Revenue'],
                             ['2026-10', '3', '300.00'],
                             ['2026-11', '4', '700.00']],
            'product_rows': [['Product', 'Revenue'],
                             ['Service A', '800'], ['Service B', '200']],
            'customer': 'PRIVATE PERSON'}


class ScenarioTests(unittest.TestCase):
    def test_reconciled_revenue_and_four_scenarios(self):
        result = lab.scenario(report())
        self.assertEqual(result['baseline'], Decimal('1000'))
        self.assertEqual([case['revenue'] for case in result['cases']],
                         [Decimal('900'), Decimal('1000'),
                          Decimal('1100'), Decimal('1200')])

    def test_scenario_not_prediction_and_no_customer_data(self):
        rendered = lab.html_panel(report())
        self.assertIn('not forecasts', rendered)
        self.assertIn('$1,200.00', rendered)
        self.assertNotIn('PRIVATE PERSON', rendered)
        self.assertIn('scope="col"', rendered)

    def test_refuses_mismatched_summary_totals(self):
        data = report()
        data['product_rows'][1][1] = '700'
        self.assertIsNone(lab.scenario(data))

    def test_refuses_invalid_and_negative_values(self):
        for value in ('NaN', 'Infinity', '-1', 'not-money', ''):
            with self.subTest(value=value):
                data = report()
                data['monthly_rows'][1][2] = value
                self.assertEqual(lab.html_panel(data), '')

    def test_refuses_missing_or_ambiguous_headers(self):
        for header in (['Month', 'Sales'],
                       ['Month', 'Revenue', 'Revenue']):
            data = report()
            data['monthly_rows'][0] = header
            self.assertIsNone(lab.scenario(data))

    def test_refuses_partial_or_empty_summary(self):
        data = report()
        data['monthly_rows'][1] = ['2026-10']
        self.assertIsNone(lab.scenario(data))
        self.assertEqual(lab.html_panel({}), '')

    def test_zero_baseline_suppresses_scenario(self):
        data = report()
        for row in data['monthly_rows'][1:]:
            row[-1] = '0'
        for row in data['product_rows'][1:]:
            row[-1] = '0'
        self.assertIsNone(lab.scenario(data))

    def test_large_values_decimal_accuracy(self):
        data = report()
        data['monthly_rows'] = [['Month', 'Revenue'],
                                ['2026-10', '999999999999.99']]
        data['product_rows'] = [['Product', 'Revenue'],
                                ['A', '999999999999.99']]
        self.assertEqual(lab.scenario(data)['baseline'],
                         Decimal('999999999999.99'))


if __name__ == '__main__':
    unittest.main()
