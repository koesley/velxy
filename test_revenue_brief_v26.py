import sqlite3
import unittest
from unittest.mock import patch
from revenue_brief_v26 import build,render

class DailyBriefTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.execute("CREATE TABLE vx_followup23 (workspace_id TEXT,status TEXT,due_date TEXT)")
        self.c.execute("CREATE TABLE bos59_actions (workspace_id TEXT,decision TEXT)")
        self.c.execute("CREATE TABLE bos59_leads (workspace_id TEXT,status TEXT)")
        self.c.execute("INSERT INTO vx_followup23 VALUES ('one','planned','2000-01-01')")
        self.c.execute("INSERT INTO vx_followup23 VALUES ('two','planned','2000-01-01')")
        self.c.execute("INSERT INTO bos59_actions VALUES ('one','pending')")
        self.c.execute("INSERT INTO bos59_leads VALUES ('one','new')")
    def tearDown(self):self.c.close()

    @patch("revenue_brief_v26.conversion.summarize",return_value={})
    @patch("revenue_brief_v26.bos.core.access")
    def test_scoped_recommendations(self,access,summary):
        result=build(self.c,8,"one")
        self.assertEqual(len(result["actions"]),3)
        self.assertIn("1 scheduled",result["actions"][0]["detail"])
        self.assertIn("Daily Revenue Action Brief",render(self.c,8,"one"))
        access.assert_called_with(self.c,8,"one")

    @patch("revenue_brief_v26.bos.core.access",side_effect=ValueError("Denied"))
    def test_access_denied(self,access):
        with self.assertRaises(ValueError):build(self.c,8,"two")

if __name__=="__main__":unittest.main()
