import os
import sqlite3
import unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
import integration_health_v72 as v72
import hubspot_oauth_v70 as oauth
import business_os_v59 as crm

class IntegrationHealthTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.env=patch.dict(os.environ,{"VELXTRIA_V70_HUBSPOT_CLIENT_ID":"client","VELXTRIA_V70_HUBSPOT_CLIENT_SECRET":"secret","VELXTRIA_V70_HUBSPOT_REDIRECT_URI":"https://example.com/hubspot-oauth-v70/callback","VELXTRIA_V70_ENCRYPTION_KEY":Fernet.generate_key().decode()})
        self.env.start()
        self.access=patch.object(crm.core,"access",return_value="owner")
        self.audit=patch.object(crm.core,"audit")
        self.access.start();self.audit.start()
        from urllib.parse import urlsplit,parse_qs
        url=oauth.begin(self.c,1,"a",now=100)
        state=parse_qs(urlsplit(url).query)["state"][0]
        oauth.finish(self.c,1,state,"code",requester=lambda *args:{"access_token":"private-a","refresh_token":"refresh-a","expires_in":999999999},now=110)
    def tearDown(self):
        self.access.stop();self.audit.stop();self.env.stop();self.c.close()
    def test_multi_page_import_dedupe(self):
        calls=[]
        def fetch(url,token):
            calls.append(url)
            self.assertEqual(token,"private-a")
            if len(calls)==1:return {"results":[{"properties":{"firstname":"Ada","email":"ada@example.com"}}],"paging":{"next":{"after":"cursor-2"}}}
            return {"results":[{"properties":{"firstname":"Ada","email":"ada@example.com"}},{"properties":{"firstname":"Bob","email":"bob@example.com"}}]}
        self.assertEqual(v72.import_all(self.c,1,"a",fetcher=fetch),2)
        self.assertEqual(len(calls),2)
        self.assertIn("after=cursor-2",calls[1])
        self.assertEqual(len(crm.overview(self.c,1,"b")["leads"]),0)
    def test_cursor_loop_rejected(self):
        def fetch(url,token):return {"results":[],"paging":{"next":{"after":"repeat"}}}
        with self.assertRaises(ValueError):v72.import_all(self.c,1,"a",fetcher=fetch)
    def test_health_is_scoped(self):
        self.assertTrue(v72.health(self.c,1,"a")["connected"])
        self.assertFalse(v72.health(self.c,1,"b")["connected"])
        self.assertNotIn("private-a",v72.render(self.c,1,"a"))

if __name__=="__main__":unittest.main()
