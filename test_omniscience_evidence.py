import sqlite3
import time
import unittest
import omniscience_evidence as omnis

class OmniscienceEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
    def tearDown(self):
        self.db.close()
    def test_tenant_isolation_and_history(self):
        eid=omnis.record_evidence(self.db,1,"crm","lead-1","user_reported",{"stage":"proposal"})
        with self.assertRaises(ValueError):
            omnis.recommend(self.db,2,"Review lead","Stalled","Follow up",eid)
        rid=omnis.recommend(self.db,1,"Review lead","Stalled","Follow up",eid)
        with self.assertRaises(ValueError):
            omnis.decide(self.db,2,rid,"accept","Approved")
        omnis.decide(self.db,1,rid,"defer","Awaiting customer response")
        omnis.decide(self.db,1,rid,"accept","Approved for internal review")
        history=omnis.history(self.db,1,rid)
        self.assertEqual([x["choice"] for x in history["decisions"]],["defer","accept"])
        self.assertEqual(history["evidence"]["reliability"],"user_reported")
        with self.assertRaises(ValueError):
            omnis.history(self.db,2,rid)
    def test_unverified_evidence_stays_unverified(self):
        eid=omnis.record_evidence(self.db,1,"manual","payment-1","user_reported",{"amount":500})
        rid=omnis.recommend(self.db,1,"Review payment","Reported","Verify receipt",eid)
        self.assertEqual(omnis.history(self.db,1,rid)["evidence"]["reliability"],"user_reported")
    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            omnis.record_evidence(self.db,1,"crm","x","verified_by_magic",{})
        with self.assertRaises(ValueError):
            omnis.record_evidence(self.db,1,"crm","x","estimate",{"x":float("nan")})
        eid=omnis.record_evidence(self.db,1,"crm","x","estimate",{})
        rid=omnis.recommend(self.db,1,"Review","Stalled","Investigate",eid)
        with self.assertRaises(ValueError):
            omnis.decide(self.db,1,rid,"execute","No permission")
    def test_expiry(self):
        eid=omnis.record_evidence(self.db,1,"crm","x","inference",{})
        with self.assertRaises(ValueError):
            omnis.recommend(self.db,1,"Review","Stalled","Investigate",eid,int(time.time())-1)

if __name__=="__main__":
    unittest.main()
