import unittest
from revenue_dominion_v60 import SaaSScenario, analyze, compare


class RevenueDominionTests(unittest.TestCase):
    def test_base_case(self):
        result = analyze(SaaSScenario(100, "49", "9", "1000", ".05", "100", 10))
        self.assertEqual(result["monthly_recurring_revenue"], "4900.00")
        self.assertEqual(result["monthly_operating_contribution"], "2000.00")
        self.assertEqual(result["break_even_active_customers_excluding_acquisition"], 25)
        self.assertEqual(result["simplified_contribution_ltv"], "800.00")
        self.assertEqual(result["simplified_cac_payback_months"], "2.50")

    def test_unprofitable_customer(self):
        result = analyze(SaaSScenario(1, 10, 20, 0, ".1", 0))
        self.assertEqual(result["monthly_operating_contribution"], "-10.00")
        self.assertIsNone(result["break_even_active_customers_excluding_acquisition"])
        self.assertIsNone(result["simplified_contribution_ltv"])

    def test_zero_churn_does_not_invent_ltv(self):
        self.assertIsNone(analyze(SaaSScenario(1, 50, 10, 0, 0, 5))["simplified_contribution_ltv"])

    def test_zero_cac_does_not_divide_by_zero(self):
        self.assertIsNone(analyze(SaaSScenario(1, 50, 10, 0, ".1", 0))["ltv_to_cac"])

    def test_bad_inputs(self):
        for value in ("NaN", "Infinity", -1):
            with self.assertRaises(ValueError):
                analyze(SaaSScenario(1, value, 0, 0, ".1", 0))
        with self.assertRaises(ValueError):
            analyze(SaaSScenario(True, 10, 0, 0, ".1", 0))
        with self.assertRaises(ValueError):
            analyze(SaaSScenario(1, 10, 0, 0, "1.1", 0))

    def test_compare(self):
        s = SaaSScenario(1, 49, 9, 0, ".1", 10)
        self.assertEqual(len(compare({"base": s, "higher": s})), 2)
        with self.assertRaises(ValueError):
            compare({})


if __name__ == "__main__":
    unittest.main()
