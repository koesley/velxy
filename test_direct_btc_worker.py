import sqlite3
import unittest
from unittest.mock import patch
import direct_btc_worker as worker
import direct_btc_launch_guard as guard
import direct_btc_orders as orders
import direct_btc_billing as billing

class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE users(id INTEGER PRIMARY KEY)")
        self.db.execute("INSERT INTO users VALUES (1)")
        self.db.commit()
        with patch.object(orders, "receive_address", return_value="bc1q"+"a"*38):
            self.order = orders.allocate_sqlite(self.db,1,"wallet","public")
        billing.quote_order(self.db,self.order["order_id"],1,rate="100000",now=1000)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_monitor_failure_does_not_activate(self):
        with patch("direct_btc_monitor.observe_order",side_effect=OSError("API unavailable")):
            result=worker.scan_once(self.db,now=1200)
        self.assertEqual(result["activated"],0)
        self.assertEqual(self.db.execute("SELECT status FROM direct_btc_orders").fetchone()[0],"pending")

    def test_expired_quote_not_newly_observed(self):
        with patch("direct_btc_monitor.observe_order") as observe:
            result=worker.scan_once(self.db,now=2000)
        observe.assert_not_called()
        self.assertEqual(result["activated"],0)

    def test_expired_quote_initializes_observation_storage(self):
        result = worker.scan_once(self.db, now=2000)
        self.assertEqual(result["activated"], 0)
        tables = self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        self.assertIn(("direct_btc_observations",), tables)

    def test_launch_guard_never_enables_checkout(self):
        self.assertFalse(guard.live_checkout_enabled())
        self.assertFalse(guard.readiness()["ready"])
        self.assertFalse(guard.readiness(persistent_database=True,monitoring_enabled=True,
                                          end_to_end_tested=True)["ready"])

if __name__ == "__main__":
    unittest.main()
