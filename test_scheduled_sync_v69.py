import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import scheduled_sync_v69 as worker
import sync_control_v68 as sync
import business_os_v59 as crm

class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=self.tmp.name+"/db.sqlite"
        self.access=patch.object(crm.core,"access",return_value="owner")
        self.audit=patch.object(crm.core,"audit")
        self.access.start();self.audit.start()
    def tearDown(self):
        self.access.stop();self.audit.stop();self.tmp.cleanup()
    def connect(self):
        import persistent
        return persistent.connect(self.path)
    def test_due_worker_claims_once(self):
        with self.connect() as c:
            sync.set_policy(c,1,"a","daily",now=100)
            sync.set_policy(c,1,"b","weekly",now=100)
        def fetch(url,token):
            return {"results":[{"properties":{"firstname":"Ada","lastname":"Lovelace","email":"ada@example.com"}}]}
        with patch.dict(os.environ,{"VELXTRIA_V67_HUBSPOT_TOKEN":"long-enough-test-token"}):
            result=worker.tick(self.connect,fetcher=fetch,now=86500)
            self.assertEqual(result,[("a","success",1)])
            self.assertEqual(worker.tick(self.connect,fetcher=fetch,now=86500),[])
        with self.connect() as c:
            self.assertEqual(len(sync.overview(c,1,"a")[2]),1)
            self.assertEqual(len(sync.overview(c,1,"b")[2]),0)
    def test_disabled_not_due(self):
        with self.connect() as c:sync.set_policy(c,1,"a","off",now=100)
        self.assertEqual(worker.tick(self.connect,now=100000),[])
    def test_failure_does_not_leak_and_no_immediate_retry(self):
        with self.connect() as c:sync.set_policy(c,1,"a","daily",now=100)
        with patch.dict(os.environ,{"VELXTRIA_V67_HUBSPOT_TOKEN":"long-enough-test-token"}):
            result=worker.tick(self.connect,fetcher=lambda *args:(_ for _ in ()).throw(ValueError("secret error")),now=86500)
            self.assertEqual(result,[("a","failed",0)])
            self.assertEqual(worker.tick(self.connect,now=86500),[])

if __name__=="__main__":unittest.main()
