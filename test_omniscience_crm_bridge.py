import sqlite3
import time
import unittest
import sales_pipeline
import omniscience_crm_bridge as bridge
import omniscience_evidence as ledger

class CRMBridgeTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
    def tearDown(self):
        self.c.close()
    def test_empty_account(self):
        self.assertEqual(bridge.candidates(self.c,1),[])
    def test_scoped_and_provenance(self):
        lead=sales_pipeline.save(self.c,1,{"business":"Example Studio","stage":"proposal","value":"1200"})
        self.c.execute("UPDATE sales_pipeline_leads SET updated_at=? WHERE id=?",
                       (int(time.time())-16*86400,lead))
        items=bridge.candidates(self.c,1)
        self.assertTrue(items)
        self.assertEqual(bridge.candidates(self.c,2),[])
        self.assertEqual(items[0]["reliability"],"inference")
        rid=bridge.save_for_review(self.c,1,items[0])
        self.assertEqual(ledger.history(self.c,1,rid)["evidence"]["reliability"],"inference")
        self.assertEqual(bridge.save_for_review(self.c,1,items[0]),rid)
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM omnis_recommendations").fetchone()[0],1)
        with self.assertRaises(ValueError):
            bridge.save_for_review(self.c,2,items[0])
    def test_reject_forged_or_stale_candidate(self):
        lead=sales_pipeline.save(self.c,1,{"business":"Example Studio","stage":"proposal"})
        self.c.execute("UPDATE sales_pipeline_leads SET updated_at=? WHERE id=?",
                       (int(time.time())-16*86400,lead))
        item=bridge.candidates(self.c,1)[0]
        forged=dict(item,reliability="external_verified")
        with self.assertRaises(ValueError):
            bridge.save_for_review(self.c,1,forged)
        self.c.execute("UPDATE sales_pipeline_leads SET stage='lost',updated_at=? WHERE id=?",
                       (int(time.time()),lead))
        with self.assertRaises(ValueError):
            bridge.save_for_review(self.c,1,item)

if __name__=="__main__":
    unittest.main()
