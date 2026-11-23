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

    def test_weekly_first_day_and_delayed_stages_reconcile(self):
        for uid in range(1, 6):
            self.user(uid, 21)
        self.report("instant", 1, 21)
        self.report("day-one-boundary", 2, 20)
        self.report("six-days", 3, 15)
        self.report("late", 4, 13)
        m = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(len(m["weekly_activation_stages"]), 1)
        week, total, fast, delayed = m["weekly_activation_stages"][0]
        self.assertEqual((total, fast, delayed), (5, 1, 2))
        self.assertEqual(m["weekly_cohorts"][0], (week, 5, fast + delayed))
        page = founder_activation.panel_html(m)
        self.assertIn("Saved within 24h", page)
        self.assertIn("First saved 24h", page)
        self.assertNotIn("instant", page)

    def test_weekly_stages_exclude_immature_admin_and_failed(self):
        self.user(1, 21)
        self.user(2, 2)
        self.user(3, 21, "admin")
        self.report("failed", 1, 20, "failed")
        self.report("young", 2, 1)
        self.report("admin", 3, 20)
        m = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(sum(row[1] for row in m["weekly_activation_stages"]), 1)
        self.assertEqual(sum(row[2] + row[3] for row in m["weekly_activation_stages"]), 0)

    def test_weekly_stages_keep_existing_cohort_contract_and_eight_week_cap(self):
        for uid in range(1, 15):
            self.user(uid, 8 + uid * 7)
        m = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(len(m["weekly_activation_stages"]), 8)
        self.assertEqual(tuple(row[:2] for row in m["weekly_activation_stages"]),
                         tuple(row[:2] for row in m["weekly_cohorts"]))
        self.assertTrue(all(len(row) == 3 for row in m["weekly_cohorts"]))


    def test_repeat_usage_counts_only_further_ready_reports_in_days_seven_to_thirty(self):
        self.user(1, 45)
        self.user(2, 45)
        self.user(3, 45)
        self.report("first-a", 1, 44)
        self.report("repeat-a", 1, 35)
        self.report("duplicate-repeat-a", 1, 34)
        self.report("first-b", 2, 44)
        self.report("failed-repeat-b", 2, 35, "failed")
        self.report("late-first-c", 3, 35)
        m = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(m["first_week_activated_with_30_day_observation"], 2)
        self.assertEqual(m["first_week_activated_with_later_ready_report"], 1)
        self.assertEqual(m["later_report_usage_rate_pct"], 50.0)
        page = founder_activation.panel_html(m)
        self.assertIn("Repeat-usage diagnostic", page)
        self.assertNotIn("repeat-a", page)

    def test_repeat_usage_excludes_immature_admin_and_out_of_window(self):
        self.user(1, 29)
        self.user(2, 40, "admin")
        self.user(3, 40)
        self.user(4, 40)
        self.report("young-first", 1, 28)
        self.report("young-repeat", 1, 20)
        self.report("admin-first", 2, 39)
        self.report("admin-repeat", 2, 30)
        self.report("first-three", 3, 39)
        self.report("day-thirty", 3, 10)
        self.report("first-four", 4, 39)
        self.report("day-seven-boundary", 4, 33)
        m = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(m["first_week_activated_with_30_day_observation"], 2)
        self.assertEqual(m["first_week_activated_with_later_ready_report"], 1)
        self.assertEqual(m["later_report_usage_rate_pct"], 50.0)

    def test_repeat_usage_without_eligible_cohort_is_undefined(self):
        self.user(1, 12)
        self.report("first", 1, 11)
        m = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(m["first_week_activated_with_30_day_observation"], 0)
        self.assertIsNone(m["later_report_usage_rate_pct"])
        self.assertIn("no eligible 30-day cohort", founder_activation.panel_html(m))


    def test_repeat_usage_speed_segments_reconcile_and_exclude_immature(self):
        self.user(1, 45)
        self.user(2, 45)
        self.user(3, 45)
        self.user(4, 45)
        self.user(5, 15)
        self.report("fast-first", 1, 45)
        self.report("fast-repeat", 1, 35)
        self.report("fast-no-repeat", 2, 45)
        self.report("delayed-first", 3, 43)
        self.report("delayed-repeat", 3, 35)
        self.report("delayed-no-repeat", 4, 43)
        self.report("young-first", 5, 15)
        self.report("young-repeat", 5, 7)
        m = founder_activation.report_activation(self.db, NOW)
        speed = m["repeat_usage_by_first_save_speed"]
        self.assertEqual(speed["within_24h"], {"eligible": 2, "repeat_users": 1, "rate_pct": 50.0})
        self.assertEqual(speed["24h_to_7d"], {"eligible": 2, "repeat_users": 1, "rate_pct": 50.0})
        self.assertEqual(sum(v["eligible"] for v in speed.values()),
                         m["first_week_activated_with_30_day_observation"])
        self.assertEqual(sum(v["repeat_users"] for v in speed.values()),
                         m["first_week_activated_with_later_ready_report"])
        page = founder_activation.panel_html(m)
        self.assertIn("30-day repeat use by first-save timing", page)
        self.assertNotIn("fast-repeat", page)

    def test_repeat_usage_speed_boundaries_and_empty_segment(self):
        self.user(1, 35)
        self.user(2, 35)
        self.report("exact-day-one", 1, 34)
        self.report("repeat-day-seven", 1, 28)
        self.report("exact-day-seven", 2, 28)
        self.report("later", 2, 25)
        m = founder_activation.report_activation(self.db, NOW)
        speed = m["repeat_usage_by_first_save_speed"]
        self.assertEqual(speed["within_24h"], {"eligible": 0, "repeat_users": 0, "rate_pct": None})
        self.assertEqual(speed["24h_to_7d"], {"eligible": 1, "repeat_users": 1, "rate_pct": 100.0})
        self.assertEqual(m["first_week_activated_with_30_day_observation"], 1)
        self.assertIn("Not available", founder_activation.panel_html(m))

    def test_repeat_usage_speed_excludes_admin_failed_and_duplicates(self):
        self.user(1, 50)
        self.user(2, 50, "admin")
        self.report("first", 1, 50)
        self.report("failed", 1, 40, "failed")
        self.report("admin-first", 2, 50)
        self.report("admin-repeat", 2, 40)
        m = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(m["repeat_usage_by_first_save_speed"]["within_24h"]["eligible"], 1)
        self.assertEqual(m["repeat_usage_by_first_save_speed"]["within_24h"]["repeat_users"], 0)
        self.assertEqual(m["first_week_activated_with_later_ready_report"], 0)


    def test_weekly_repeat_usage_reconciles_and_excludes_immature(self):
        self.user(1, 56)
        self.user(2, 56)
        self.user(3, 42)
        self.user(4, 20)
        self.report("one-first", 1, 55)
        self.report("one-repeat", 1, 46)
        self.report("two-first", 2, 55)
        self.report("three-first", 3, 41)
        self.report("three-repeat", 3, 33)
        self.report("young-first", 4, 19)
        self.report("young-repeat", 4, 12)
        result = founder_activation.report_activation(self.db, NOW)
        weeks = result["weekly_mature_repeat_usage"]
        self.assertEqual(sum(row[1] for row in weeks), 3)
        self.assertEqual(sum(row[2] for row in weeks), 2)
        self.assertEqual(result["first_week_activated_with_30_day_observation"], 3)
        self.assertEqual(result["first_week_activated_with_later_ready_report"], 2)
        page = founder_activation.panel_html(result)
        self.assertIn("Repeat usage by mature signup week", page)
        self.assertNotIn("one-repeat", page)

    def test_weekly_repeat_usage_excludes_admin_failed_and_late_first_saves(self):
        self.user(1, 45)
        self.user(2, 45, "admin")
        self.user(3, 45)
        self.user(4, 45)
        self.report("valid-first", 1, 44)
        self.report("failed-repeat", 1, 35, "failed")
        self.report("admin-first", 2, 44)
        self.report("admin-repeat", 2, 35)
        self.report("late-first", 3, 35)
        self.report("late-repeat", 3, 30)
        self.report("first-four", 4, 44)
        self.report("repeat-at-thirty", 4, 15)
        result = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(sum(row[1] for row in result["weekly_mature_repeat_usage"]), 2)
        self.assertEqual(sum(row[2] for row in result["weekly_mature_repeat_usage"]), 0)

    def test_weekly_repeat_usage_caps_eight_weeks_and_handles_empty(self):
        self.assertEqual(founder_activation.report_activation(self.db, NOW)["weekly_mature_repeat_usage"], ())
        self.assertIn("No mature 30-day signup weeks",
                      founder_activation.panel_html(founder_activation.report_activation(self.db, NOW)))
        for uid in range(1, 13):
            self.user(uid, 35 + uid * 7)
            self.report("first-" + str(uid), uid, 34 + uid * 7)
        result = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(len(result["weekly_mature_repeat_usage"]), 8)
        self.assertEqual(list(result["weekly_mature_repeat_usage"]),
                         sorted(result["weekly_mature_repeat_usage"], reverse=True))
        self.assertTrue(all(eligible > 0 and repeated == 0
                            for _, eligible, repeated in result["weekly_mature_repeat_usage"]))

    def test_24_hour_cohort_includes_recent_mature_signups_without_polluting_seven_day(self):
        self.user(1, 2)
        self.user(2, 2)
        self.user(3, 0)
        self.user(4, 10)
        self.report("recent-fast", 1, 2)
        self.report("recent-late", 2, 1)
        self.report("young-fast", 3, 0)
        self.report("older-fast", 4, 10)
        m = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(m["mature_24_hour_cohort"], 3)
        self.assertEqual(m["saved_report_within_24h_observed"], 2)
        self.assertEqual(m["observed_24h_activation_rate_pct"], 66.67)
        self.assertEqual(m["mature_seven_day_cohort"], 1)
        self.assertEqual(sum(r[1] for r in m["weekly_24h_activation"]), 3)
        self.assertEqual(sum(r[2] for r in m["weekly_24h_activation"]), 2)
        markup = founder_activation.panel_html(m)
        self.assertIn("24-hour activation by signup week", markup)
        self.assertNotIn("recent-fast", markup)

    def test_24_hour_cohort_excludes_admin_failed_and_future_reports(self):
        self.user(1, 2)
        self.user(2, 2, "admin")
        self.user(3, 1)
        self.report("failed", 1, 2, "failed")
        self.report("admin", 2, 2)
        self.report("future", 3, -1)
        m = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(m["mature_24_hour_cohort"], 2)
        self.assertEqual(m["saved_report_within_24h_observed"], 0)
        self.assertEqual(m["observed_24h_activation_rate_pct"], 0.0)

    def test_24_hour_empty_and_weekly_cap(self):
        self.user(1, 0)
        m = founder_activation.report_activation(self.db, NOW)
        self.assertIsNone(m["observed_24h_activation_rate_pct"])
        self.assertIn("No signups with a complete 24-hour observation window", founder_activation.panel_html(m))
        for uid in range(2, 17):
            self.user(uid, uid * 7 + 2)
        m = founder_activation.report_activation(self.db, NOW)
        self.assertEqual(len(m["weekly_24h_activation"]), 8)
        self.assertEqual(m["mature_24_hour_cohort"], 15)

if __name__ == "__main__":
    unittest.main()
