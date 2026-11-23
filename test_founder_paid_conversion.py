"""Offline V60/V61 paid-conversion cohort regression coverage."""
import sqlite3
import unittest
import founder_paid_conversion as pc

DAY = 86400
NOW = 200 * DAY


class PaidConversionTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, created INTEGER, role TEXT)")
        self.db.execute("CREATE TABLE reports(id TEXT, user_id INTEGER, created INTEGER, status TEXT)")
        self.db.execute("""CREATE TABLE btcpay_orders(
            order_id TEXT PRIMARY KEY,user_id INTEGER,network TEXT,status TEXT,
            invoice_id TEXT,settled_at INTEGER)""")

    def tearDown(self):
        self.db.close()

    def user(self, uid, age, role="customer"):
        self.db.execute("INSERT INTO users VALUES(?,?,?)", (uid, NOW-age*DAY, role))

    def report(self, uid, days_ago, status="ready"):
        self.db.execute("INSERT INTO reports VALUES(?,?,?,?)",
                        ("private-report-" + str(uid), uid, NOW-days_ago*DAY, status))

    def order(self, uid, days_ago, status="settled", network="mainnet", invoice="verified"):
        self.db.execute("INSERT INTO btcpay_orders VALUES(?,?,?,?,?,?)",
                        ("private-order-" + str(uid), uid, network, status,
                         invoice, NOW-days_ago*DAY))

    def test_mature_first_value_and_verified_payment_intersection(self):
        self.user(1, 45)
        self.user(2, 45)
        self.user(3, 45)
        self.report(1, 44)
        self.order(1, 30)
        self.report(2, 44)
        self.order(3, 30)
        m = pc.paid_cohorts(self.db, NOW)
        self.assertEqual((m["mature_30d_signups"],m["first_week_activated"],
                          m["settled_within_30d"],m["activated_and_settled"]), (3,2,2,1))
        self.assertEqual(m["paid_conversion_pct"],66.67)
        self.assertEqual(m["activated_paid_conversion_pct"],50.0)
        self.assertNotIn("private-",pc.panel_html(m))

    def test_excludes_immature_admin_pending_testnet_and_failed_reports(self):
        for uid, age, role in [(1,29,"customer"),(2,40,"admin"),(3,40,"customer"),
                                (4,40,"customer"),(5,40,"customer")]:
            self.user(uid,age,role)
        self.order(1,20)
        self.order(2,30)
        self.order(3,30,"pending")
        self.order(4,30,"settled","testnet")
        self.order(5,30,"settled","mainnet",None)
        self.report(3,39,"failed")
        m=pc.paid_cohorts(self.db,NOW)
        self.assertEqual(m["mature_30d_signups"],3)
        self.assertEqual(m["settled_within_30d"],0)
        self.assertIsNone(m["activated_paid_conversion_pct"])

    def test_exact_day_thirty_excluded_and_one_day_earlier_included(self):
        self.user(1,40)
        self.user(2,40)
        self.order(1,10)
        self.order(2,11)
        m=pc.paid_cohorts(self.db,NOW)
        self.assertEqual(m["settled_within_30d"],1)

    def test_ignores_pre_signup_and_future_settlement(self):
        self.user(1,40)
        self.user(2,40)
        self.order(1,41)
        self.order(2,-1)
        self.assertEqual(pc.paid_cohorts(self.db,NOW)["settled_within_30d"],0)

    def test_missing_table_is_explicitly_unavailable(self):
        self.db.execute("DROP TABLE btcpay_orders")
        m=pc.paid_cohorts(self.db,NOW)
        self.assertFalse(m["available"])
        self.assertIn("Unavailable",pc.panel_html(m))

    def test_read_only_and_weekly_bounded(self):
        for uid in range(1,14):
            self.user(uid,35+uid*7)
        self.db.execute("PRAGMA query_only=ON")
        m=pc.paid_cohorts(self.db,NOW)
        self.assertEqual(m["mature_30d_signups"],13)
        self.assertEqual(len(m["weekly"]),8)
        self.assertIsNone(m["activated_paid_conversion_pct"])

    def test_negative_signup_timestamp_is_excluded(self):
        self.db.execute("INSERT INTO users VALUES(?,?,?)", (91, -DAY, "customer"))
        self.user(1, 40)
        m = pc.paid_cohorts(self.db, NOW)
        self.assertEqual(m["mature_30d_signups"], 1)

    def test_nonactivated_paid_segment_and_rates_reconcile(self):
        for uid in range(1, 5):
            self.user(uid, 45)
        self.report(1, 44)
        self.report(2, 44)
        self.order(1, 35)
        self.order(3, 35)
        m = pc.paid_cohorts(self.db, NOW)
        self.assertEqual(m["nonactivated_signups"], 2)
        self.assertEqual(m["nonactivated_settled"], 1)
        self.assertEqual(m["nonactivated_paid_conversion_pct"], 50.0)
        self.assertEqual(m["settled_within_30d"],
                         m["activated_and_settled"] + m["nonactivated_settled"])
        self.assertEqual(m["mature_30d_signups"],
                         m["first_week_activated"] + m["nonactivated_signups"])

    def test_no_nonactivated_denominator_does_not_invent_rate(self):
        self.user(1, 45)
        self.report(1, 44)
        m = pc.paid_cohorts(self.db, NOW)
        self.assertIsNone(m["nonactivated_paid_conversion_pct"])
        self.assertIn("Not available", pc.panel_html(m))

    def test_weekly_funnel_rendered_aggregate_only(self):
        self.user(1, 45)
        self.report(1, 44)
        self.order(1, 35)
        m = pc.paid_cohorts(self.db, NOW)
        panel = pc.panel_html(m)
        self.assertIn("Recent mature signup weeks", panel)
        self.assertIn("Signup week (UTC)", panel)
        self.assertIn("does not establish causation", panel)
        self.assertNotIn("private-order", panel)
        self.assertNotIn("private-report", panel)
        self.assertIn("<td>1</td><td>1</td><td>1</td><td>1</td>", panel)

    def test_time_to_value_and_settlement_medians_and_boundaries(self):
        for uid in range(1, 5):
            self.user(uid, 50)
        self.report(1, 50)  # first report at signup, zero days
        self.report(2, 49)  # exactly one day, not first-day
        self.report(3, 44)  # six days, within first week
        self.report(4, 43)  # exactly seven days, not activated
        self.order(1, 50)
        self.order(2, 43)  # exactly seven days, not first-week settlement
        self.order(3, 21)  # 29 days
        m = pc.paid_cohorts(self.db, NOW)
        self.assertEqual(m["first_day_activated"], 1)
        self.assertEqual(m["first_week_activated"], 3)
        self.assertEqual(m["median_days_to_first_value"], 1.0)
        self.assertEqual(m["first_week_settled"], 1)
        self.assertEqual(m["median_days_to_settlement"], 7.0)
        panel = pc.panel_html(m)
        self.assertIn("Median days to first ready report", panel)
        self.assertIn("Median days to settlement", panel)

    def test_latency_metrics_exclude_unqualified_and_missing_events(self):
        self.user(1, 40)
        self.user(2, 40)
        self.report(1, 39, "failed")
        self.order(1, 39, "pending")
        self.order(2, 39, "settled", "testnet")
        m = pc.paid_cohorts(self.db, NOW)
        self.assertEqual(m["first_day_activated"], 0)
        self.assertEqual(m["first_week_settled"], 0)
        self.assertIsNone(m["median_days_to_first_value"])
        self.assertIsNone(m["median_days_to_settlement"])
        self.assertIn("Not available", pc.panel_html(m))

    def test_empty_cohort_has_no_fabricated_rate(self):
        self.user(1,1)
        m=pc.paid_cohorts(self.db,NOW)
        self.assertIsNone(m["paid_conversion_pct"])
        self.assertIn("Not available",pc.panel_html(m))


    def test_verified_mainnet_pro_snapshot_active_expired_and_untrusted(self):
        import subscriptions
        subscriptions.setup(self.db)
        for uid in range(1, 8):
            self.user(uid, 40, "admin" if uid == 7 else "customer")
        def sub(uid, source, start, end, status="active", verified=1, product=None):
            self.db.execute(
                "INSERT INTO subscriptions(user_id,product_key,pricing_plan,status,"
                "period_start,period_end,verified_at,verification_source,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (uid, subscriptions.PRODUCT_KEY if product is None else product,
                 subscriptions.PRICING_PLAN, status, start, end, verified, source, NOW))
        good = "btcpay_mainnet_verified"
        sub(1, good, NOW-10, NOW+10)
        sub(2, good, NOW-40, NOW-1, "cancel_at_period_end")
        sub(3, "btcpay_testnet_verified", NOW-10, NOW+10)
        sub(4, "referral", NOW-10, NOW+10)
        sub(5, good, NOW-10, NOW+10, verified=0)
        sub(6, good, NOW-10, NOW+10, product="other")
        sub(7, good, NOW-10, NOW+10)
        metrics = pc.paid_cohorts(self.db, NOW)
        self.assertEqual(metrics["verified_pro_snapshot"],
                         {"available": True, "active": 1, "expired": 1})
        rendered = pc.panel_html(metrics)
        self.assertIn("active 1; expired 1", rendered)
        self.assertIn("not proof of churn", rendered)
        self.assertNotIn("private-", rendered)

    def test_missing_subscription_schema_is_not_zero_active(self):
        self.user(1, 40)
        metrics = pc.paid_cohorts(self.db, NOW)
        self.assertEqual(metrics["verified_pro_snapshot"], {"available": False})
        self.assertIn("unavailable (subscription records not initialized)",
                      pc.panel_html(metrics))

    def test_verified_pro_snapshot_is_read_only_and_respects_period_boundary(self):
        import subscriptions
        subscriptions.setup(self.db)
        self.user(1, 40)
        self.db.execute(
            "INSERT INTO subscriptions(user_id,product_key,pricing_plan,status,"
            "period_start,period_end,verified_at,verification_source,updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (1, subscriptions.PRODUCT_KEY, subscriptions.PRICING_PLAN,
             "active", NOW-10, NOW, NOW-9, "btcpay_mainnet_verified", NOW))
        self.db.execute("PRAGMA query_only=ON")
        metrics = pc.paid_cohorts(self.db, NOW)
        self.assertEqual(metrics["verified_pro_snapshot"]["active"], 0)
        self.assertEqual(metrics["verified_pro_snapshot"]["expired"], 1)


if __name__ == "__main__":
    unittest.main()
