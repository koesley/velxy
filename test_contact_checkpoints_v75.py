import os
import tempfile
import time
import unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
import persistent
import hubspot_oauth_v70 as oauth
import contact_checkpoints_v75 as v75
import business_os_v59 as crm

class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=self.tmp.name+"/db.sqlite"
        self.env=patch.dict(os.environ,{"VELXTRIA_V70_HUBSPOT_CLIENT_ID":"client","VELXTRIA_V70_HUBSPOT_CLIENT_SECRET":"secret","VELXTRIA_V70_HUBSPOT_REDIRECT_URI":"https://example.com/hubspot-oauth-v70/callback","VELXTRIA_V70_ENCRYPTION_KEY":Fernet.generate_key().decode()})
        self.env.start()
        self.access=patch.object(crm.core,"access",return_value="owner")
        self.audit=patch.object(crm.core,"audit")
        self.access.start();self.audit.start()
        from urllib.parse import urlsplit,parse_qs
        with self.connect() as c:
            now=int(time.time())
            state=parse_qs(urlsplit(oauth.begin(c,1,"a",now=now)).query)["state"][0]
            oauth.finish(c,1,state,"code",requester=lambda *args:{"access_token":"token-a","refresh_token":"refresh-a","expires_in":7200},now=now)
    def connect(self):return persistent.connect(self.path)
    def tearDown(self):self.access.stop();self.audit.stop();self.env.stop();self.tmp.cleanup()
    def test_resume_after_page_failure(self):
        seen=[]
        def fetch(url,token):
            seen.append(url)
            if len(seen)==1:return {"results":[{"properties":{"email":"one@example.com"}}],"paging":{"next":{"after":"cursor2"}}}
            if len(seen)==2:raise ValueError("temporary")
            return {"results":[{"properties":{"email":"two@example.com"}}]}
        with self.assertRaises(ValueError):v75.import_batch(self.connect,1,"a",fetcher=fetch)
        with self.connect() as c:
            self.assertTrue(v75.status(c,1,"a")["in_progress"])
            self.assertEqual(v75.status(c,1,"a")["contacts_added"],1)
        self.assertEqual(v75.import_batch(self.connect,1,"a",fetcher=fetch),1)
        self.assertIn("after=cursor2",seen[-1])
        with self.connect() as c:
            state=v75.status(c,1,"a")
            self.assertEqual(state["cycles"],1)
            self.assertFalse(state["in_progress"])
            self.assertEqual(len(crm.overview(c,1,"a")["leads"]),2)
    def test_workspace_scope(self):
        with self.connect() as c:
            self.assertEqual(v75.status(c,1,"b")["contacts_added"],0)
    def test_cursor_loop_rejected(self):
        def fetch(url,token):return {"results":[],"paging":{"next":{"after":"same"}}}
        with self.assertRaises(ValueError):v75.import_batch(self.connect,1,"a",fetcher=fetch)
        with self.connect() as c:self.assertEqual(v75.status(c,1,"a")["pages_done"],1)

if __name__=="__main__":unittest.main()
