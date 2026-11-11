import sqlite3
import unittest
from unittest.mock import patch
import business_agents_v59 as agents

class AgentWorkforceTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.p1=patch.object(agents.core,"access",return_value="owner")
        self.p2=patch.object(agents.core,"audit")
        self.p1.start();self.p2.start()
    def tearDown(self):
        self.p1.stop();self.p2.stop();self.c.close()
    def test_job_lifecycle_and_isolation(self):
        jid=agents.create_job(self.c,1,"alpha","sales","Review dormant leads")
        self.assertEqual(len(agents.overview(self.c,1,"beta")["jobs"]),0)
        with self.assertRaises(ValueError):agents.propose_job(self.c,1,"beta",jid,"Follow up")
        agents.propose_job(self.c,1,"alpha",jid,"Prepare a follow-up draft")
        with self.assertRaises(ValueError):agents.complete_job(self.c,1,"alpha",jid)
        agents.review_job(self.c,1,"alpha",jid,"approved","Reviewed")
        agents.complete_job(self.c,1,"alpha",jid)
        self.assertEqual(agents.overview(self.c,1,"alpha")["jobs"][0]["status"],"completed")
    def test_knowledge_isolation_and_escaping(self):
        kid=agents.add_knowledge(self.c,1,"alpha","faq","Hours?","<script>bad</script>")
        self.assertEqual(len(agents.overview(self.c,1,"beta")["knowledge"]),0)
        self.assertNotIn("<script>",agents.render(self.c,1,"alpha","csrf"))
        with self.assertRaises(ValueError):agents.remove_knowledge(self.c,1,"beta",kid)
        agents.remove_knowledge(self.c,1,"alpha",kid)
        self.assertEqual(agents.overview(self.c,1,"alpha")["counts"]["approved_knowledge"],0)

if __name__=="__main__":
    unittest.main()
