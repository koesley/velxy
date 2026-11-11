import sqlite3
import unittest
from unittest.mock import patch
import business_collaboration_v62 as v62
import business_agents_v59 as agents

class V62Tests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.access=patch.object(agents.core,"access",return_value="owner")
        self.audit=patch.object(agents.core,"audit")
        self.access.start();self.audit.start()
    def tearDown(self):
        self.access.stop();self.audit.stop();self.c.close()
    def test_public_only_published_faq(self):
        agents.add_knowledge(self.c,1,"a","faq","What are your hours?","9 to 5")
        agents.add_knowledge(self.c,1,"a","memory","Secret","Private detail")
        token=v62.publish(self.c,1,"a",True)
        page=v62.widget_html(self.c,token,"What are your hours?")
        self.assertIn("9 to 5",page)
        self.assertNotIn("Private detail",page)
        v62.publish(self.c,1,"a",False)
        self.assertIsNone(v62.widget_html(self.c,token))
    def test_token_rotation_revokes_old(self):
        old=v62.publish(self.c,1,"a",True)
        new=v62.rotate(self.c,1,"a")
        self.assertNotEqual(old,new)
        self.assertIsNone(v62.public_faq(self.c,old))
        self.assertIsNotNone(v62.public_faq(self.c,new))
    def test_collaboration_creates_five_scoped_jobs(self):
        v62.collaborate(self.c,1,"a","Improve lead follow-up process")
        self.assertEqual(len(agents.overview(self.c,1,"a")["jobs"]),5)
        self.assertEqual(len(agents.overview(self.c,1,"b")["jobs"]),0)
    def test_escape_faq_html(self):
        agents.add_knowledge(self.c,1,"a","faq","<script>","<b>answer</b>")
        token=v62.publish(self.c,1,"a",True)
        page=v62.widget_html(self.c,token)
        self.assertNotIn("<script>",page)
        self.assertNotIn("<b>answer</b>",page)

if __name__=="__main__":unittest.main()
