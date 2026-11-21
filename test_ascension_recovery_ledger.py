"""Regression tests for full-ledger revenue recovery reporting (SQLite only)."""
import sqlite3
import unittest
from unittest.mock import patch
import ascension_recovery


class RecoveryLedgerTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("""CREATE TABLE sales_pipeline_leads(
            id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL, business TEXT NOT NULL)""")
        self.c.execute("""CREATE TABLE ascension_actions(
            id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL, lead_id TEXT NOT NULL,
            kind TEXT NOT NULL, status TEXT NOT NULL, updated_at INTEGER NOT NULL)""")
        self.c.execute("""CREATE TABLE ascension_recovery_outcomes(
            id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL, action_id TEXT NOT NULL,
            outcome TEXT NOT NULL, amount_cents INTEGER NOT NULL,
            evidence TEXT NOT NULL, created_at INTEGER NOT NULL)""")
        self.c.executemany("INSERT INTO sales_pipeline_leads VALUES(?,?,?)",
                           [("lead1",1,"Alpha"),("lead2",2,"Private Beta")])
        self.c.executemany("INSERT INTO ascension_actions VALUES(?,?,?,?,?,?)",
                           [("action1",1,"lead1","stalled_deal","completed",1),
                            ("action2",2,"lead2","stalled_deal","completed",1)])

    def tearDown(self):
        self.c.close()

    def render(self,owner):
        with patch.object(ascension_recovery.sales_pipeline,"setup"), patch.object(
                ascension_recovery.sovereign_ascension,"setup"), patch.object(
                ascension_recovery,"setup"):
            return ascension_recovery.dashboard(self.c,owner,"csrf")

    def test_summary_counts_every_outcome_beyond_history_limit(self):
        self.c.executemany("INSERT INTO ascension_recovery_outcomes VALUES(?,?,?,?,?,?,?)",
                           [(f"item{i}",1,"action1","payment_reported",101,"reported",i)
                            for i in range(125)])
        page=self.render(1)
        self.assertIn("125 recorded outcomes",page)
        self.assertIn("$126.25 user-reported payments",page)
        self.assertIn("Recent outcome history (latest 100)",page)
        self.assertNotIn("Private Beta",page)

    def test_money_is_exact_and_other_owners_are_excluded(self):
        self.c.executemany("INSERT INTO ascension_recovery_outcomes VALUES(?,?,?,?,?,?,?)",
                           [("a",1,"action1","payment_reported",100000001,"reported",1),
                            ("b",1,"action1","payment_reported",1,"reported",2),
                            ("c",2,"action2","payment_reported",90000000,"private",3),
                            ("d",1,"action1","meeting_booked",0,"meeting",4),
                            ("e",1,"action1","responded",0,"reply",5)])
        page=self.render(1)
        self.assertIn("4 recorded outcomes",page)
        self.assertIn("$1,000,000.02 user-reported payments",page)
        self.assertIn("1 meetings booked",page)
        self.assertIn("1 responses recorded",page)
        self.assertNotIn("$900,000.00",page)
        self.assertNotIn("Private Beta",page)


if __name__=="__main__":
    unittest.main()
