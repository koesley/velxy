import os
import sqlite3
import unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
import hubspot_oauth_v70 as v70
import business_os_v59 as crm

class OAuthTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.env=patch.dict(os.environ,{
            "VELXTRIA_V70_HUBSPOT_CLIENT_ID":"client123",
            "VELXTRIA_V70_HUBSPOT_CLIENT_SECRET":"secret123",
            "VELXTRIA_V70_HUBSPOT_REDIRECT_URI":"https://example.com/hubspot-oauth-v70/callback",
            "VELXTRIA_V70_ENCRYPTION_KEY":Fernet.generate_key().decode()})
        self.env.start()
        self.access=patch.object(crm.core,"access",return_value="owner")
        self.audit=patch.object(crm.core,"audit")
        self.access.start();self.audit.start()
    def tearDown(self):
        self.access.stop();self.audit.stop();self.env.stop();self.c.close()
    def connect(self,wid="a"):
        url=v70.begin(self.c,1,wid,now=100)
        from urllib.parse import parse_qs,urlsplit
        state=parse_qs(urlsplit(url).query)["state"][0]
        token=lambda *args:{"access_token":"private-access","refresh_token":"private-refresh","expires_in":3600}
        self.assertEqual(v70.finish(self.c,1,state,"authorization-code",requester=token,now=110),wid)
        return state
    def test_connect_encrypted_and_one_time(self):
        state=self.connect()
        row=self.c.execute("SELECT access_token,refresh_token FROM v70_hubspot_connections WHERE workspace_id='a'").fetchone()
        self.assertNotIn("private-access",str(row))
        with self.assertRaises(ValueError):
            v70.finish(self.c,1,state,"another-code",requester=lambda *args:{},now=111)
        self.assertEqual(v70.access_token(self.c,1,"a",now=120),"private-access")
        with self.assertRaises(ValueError):v70.access_token(self.c,1,"b",now=120)
    def test_refresh_rotates_credentials(self):
        self.connect()
        def refresh(url,params):
            self.assertEqual(params["grant_type"],"refresh_token")
            return {"access_token":"new-access","refresh_token":"new-refresh","expires_in":7200}
        self.assertEqual(v70.access_token(self.c,1,"a",now=4000,requester=refresh),"new-access")
        self.assertEqual(v70.access_token(self.c,1,"a",now=4100),"new-access")
    def test_import_is_scoped_and_read_only(self):
        self.connect()
        def fetch(url,token):
            self.assertEqual(token,"private-access")
            return {"results":[{"properties":{"firstname":"Ada","lastname":"Lovelace","email":"ada@example.com"}}]}
        self.assertEqual(v70.import_contacts(self.c,1,"a",fetcher=fetch),1)
        self.assertEqual(v70.import_contacts(self.c,1,"a",fetcher=fetch),0)
        self.assertEqual(len(crm.overview(self.c,1,"b")["leads"]),0)
        v70.disconnect(self.c,1,"a")
        with self.assertRaises(ValueError):v70.access_token(self.c,1,"a")
    def test_invalid_state_and_expiry(self):
        url=v70.begin(self.c,1,"a",now=100)
        from urllib.parse import parse_qs,urlsplit
        state=parse_qs(urlsplit(url).query)["state"][0]
        with self.assertRaises(ValueError):v70.finish(self.c,1,"wrong","code",now=101)
        with self.assertRaises(ValueError):v70.finish(self.c,1,state,"code",now=701)
    def test_no_credentials_in_html(self):
        self.connect()
        page=v70.render(self.c,1,"a","csrf")
        self.assertNotIn("private-access",page)
        self.assertNotIn("private-refresh",page)

if __name__=="__main__":unittest.main()
