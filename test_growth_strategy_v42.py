import sqlite3,unittest
from unittest.mock import patch
from growth_strategy_v42 import create,change,analyze,suggestions,setup
class GrowthStrategyTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(":memory:")
  self.c.execute("CREATE TABLE empire_members(workspace_id TEXT,user_id INTEGER)")
  self.c.executemany("INSERT INTO empire_members VALUES (?,?)",[("a",1),("a",2),("b",3)])
  setup(self.c)
 def tearDown(self):self.c.close()
 @patch("growth_strategy_v42.bos.core.access")
 def test_scoped_owner_and_event_log(self,access):
  with self.assertRaises(ValueError):create(self.c,1,"a",3,"Fix","Reason","Leads","10","2026-12-01","high")
  pid=create(self.c,1,"a",2,"Fix","Reason","Leads","10","2026-12-01","high")
  with self.assertRaises(ValueError):change(self.c,1,"a",pid,"completed","Done")
  with self.assertRaises(ValueError):change(self.c,2,"b",pid,"completed","Done")
  change(self.c,2,"a",pid,"in_progress","First outreach")
  change(self.c,2,"a",pid,"completed","Finished outreach")
  self.assertEqual(analyze(self.c,1,"a")[0]["status"],"completed")
  self.assertEqual(analyze(self.c,3,"b"),[])
  self.assertEqual(self.c.execute("SELECT count(*) FROM vx_growth_events42 WHERE workspace_id='a'").fetchone()[0],2)
  with self.assertRaises(ValueError):change(self.c,2,"a",pid,"open","Again")
 @patch("growth_strategy_v42.bos.core.access",side_effect=ValueError("Denied"))
 def test_denied(self,access):
  with self.assertRaises(ValueError):analyze(self.c,3,"a")
 def test_suggestions(self):
  data=dict(lead_count=0,acquisition_spend_cents=0,won_lead_count=0,pending_followups=0,campaigns=[],review_ready_campaigns=0)
  self.assertEqual(suggestions(data)[0][1],"Capture and qualify prospects")
if __name__=="__main__":unittest.main()
