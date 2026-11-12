import os
import tempfile
import time
import unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
import persistent
import oauth_scheduler_v71 as worker
import hubspot_oauth_v70 as oauth
import sync_control_v68 as sync
import business_os_v59 as crm

class OAuthSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=self.tmp.name+"/db.sqlite"
        self.env=patch.dict(os.environ,{
            "VELXTRIA_V70_HUBSPOT_CLIENT_ID":"client123",
            "VELXTRIA_V70_HUBSPOT_CLIENT_SECRET":"secret123",
            "VELXTRIA_V70_HUBSPOT_REDIRECT_URI":"https://example.com/hubspot-oauth-v70/callback",
            "VELXTRIA_V70_ENCRYPTION_KEY":Fernet.generate_key().decode(),
            "VELXTRIA_V67_HUBSPOT_TOKEN":""})
        self.env.start()
        self.access=patch.object(crm.core,"access",return_value="owner")
        self.audit=patch.object(crm.core,"audit")
        self.access.start();self.audit.start()
        self.now=int(time.time())
    def tearDown(self):
        self.access.stop();self.audit.stop();self.env.stop();self.tmp.cleanup()
    def connect(self):
        return persistent.connect(self.path)
    def provision(self,wid):
        from urllib.parse import urlsplit,parse_qs
        with self.connect() as c:
            url=oauth.begin(c,1,wid,now=self.now)
            state=parse_qs(urlsplit(url).query)["state"][0]
            oauth.finish(c,1,state,"code",requester=lambda *args:{"access_token":"token-"+wid,"refresh_token":"refresh-"+wid,"expires_in":3600},now=self.now+1)
            sync.set_policy(c,1,wid,"daily",now=self.now-86400)
    def test_multiple_workspaces_and_dedupe(self):
        self.provision("a");self.provision("b")
        def fetch(url,token):
            return {"results":[{"properties":{"firstname":token,"email":token+"@example.com"}}]}
        results=worker.tick(self.connect,fetcher=fetch,now=self.now+2)
        self.assertEqual(len(results),2)
        self.assertTrue(all(x[1]=="success" and x[2]==1 for x in results))
        self.assertEqual(worker.tick(self.connect,fetcher=fetch,now=self.now+2),[])
        with self.connect() as c:
            self.assertEqual(crm.overview(c,1,"a")["leads"][0]["contact"],"token-a@example.com")
            self.assertEqual(crm.overview(c,1,"b")["leads"][0]["contact"],"token-b@example.com")
    def test_unconnected_workspace_skipped(self):
        with self.connect() as c:sync.set_policy(c,1,"a","daily",now=self.now-86400)
        self.assertEqual(worker.tick(self.connect,now=self.now+2),[])
    def test_failed_sync_is_recorded(self):
        self.provision("a")
        results=worker.tick(self.connect,fetcher=lambda *args:(_ for _ in ()).throw(ValueError("provider error")),now=self.now+2)
        self.assertEqual(results,[("a","failed",0)])
        with self.connect() as c:
            self.assertEqual(sync.overview(c,1,"a")[2][0][0],"failed")
    def test_disconnect_prevents_future_runs(self):
        self.provision("a")
        with self.connect() as c:oauth.disconnect(c,1,"a")
        self.assertEqual(worker.tick(self.connect,now=self.now+2),[])

if __name__=="__main__":unittest.main()
