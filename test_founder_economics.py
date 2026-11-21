import unittest
from urllib.parse import parse_qs
from founder_economics import FIELDS, evaluate, render


def defaults():
    return {name: default for name, _, default in FIELDS}


class FounderEconomicsTests(unittest.TestCase):
    def test_scenario_math_and_acquisition_inclusive_break_even(self):
        data = defaults()
        data.update(active_customers="10", monthly_fixed_cost="100",
                    new_customers_per_month="2", acquisition_cost_per_customer="25")
        result = evaluate(data)
        self.assertEqual(result["monthly_recurring_revenue"], "490.00")
        self.assertEqual(result["monthly_acquisition_spend"], "50.00")
        self.assertEqual(result["monthly_operating_contribution"], "290.00")
        self.assertEqual(result["break_even_active_customers_including_assumed_acquisition"], 4)

    def test_empty_page_is_form_only(self):
        html = render({})
        self.assertIn('action="/founder-economics"', html)
        self.assertNotIn("Calculated scenario", html)
        self.assertIn("not shown here", html)

    def test_duplicate_parameters_rejected(self):
        query = {name: [value] for name, value in defaults().items()}
        query["monthly_price"] = ["49", "999"]
        html = render(query)
        self.assertIn("exactly once", html)
        self.assertNotIn("Calculated scenario", html)

    def test_html_injection_escaped(self):
        query = {name: [value] for name, value in defaults().items()}
        query["monthly_price"] = ['<script>alert(1)</script>']
        html = render(query)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("Invalid scenario", html)

    def test_invalid_money_and_churn(self):
        for field, value in (("monthly_price", "-1"), ("monthly_price", "NaN"),
                             ("monthly_churn_rate", "1.1"), ("monthly_fixed_cost", "Infinity")):
            data = defaults()
            data[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                evaluate(data)

    def test_invalid_customer_counts(self):
        for value in ("-1", "1.5", "999999999", "1e2", " 2 "):
            data = defaults()
            data["active_customers"] = value
            if value == " 2 ":
                self.assertEqual(evaluate(data)["active_customers"], 2)
            else:
                with self.subTest(value=value), self.assertRaises(ValueError):
                    evaluate(data)

    def test_missing_extra_and_oversized_rejected(self):
        data = defaults()
        del data["monthly_price"]
        with self.assertRaises(ValueError):
            evaluate(data)
        data = defaults()
        data["unknown"] = "1"
        with self.assertRaises(ValueError):
            evaluate(data)
        data = defaults()
        data["monthly_price"] = "9" * 41
        with self.assertRaises(ValueError):
            evaluate(data)

    def test_zero_margin_is_explicitly_undefined(self):
        data = defaults()
        data["monthly_price"] = "0"
        result = evaluate(data)
        self.assertIsNone(result["break_even_active_customers_including_assumed_acquisition"])
        self.assertIsNone(result["monthly_contribution_margin_pct"])

    def test_no_false_activation_rate(self):
        html = render({name: [value] for name, value in defaults().items()})
        self.assertIn("Calculated scenario", html)
        self.assertIn("aggregate site events do not", html)
        self.assertNotIn("verified subscriptions", html.split("<h3>Calculated scenario</h3>")[1])


if __name__ == "__main__":
    unittest.main()
