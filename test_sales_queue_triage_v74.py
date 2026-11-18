"""Regression coverage for sales queue triage, tenant isolation, and >200 actions."""
import sqlite3
import unittest
from unittest.mock import patch
import sales_execution_v44 as sales

class SalesTriageTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(":memory:")
  self.c.execute("CREATE TABLE empire_members(workspace_id TEXT,user_id INTEGER)")
  self.c.execute("CREATE TABLE vx_growth_strategy42(id TEXT,workspace_id TEXT,title TEXT)")
  self.c.executemany("INSERT INTO empire_members VALUES (?,?)",[("a",1),("b",2)])
  self.c.executemany("INSERT INTO vx_growth_strategy42 VALUES (?,?,?)",[("p","a","Plan A"),("q","b","Plan B")])
  sales.setup(self.c)
  self.access=patch.object(sales.bos.core,"access",side_effect=lambda c,uid,wid,**kw: None if (uid,wid) in ((1,"a"),(2,"b")) else (_ for _ in ()).throw(PermissionError("denied")))
  self.access.start()
  self.addCleanup(self.access.stop)
  self.addCleanup(self.c.close)

 def add(self,wid,owner,due,stage,number):
  self.c.execute("INSERT INTO vx_sales_actions44 VALUES (?,?,?,?,?,?,?,?,?,?,?)",
    (wid+str(number),wid,"p" if wid=="a" else "q",owner,"Customer","call","Follow up",due,stage,1,1))

 def test_counts_include_all_rows_and_priority_first(self):
  for i in range(220):self.add("a",1,"2026-12-01","queued",i)
  self.add("a",1,"2026-01-01","queued",220)
  self.add("a",1,"2026-01-01","won",221)
  data=sales.snapshot(self.c,1,"a",today="2026-11-18")
  self.assertEqual((data["total"],data["open"],data["overdue"],data["won_marked"],data["shown"]),(222,221,1,1,200))
  self.assertEqual(data["items"][0]["priority"],"overdue")
  self.assertEqual(data["items"][0]["id"],"a220")

 def test_team_totals_and_tenant_isolation(self):
  self.add("a",1,"2026-01-01","queued",1)
  self.add("a",1,"2026-11-18","contacted",2)
  self.add("b",2,"2026-01-01","queued",3)
  self.assertEqual(sales.team_triage(self.c,1,"a","2026-11-18"),[{"owner":1,"open":2,"overdue":1,"due_today":1}])
  self.assertEqual(sales.snapshot(self.c,1,"a","2026-11-18")["total"],2)
  with self.assertRaises(PermissionError):sales.snapshot(self.c,1,"b","2026-11-18")

 def test_render_escapes_customer_content(self):
  self.add("a",1,"2026-01-01","queued",1)
  self.c.execute("UPDATE vx_sales_actions44 SET contact_label=? WHERE id='a1'",("<script>alert(1)</script>",))
  with patch.object(sales.strategy,"analyze",return_value=[]):
   page=sales.render(self.c,1,"a","csrf")
  self.assertNotIn("<script>",page)
  self.assertIn("&lt;script&gt;",page)
  self.assertIn("Team follow-up workload",page)

if __name__=="__main__":unittest.main()
