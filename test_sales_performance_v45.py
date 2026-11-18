"""V45 sales performance regression tests."""
import sqlite3,unittest
from unittest.mock import patch
import sales_performance_v45 as performance
import sales_execution_v44 as sales
import growth_strategy_v42 as strategy
class SalesPerformanceTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(":memory:")
  self.c.execute("CREATE TABLE empire_members(workspace_id TEXT,user_id INTEGER)")
  self.c.executemany("INSERT INTO empire_members VALUES (?,?)",[("a",1),("a",2),("b",3)])
  strategy.setup(self.c);sales.setup(self.c)
  self.c.executemany("INSERT INTO vx_growth_strategy42 VALUES (?,?,?,?,?,?,?,?,?,?,?)",[
   ("p1","a",1,"Revenue","Reason","Leads","10","2026-12-01","open","high",1),
   ("p2","b",3,"Other","Reason","Leads","10","2026-12-01","open","high",1)])
  self.c.executemany("INSERT INTO vx_sales_actions44 VALUES (?,?,?,?,?,?,?,?,?,?,?)",[
   ("a1","a","p1",1,"A & B","call","Follow up","2026-11-01","queued",1,1),
   ("a2","a","p1",2,"Customer 2","email","Reply","2026-11-18","contacted",1,1),
   ("a3","a","p1",1,"Customer 3","proposal","Close","2026-11-02","won",1,1),
   ("b1","b","p2",3,"SECRET","call","Private","2026-11-01","lost",1,1)])
  self.guard=patch("sales_performance_v45.bos.core.access")
  self.guard.start()
 def tearDown(self):
  self.guard.stop();self.c.close()
 def test_aggregates_and_tenant_isolation(self):
  d=performance.analyze(self.c,1,"a",today="2026-11-18")
  self.assertEqual((d["total"],d["open"],d["overdue"],d["due_today"],d["won_marked"]),(3,2,1,1,1))
  self.assertEqual(d["attention_total"],2)
  self.assertEqual(d["won_share_of_closed"],100.0)
  self.assertNotIn("SECRET",performance.render(self.c,1,"a"))
 def test_html_escape(self):
  rendered=performance.render(self.c,1,"a")
  self.assertIn("A &amp; B",rendered)
 def test_empty_workspace(self):
  d=performance.analyze(self.c,3,"b",today="2026-11-18")
  self.assertEqual(d["total"],1)
  self.c.execute("DELETE FROM vx_sales_actions44 WHERE workspace_id='b'")
  d=performance.analyze(self.c,3,"b",today="2026-11-18")
  self.assertIsNone(d["close_rate"])
  self.assertEqual(d["attention_total"],0)
 def test_not_capped_at_200(self):
  self.c.executemany("INSERT INTO vx_sales_actions44 VALUES (?,?,?,?,?,?,?,?,?,?,?)",[
   ("many"+str(i),"a","p1",1,"Customer","call","Action","2026-11-01","queued",1,1) for i in range(210)])
  d=performance.analyze(self.c,1,"a",today="2026-11-18")
  self.assertEqual(d["total"],213)
  self.assertEqual(len(d["attention"]),50)
  self.assertEqual(d["attention_total"],212)
 def test_access_control(self):
  with patch("sales_performance_v45.bos.core.access",side_effect=ValueError("Denied")):
   with self.assertRaises(ValueError):performance.analyze(self.c,3,"a")
if __name__=="__main__":unittest.main()
