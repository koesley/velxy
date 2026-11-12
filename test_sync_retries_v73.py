import os
import tempfile
import time
import unittest
from unittest.mock import patch
from cryptography.fernet import Fernet
import persistent
import hubspot_oauth_v70 as oauth
import sync_retries_v73 as retry
import business_os_v59 as crm

class RetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=self.tmp.name+"/db.sqlite"
        self.now=int(time.time())
        self.env=patch.dict(os.environ,{"VELXTRIA_V70_HUBSPOT_CLIENT_ID":"client","VELXTRIA_V70_HUBSPOT_CLIENT_SECRET":"secret","VELXTRIA_V70_HUBSPOT_REDIRECT_URI":"https://example.com/hubspot-oauth-v70/callback","VELXTRIA_V70_ENCRYPTION_KEY":Fernet.generate_key().decode()})
        self.env.start()
        self.access=patch.object(crm.core,"access",return_value="owner")
        self.audit=patch.object(crm.core,"audit")
        self.access.start();self.audit.start()
    def tearDown(self):
        self.access.stop();self.audit.stop();self.env.stop();self.tmp.cleanup()
    def connect(self):return persistent.connect(self.path)
    def provision(self,wid):
        from urllib.parse import urlsplit,parse_qs
        with self.connect() as c:
            state=parse_qs(urlsplit(oauth.begin(c,1,wid,now=self.now)).query)["state"][0]
            oauth.finish(c,1,state,"code",requester=lambda *args:{"access_token":"token-"+wid,"refresh_token":"refresh-"+wid,"expires_in":7200},now=self.now)
    def test_retry_success_and_workspace_scope(self):
        self.provision("a");self.provision("b")
        with self.connect() as c:
            retry.enqueue(c,"a",1,now=self.now)
            retry.enqueue(c,"a",1,now=self.now)
            self.assertEqual(retry.metrics(c,1,"a"),[("pending",1)])
            self.assertEqual(retry.metrics(c,1,"b"),[])
        def fetch(url,token):return {"results":[{"properties":{"email":token+"@example.com"}}]}
        self.assertEqual(retry.tick(self.connect,fetcher=fetch,now=self.now+300),[("a","success",1)])
        self.assertEqual(retry.tick(self.connect,fetcher=fetch,now=self.now+300),[])
        with self.connect() as c:self.assertEqual(retry.metrics(c,1,"a"),[("success",1)])
    def test_bounded_failures(self):
        self.provision("a")
        with self.connect() as c:retry.enqueue(c,"a",1,now=self.now)
        def fail(*args):raise ValueError("transient")
        for offset in (300,2100,9300):
            self.assertEqual(retry.tick(self.connect,fetcher=fail,now=self.now+offset),[("a","failed",0)])
        with self.connect() as c:self.assertEqual(retry.metrics(c,1,"a"),[("exhausted",1)])
    def test_disconnect_skips(self):
        self.provision("a")
        with self.connect() as c:
            retry.enqueue(c,"a",1,now=self.now)
            oauth.disconnect(c,1,"a")
        self.assertEqual(retry.tick(self.connect,now=self.now+300),[])

if __name__=="__main__":unittest.main()
