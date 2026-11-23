"""Offline V60/V61 paid-conversion cohort regression coverage."""
import sqlite3
import unittest
import founder_paid_conversion as pc

DAY = 86400
NOW = 100 * DAY


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

    def test_empty_cohort_has_no_fabricated_rate(self):
        self.user(1,1)
        m=pc.paid_cohorts(self.db,NOW)
        self.assertIsNone(m["paid_conversion_pct"])
        self.assertIn("Not available",pc.panel_html(m))


if __name__ == "__main__":
    unittest.main()
