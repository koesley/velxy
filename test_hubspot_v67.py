import sqlite3
import unittest
from unittest.mock import patch
import hubspot_v67 as v67
import business_os_v59 as crm

class HubspotTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.access=patch.object(crm.core,"access",return_value="owner")
        self.audit=patch.object(crm.core,"audit")
        self.access.start();self.audit.start()
    def tearDown(self):
        self.access.stop();self.audit.stop();self.c.close()
    def test_sync_and_workspace_isolation(self):
        def fetch(url,token):
            return {"results":[{"properties":{"firstname":"Ada","lastname":"Lovelace","email":"ada@example.com"}}]}
        with patch.dict("os.environ",{"VELXTRIA_V67_HUBSPOT_TOKEN":"test-private-token-long"}):
            self.assertEqual(v67.sync(self.c,1,"a",fetcher=fetch),1)
            self.assertEqual(v67.sync(self.c,1,"a",fetcher=fetch),0)
        self.assertEqual(len(crm.overview(self.c,1,"a")["leads"]),1)
        self.assertEqual(len(crm.overview(self.c,1,"b")["leads"]),0)
    def test_missing_token_rejected(self):
        with patch.dict("os.environ",{"VELXTRIA_V67_HUBSPOT_TOKEN":""}):
            with self.assertRaises(ValueError):v67.fetch_contacts()
    def test_malformed_response_rejected(self):
        with patch.dict("os.environ",{"VELXTRIA_V67_HUBSPOT_TOKEN":"test-private-token-long"}):
            with self.assertRaises(ValueError):v67.fetch_contacts(fetcher=lambda *args:{"results":{}})
    def test_token_not_rendered(self):
        with patch.dict("os.environ",{"VELXTRIA_V67_HUBSPOT_TOKEN":"super-private-test-token"}):
            self.assertNotIn("super-private-test-token",v67.render(self.c,1,"a","csrf"))

if __name__=="__main__":unittest.main()
