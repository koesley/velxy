import sqlite3
import unittest
from unittest.mock import patch
import business_intelligence_v60 as intelligence
import business_agents_v59 as agents
import business_os_v59 as leads

class IntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.access=patch.object(agents.core,"access",return_value="owner")
        self.audit=patch.object(agents.core,"audit")
        self.access.start();self.audit.start()
    def tearDown(self):
        self.access.stop();self.audit.stop();self.c.close()
    def test_suggestions_are_workspace_scoped(self):
        leads.add_lead(self.c,1,"a","Example","example@example.com","web",100)
        report=intelligence.analyze(self.c,1,"a")
        self.assertEqual(report["open_potential"],100)
        self.assertIn("new_leads",[s["code"] for s in report["suggestions"]])
        self.assertEqual(intelligence.analyze(self.c,1,"b")["lead_count"],0)
        intelligence.enqueue(self.c,1,"a","new_leads")
        self.assertEqual(len(agents.overview(self.c,1,"a")["jobs"]),1)
        self.assertEqual(len(agents.overview(self.c,1,"b")["jobs"]),0)
    def test_unknown_suggestion_rejected(self):
        with self.assertRaises(ValueError):
            intelligence.enqueue(self.c,1,"a","invalid")
    def test_html_escaped(self):
        leads.add_lead(self.c,1,"a","<script>","test@example.com","web",10)
        self.assertNotIn("<script>",intelligence.render(self.c,1,"a","csrf"))

if __name__=="__main__":unittest.main()
