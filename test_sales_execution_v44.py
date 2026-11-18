"""V44 sales execution regression tests."""
import sqlite3
import unittest
from unittest.mock import patch
import growth_strategy_v42 as strategy
import sales_execution_v44 as sales

class SalesExecutionTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(":memory:")
  self.c.execute("CREATE TABLE empire_members(workspace_id TEXT,user_id INTEGER)")
  self.c.executemany("INSERT INTO empire_members VALUES (?,?)",[("a",1),("a",2),("b",3)])
  strategy.setup(self.c);sales.setup(self.c)
  self.c.execute("INSERT INTO vx_growth_strategy42 VALUES (?,?,?,?,?,?,?,?,?,?,?)",("plan-a","a",1,"Win prospects","reason","Calls","10","2026-12-01","open","high",1))
  self.c.execute("INSERT INTO vx_growth_strategy42 VALUES (?,?,?,?,?,?,?,?,?,?,?)",("plan-b","b",3,"Other","reason","Calls","10","2026-12-01","open","high",1))
 def tearDown(self):self.c.close()
 @patch("sales_execution_v44.bos.core.access")
 def test_lifecycle_and_metrics(self,access):
  identifier=sales.create(self.c,1,"a","plan-a",2,"Prospect A","call","Call to discuss quote","2026-11-01")
  snap=sales.snapshot(self.c,1,"a",today="2026-11-18")
  self.assertEqual((snap["open"],snap["overdue"]),(1,1))
  with self.assertRaises(ValueError):sales.update(self.c,1,"a",identifier,"contacted","Called")
  sales.update(self.c,2,"a",identifier,"contacted","Called")
  sales.update(self.c,2,"a",identifier,"won","Confirmed verbally")
  snap=sales.snapshot(self.c,1,"a",today="2026-11-18")
  self.assertEqual((snap["open"],snap["won_marked"]),(0,1))
  self.assertEqual(self.c.execute("SELECT COUNT(*) FROM vx_sales_events44").fetchone()[0],2)
  with self.assertRaises(ValueError):sales.update(self.c,2,"a",identifier,"queued","Reopen")
 @patch("sales_execution_v44.bos.core.access")
 def test_cross_tenant_rejected(self,access):
  with self.assertRaises(ValueError):sales.create(self.c,1,"a","plan-b",1,"Contact","email","Email","2026-11-20")
  with self.assertRaises(ValueError):sales.create(self.c,1,"a","plan-a",3,"Contact","email","Email","2026-11-20")
  identifier=sales.create(self.c,1,"a","plan-a",1,"Contact","email","Email","2026-11-20")
  with self.assertRaises(ValueError):sales.update(self.c,3,"b",identifier,"won","Wrong workspace")
  self.assertEqual(sales.snapshot(self.c,3,"b")["items"],[])
 @patch("sales_execution_v44.bos.core.access")
 def test_validation_and_html_escaping(self,access):
  for due in ("2026-02-30","tomorrow"):
   with self.assertRaises(ValueError):sales.create(self.c,1,"a","plan-a",1,"A","call","Call",due)
  with self.assertRaises(ValueError):sales.create(self.c,1,"a","plan-a",1,"A","call","", "2026-11-20")
  sales.create(self.c,1,"a","plan-a",1,"<script>alert(1)</script>","call","Call","2026-11-20")
  with patch("sales_execution_v44.strategy.analyze",return_value=[{"id":"plan-a","title":"Win prospects","status":"open"}]):
   output=sales.render(self.c,1,"a","csrf-value")
  self.assertNotIn("<script>",output)
  self.assertIn("&lt;script&gt;",output)
 @patch("sales_execution_v44.bos.core.access",side_effect=ValueError("Denied"))
 def test_access_denied(self,access):
  with self.assertRaises(ValueError):sales.snapshot(self.c,3,"a")

if __name__=="__main__":unittest.main()
