import sqlite3
import unittest
from unittest.mock import patch
import sync_control_v68 as v68
import business_os_v59 as crm

class SyncControlTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.access=patch.object(crm.core,"access",return_value="owner")
        self.audit=patch.object(crm.core,"audit")
        self.access.start();self.audit.start()
    def tearDown(self):
        self.access.stop();self.audit.stop();self.c.close()
    def test_policy_and_due(self):
        self.assertEqual(v68.set_policy(self.c,1,"a","daily",now=100),86500)
        self.assertEqual(v68.overview(self.c,1,"a")[1],("daily",86500))
        self.assertIsNone(v68.overview(self.c,1,"b")[1])
        with self.assertRaises(ValueError):v68.run(self.c,1,"a",now=200,due_only=True)
    def test_run_history_and_dedupe(self):
        with patch.dict("os.environ",{"VELXTRIA_V67_HUBSPOT_TOKEN":"test-token-long-enough"}):
            def fetch(url,token):
                return {"results":[{"properties":{"firstname":"Ada","lastname":"Lovelace","email":"ada@example.com"}}]}
            _,added=v68.run(self.c,1,"a",fetcher=fetch)
            self.assertEqual(added,1)
            _,added=v68.run(self.c,1,"a",fetcher=fetch)
            self.assertEqual(added,0)
        self.assertEqual(len(v68.overview(self.c,1,"a")[2]),2)
        self.assertEqual(len(v68.overview(self.c,1,"b")[2]),0)
    def test_invalid_cadence(self):
        with self.assertRaises(ValueError):v68.set_policy(self.c,1,"a","every_second")
    def test_html_escape(self):
        self.assertNotIn("<script>",v68.render(self.c,1,"a","<script>"))

if __name__=="__main__":unittest.main()
