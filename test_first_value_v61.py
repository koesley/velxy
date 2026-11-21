import unittest
from datetime import datetime, timedelta, timezone
from first_value_v61 import ProductEvent, analyze_activation

T = datetime(2026, 1, 1, tzinfo=timezone.utc)


def ev(w, c, kind, days=0, hours=0):
    return ProductEvent(w, c, kind, T + timedelta(days=days, hours=hours))


class FirstValueTests(unittest.TestCase):
    def test_activation_and_tenant_isolation(self):
        rows = [ev("a", "one", "signup"), ev("a", "one", "first_value", hours=2),
                ev("a", "one", "paid", days=1), ev("a", "one", "returned", days=7),
                ev("a", "two", "signup"), ev("b", "three", "signup")]
        r = analyze_activation(rows, "a", T + timedelta(days=31))
        self.assertEqual(r["signups"], 2)
        self.assertEqual(r["activated"], 1)
        self.assertEqual(r["activation_rate_pct"], 50)
        self.assertEqual(r["paid_customers_observed"], 1)
        self.assertEqual(r["median_time_to_first_value_hours"], 2)
        self.assertEqual(r["day_n_retention"]["7"]["rate_pct"], 50)
        self.assertIsNone(r["day_n_retention"]["90"]["rate_pct"])

    def test_no_future_or_presignup_activation(self):
        rows = [ev("a", "x", "first_value", days=-1), ev("a", "x", "signup"),
                ev("a", "x", "first_value", days=100)]
        r = analyze_activation(rows, "a", T + timedelta(days=1))
        self.assertEqual(r["activated"], 0)

    def test_missing_signup_and_empty(self):
        r = analyze_activation([ev("a", "x", "paid")], "a", T)
        self.assertEqual(r["signups"], 0)
        self.assertEqual(r["customers_with_events_but_no_signup"], 1)
        self.assertIsNone(r["activation_rate_pct"])

    def test_invalid_timestamp(self):
        with self.assertRaises(ValueError):
            analyze_activation([ProductEvent("a", "x", "signup", datetime(2026, 1, 1))], "a", T)

    def test_duplicate_events_do_not_inflate_counts(self):
        rows = [ev("a", "x", "signup"), ev("a", "x", "signup"),
                ev("a", "x", "first_value"), ev("a", "x", "first_value")]
        r = analyze_activation(rows, "a", T + timedelta(days=1))
        self.assertEqual((r["signups"], r["activated"]), (1, 1))


    def test_seven_day_activation_uses_only_mature_signups(self):
        rows = [ev("a", "fast", "signup"), ev("a", "fast", "first_value", days=2),
                ev("a", "late", "signup"), ev("a", "late", "first_value", days=8),
                ev("a", "recent", "signup", days=8),
                ev("a", "recent", "first_value", days=8, hours=1),
                ev("b", "other", "signup"), ev("b", "other", "first_value")]
        result = analyze_activation(rows, "a", T + timedelta(days=10))
        self.assertEqual(result["seven_day_activation"],
                         {"eligible": 2, "activated": 1, "rate_pct": 50.0})
        self.assertEqual(result["activated"], 3)

    def test_seven_day_activation_no_mature_cohort(self):
        result = analyze_activation([ev("a", "new", "signup", days=8)],
                                    "a", T + timedelta(days=10))
        self.assertEqual(result["seven_day_activation"],
                         {"eligible": 0, "activated": 0, "rate_pct": None})

if __name__ == "__main__":
    unittest.main()
