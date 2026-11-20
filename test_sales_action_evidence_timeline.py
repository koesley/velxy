"""Regression tests for workspace-isolated sales action evidence timeline."""
import sqlite3
import unittest
from unittest.mock import patch
import sales_execution_v44 as sales

class EvidenceTimelineTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(":memory:")
  self.c.execute("CREATE TABLE empire_members(workspace_id TEXT,user_id INTEGER)")
  sales.setup(self.c)
  for wid,aid in (("a","one"),("b","other")):
   self.c.execute("INSERT INTO vx_sales_actions44 VALUES (?,?,?,?,?,?,?,?,?,?,?)",
    (aid,wid,"plan",1,"Client","call","Follow up","2026-11-20","contacted",1,1))
  for i in range(7):
   self.c.execute("INSERT INTO vx_sales_events44 VALUES (?,?,?,?,?,?,?,?)",
    ("event-"+str(i),"a","one",1,"queued","contacted","Note "+str(i),100+i))
  self.c.execute("INSERT INTO vx_sales_events44 VALUES (?,?,?,?,?,?,?,?)",
   ("private","b","other",2,"queued","contacted","Secret",200))
 def tearDown(self):self.c.close()

 @patch("sales_execution_v44.bos.core.access")
 def test_bounded_ordered_history(self,access):
  items=sales.evidence_timeline(self.c,1,"a",["one"])
  self.assertEqual(len(items["one"]),5)
  self.assertEqual(items["one"][0]["note"],"Note 6")
  self.assertEqual(items["one"][-1]["note"],"Note 2")
  self.assertIn("UTC",items["one"][0]["when"])

 @patch("sales_execution_v44.bos.core.access")
 def test_cross_workspace_events_not_returned(self,access):
  self.assertEqual(sales.evidence_timeline(self.c,1,"a",["other"]),{"other":[]})
  self.assertEqual(sales.evidence_timeline(self.c,2,"b",["one"]),{"one":[]})

 @patch("sales_execution_v44.bos.core.access",side_effect=ValueError("Denied"))
 def test_access_required(self,access):
  with self.assertRaises(ValueError):sales.evidence_timeline(self.c,3,"a",["one"])

 @patch("sales_execution_v44.bos.core.access")
 def test_invalid_limits_and_ids(self,access):
  for limit in (0,11,True if False else -1):
   with self.assertRaises(ValueError):sales.evidence_timeline(self.c,1,"a",["one"],limit)
  with self.assertRaises(ValueError):sales.evidence_timeline(self.c,1,"a",["x"]*201)
  with self.assertRaises(ValueError):sales.evidence_timeline(self.c,1,"a",[None])
  self.assertEqual(sales.evidence_timeline(self.c,1,"a",[]),{})

 @patch("sales_execution_v44.bos.core.access")
 def test_index_created(self,access):
  indexes=[r[1] for r in self.c.execute("PRAGMA index_list('vx_sales_events44')")]
  self.assertIn("vx_sales_events44_timeline",indexes)

if __name__=="__main__":unittest.main()
