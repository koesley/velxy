import sqlite3
import time
import unittest
import omniscience_evidence as ledger
import omniscience_operations as operations

class DecisionOperationsTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
    def tearDown(self):
        self.c.close()
    def test_first_visit_and_invalid_owner(self):
        self.assertEqual(operations.summary(self.c,1)["counts"]["pending"],0)
        for owner in (0,True,"1"):
            with self.assertRaises(ValueError):
                operations.summary(self.c,owner)
    def test_latest_decision_and_tenant_isolation(self):
        eid=ledger.record_evidence(self.c,1,"crm","lead","inference",{"value":100})
        rid=ledger.recommend(self.c,1,"Review","stalled","check",eid)
        self.assertEqual(operations.summary(self.c,1)["counts"]["pending"],1)
        ledger.decide(self.c,1,rid,"defer","waiting")
        ledger.decide(self.c,1,rid,"accept","manual review")
        report=operations.summary(self.c,1)
        self.assertEqual(report["counts"]["accepted"],1)
        self.assertEqual(report["counts"]["deferred"],0)
        self.assertEqual(report["records"][0]["last_decision"][0],"accept")
        self.assertEqual(operations.summary(self.c,2)["records"],[])
    def test_stale_and_escape(self):
        eid=ledger.record_evidence(self.c,1,"crm","<img>","inference",{},
                                   observed_at=int(time.time())-35*86400)
        ledger.recommend(self.c,1,"<script>","old","review",eid)
        report=operations.summary(self.c,1)
        self.assertEqual(report["counts"]["stale_evidence"],1)
        page=operations.dashboard(self.c,1)
        self.assertIn("&lt;script&gt;",page)
        self.assertNotIn("<script>",page)

if __name__=="__main__":
    unittest.main()
