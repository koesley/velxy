import sqlite3
import unittest
from unittest.mock import patch
import integrations_v65 as v65
import business_agents_v59 as agents

ENV={"VELXTRIA_V65_WEBHOOK_URL":"https://hooks.example.com/velxtria",
     "VELXTRIA_V65_ALLOWED_HOST":"hooks.example.com",
     "VELXTRIA_V65_WEBHOOK_SECRET":"a-secure-test-secret-with-length"}

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.access=patch.object(agents.core,"access",return_value="owner")
        self.audit=patch.object(agents.core,"audit")
        self.access.start();self.audit.start()
    def tearDown(self):
        self.access.stop();self.audit.stop();self.c.close()
    def job(self,wid="a",approve=True):
        jid=agents.create_job(self.c,1,wid,"sales","Follow up on lead")
        if approve:
            agents.propose_job(self.c,1,wid,jid,"Approved outbound proposal")
            agents.review_job(self.c,1,wid,jid,"approved","Approved")
        return jid
    def test_approved_signed_dispatch_and_one_attempt(self):
        jid=self.job()
        captured=[]
        def deliver(url,raw,signature):
            captured.append((url,raw,signature))
            return 202
        with patch.dict("os.environ",ENV):
            _,state=v65.dispatch(self.c,1,"a",jid,dispatcher=deliver)
            self.assertEqual(state,"delivered")
            self.assertEqual(len(captured),1)
            self.assertEqual(len(captured[0][2]),64)
            with self.assertRaises(sqlite3.IntegrityError):
                v65.dispatch(self.c,1,"a",jid,dispatcher=deliver)
        self.assertEqual(len(v65.overview(self.c,1,"b")[2]),0)
    def test_unapproved_and_cross_tenant(self):
        jid=self.job(approve=False)
        with patch.dict("os.environ",ENV):
            with self.assertRaises(ValueError):v65.dispatch(self.c,1,"a",jid,dispatcher=lambda *args:200)
            with self.assertRaises(ValueError):v65.dispatch(self.c,1,"b",jid,dispatcher=lambda *args:200)
    def test_reject_local_destination(self):
        with patch.dict("os.environ",{**ENV,"VELXTRIA_V65_WEBHOOK_URL":"https://localhost/webhook","VELXTRIA_V65_ALLOWED_HOST":"localhost"}):
            with self.assertRaises(ValueError):v65.config()
    def test_failed_attempt_not_retried(self):
        jid=self.job()
        with patch.dict("os.environ",ENV):
            _,state=v65.dispatch(self.c,1,"a",jid,dispatcher=lambda *args:503)
        self.assertEqual(state,"failed")

if __name__=="__main__":unittest.main()
