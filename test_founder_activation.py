"""Regression tests for V61 founder saved-report activation cohorts."""
import sqlite3
import unittest

import founder_activation

DAY = 86400
NOW = 150 * DAY


class FounderActivationTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, created INTEGER, role TEXT)")
        self.db.execute("CREATE TABLE reports (id TEXT, user_id INTEGER, created INTEGER, status TEXT)")

    def tearDown(self):
        self.db.close()

    def user(self, uid, age_days, role="customer"):
        self.db.execute("INSERT INTO users VALUES (?,?,?)", (uid, NOW - age_days * DAY, role))

    def report(self, ident, uid, days_ago, status="ready"):
        self.db.execute("INSERT INTO reports VALUES (?,?,?,?)", (ident, uid, NOW - days_ago * DAY, status))

    def test_mature_and_immature_cohorts(self):
        self.user(1, 20)
        self.user(2, 10)
        self.user(3, 3)
        self.report("a", 1, 19)
        self.report("b", 2, 1)
        self.report("c", 3, 2)
        m = founder_activation.report_activation(self.db, NOW)
        self.assertEqual((m["signup_accounts"], m["mature_seven_day_cohort"],
                          m["saved_report_within_seven_days"], m["seven_day_rate_pct"]),
                         (3, 2, 1, 50.0))

    def test_ignores_admin_failed_and_presignup_reports(self):
        self.user(1, 15)
        self.user(2, 15, "admin")
        self.report("bad", 1, 14, "failed")
        self.report("early", 1, 16)
        self.report("admin", 2, 14)
        m = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(m["signup_accounts"], 1)
        self.assertEqual(m["accounts_with_saved_report"], 0)

    def test_multiple_reports_count_once_and_boundary_is_exclusive(self):
        self.user(1, 10)
        self.report("at-boundary", 1, 3)
        self.report("later", 1, 2)
        m = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(m["saved_report_within_seven_days"], 0)
        self.assertEqual(m["accounts_with_saved_report"], 1)

    def test_no_mature_cohort_is_not_zero_percent(self):
        self.user(1, 1)
        m = founder_activation.report_activation(self.db, NOW)
        self.assertIsNone(m["seven_day_rate_pct"])
        self.assertIn("Not available", founder_activation.panel_html(m))

    def test_does_not_expose_customer_identifiers(self):
        self.user(1, 20)
        self.report("secret-report-id", 1, 19)
        html = founder_activation.panel_html(founder_activation.report_activation(self.db, NOW))
        self.assertNotIn("secret-report-id", html)
        self.assertIn("not proof of", html.lower())

    def test_future_records_excluded(self):
        self.db.execute("INSERT INTO users VALUES (?,?,?)", (5, NOW + DAY, "customer"))
        self.assertEqual(founder_activation.report_activation(self.db, NOW)["signup_accounts"], 0)

    def test_read_only(self):
        self.user(1, 10)
        self.db.execute("PRAGMA query_only=ON")
        self.assertEqual(founder_activation.report_activation(self.db, NOW)["mature_seven_day_cohort"], 1)


    def test_weekly_cohorts_count_only_mature_signups(self):
        self.user(1, 20)
        self.user(2, 19)
        self.user(3, 2)
        self.report("first", 1, 19)
        self.report("late", 2, 1)
        self.report("young", 3, 1)
        result = founder_activation.report_activation(self.db, NOW)
        weeks = result["weekly_cohorts"]
        self.assertEqual(sum(row[1] for row in weeks), 2)
        self.assertEqual(sum(row[2] for row in weeks), 1)
        self.assertNotIn("young", founder_activation.panel_html(result))

    def test_weekly_cohorts_exclude_admin_and_failed_reports(self):
        self.user(1, 21)
        self.user(2, 21, "admin")
        self.report("failed", 1, 20, "failed")
        self.report("admin", 2, 20)
        result = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(sum(row[1] for row in result["weekly_cohorts"]), 1)
        self.assertEqual(sum(row[2] for row in result["weekly_cohorts"]), 0)
        self.assertIn("Not activated does not mean churned", founder_activation.panel_html(result))

    def test_weekly_cohorts_are_bounded_to_eight(self):
        for uid in range(1, 15):
            self.user(uid, 8 + uid * 7)
        result = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(len(result["weekly_cohorts"]), 8)
        self.assertEqual(result["mature_seven_day_cohort"], 14)
        self.assertEqual(list(result["weekly_cohorts"]), sorted(result["weekly_cohorts"], reverse=True))

    def test_weekly_cohorts_no_mature_signups(self):
        self.user(1, 1)
        result = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(result["weekly_cohorts"], ())
        self.assertIn("No mature signup weeks", founder_activation.panel_html(result))


    def test_mature_dropoff_segments_are_disjoint(self):
        self.user(1, 20)
        self.user(2, 20)
        self.user(3, 20)
        self.user(4, 20)
        self.report("fast", 1, 20)
        self.report("within-week", 2, 15)
        self.report("late", 3, 10)
        m = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(m["saved_report_within_one_day"], 1)
        self.assertEqual(m["saved_report_within_seven_days"], 2)
        self.assertEqual(m["saved_report_after_seven_days"], 1)
        self.assertEqual(m["mature_accounts_without_saved_report"], 1)
        self.assertEqual(m["mature_seven_day_cohort"],
                         m["saved_report_within_seven_days"] +
                         m["saved_report_after_seven_days"] +
                         m["mature_accounts_without_saved_report"])

    def test_one_day_and_seven_day_boundaries_are_exclusive(self):
        self.user(1, 10)
        self.user(2, 10)
        self.report("one-day-exact", 1, 9)
        self.report("seven-day-exact", 2, 3)
        m = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(m["saved_report_within_one_day"], 0)
        self.assertEqual(m["saved_report_within_seven_days"], 1)
        self.assertEqual(m["saved_report_after_seven_days"], 1)

    def test_immature_admin_and_failed_reports_not_in_diagnostics(self):
        self.user(1, 2)
        self.user(2, 20, "admin")
        self.user(3, 20)
        self.report("young", 1, 1)
        self.report("admin", 2, 19)
        self.report("failed", 3, 19, "failed")
        m = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(m["mature_accounts_without_saved_report"], 1)
        self.assertEqual(m["saved_report_within_one_day"], 0)
        self.assertEqual(m["saved_report_after_seven_days"], 0)

    def test_dashboard_diagnostics_are_aggregate_and_explained(self):
        self.user(1, 20)
        self.report("private-report-id", 1, 10)
        markup = founder_activation.panel_html(founder_activation.report_activation(self.db, NOW))
        self.assertIn("24-hour activation", markup)
        self.assertIn("not proof of churn", markup)
        self.assertNotIn("private-report-id", markup)


    def test_first_week_funnel_reconciles_to_seven_day_activation(self):
        for uid in range(1, 5):
            self.user(uid, 20)
        self.report("instant", 1, 20)
        self.report("next-day-boundary", 2, 19)
        self.report("six-days", 3, 14)
        self.report("late", 4, 12)
        m = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(m["saved_report_within_one_day"], 1)
        self.assertEqual(m["saved_report_days_one_to_seven"], 2)
        self.assertEqual(m["saved_report_within_seven_days"], 3)
        self.assertEqual(m["one_day_rate_pct"], 25.0)
        self.assertEqual(m["seven_day_lift_pct_points"], 50.0)
        self.assertEqual(m["seven_day_rate_pct"], 75.0)
        self.assertIn("percentage points", founder_activation.panel_html(m))

    def test_missing_mature_cohort_has_no_fabricated_funnel_rates(self):
        self.user(1, 2)
        m = founder_activation.report_activation(self.db, NOW)
        self.assertIsNone(m["one_day_rate_pct"])
        self.assertIsNone(m["seven_day_lift_pct_points"])
        self.assertEqual(m["saved_report_days_one_to_seven"], 0)

    def test_negative_signup_timestamp_is_excluded_from_all_cohorts(self):
        self.db.execute("INSERT INTO users VALUES (?,?,?)", (1, -1, "customer"))
        self.user(2, 20)
        self.report("private-valid-report-token", 2, 19)
        m = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(m["excluded_invalid_timestamp_accounts"], 1)
        self.assertEqual(m["signup_accounts"], 1)
        self.assertEqual(m["mature_seven_day_cohort"], 1)
        self.assertEqual(m["saved_report_within_seven_days"], 1)
        self.assertNotIn("private-valid-report-token", founder_activation.panel_html(m))

if __name__ == "__main__":
    unittest.main()
