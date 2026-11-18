"""Prospect qualification authorization, handoff and escaping regression tests."""
import sqlite3,unittest
from unittest.mock import patch
import prospect_qualification_v46 as prospect
import growth_strategy_v42 as strategy
import sales_execution_v44 as sales
class ProspectTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(":memory:")
  self.c.execute("CREATE TABLE empire_members(workspace_id TEXT,user_id INTEGER)")
  self.c.executemany("INSERT INTO empire_members VALUES (?,?)",[("a",1),("a",2),("b",3)])
  prospect.setup(self.c);strategy.setup(self.c);sales.setup(self.c)
  self.auth=patch("prospect_qualification_v46.bos.core.access")
  self.sales_auth=patch("sales_execution_v44.bos.core.access")
  self.strategy_auth=patch("growth_strategy_v42.bos.core.access")
  self.auth.start();self.sales_auth.start();self.strategy_auth.start()
 def tearDown(self):
  self.auth.stop();self.sales_auth.stop();self.strategy_auth.stop();self.c.close()
 def make(self,owner=2,label="Acme"):
  return prospect.create(self.c,1,"a",owner,label,"website","Needs reporting","Unknown","high")
 def test_create_and_owner_validation(self):
  with self.assertRaises(ValueError):self.make(owner=3)
  with self.assertRaises(ValueError):prospect.create(self.c,1,"a",2,"","website","Need","Unknown","high")
  with self.assertRaises(ValueError):prospect.create(self.c,1,"a",2,"X","bad","Need","Unknown","high")
  self.assertEqual(prospect.snapshot(self.c,1,"a")["total"],0)
  self.make();self.assertEqual(prospect.snapshot(self.c,1,"a")["counts"]["new"],1)
  self.assertEqual(prospect.snapshot(self.c,3,"b")["total"],0)
 def test_owner_and_transition(self):
  pid=self.make()
  with self.assertRaises(ValueError):prospect.change(self.c,1,"a",pid,"qualified","Ready")
  with self.assertRaises(ValueError):prospect.change(self.c,2,"b",pid,"qualified","Ready")
  with self.assertRaises(ValueError):prospect.change(self.c,2,"a",pid,"converted","No")
  prospect.change(self.c,2,"a",pid,"qualified","Confirmed need")
  with self.assertRaises(ValueError):prospect.change(self.c,2,"a",pid,"qualified","Duplicate")
  self.assertEqual(self.c.execute("SELECT count(*) FROM vx_prospect_events46").fetchone()[0],1)
 def test_handoff_to_existing_sales_queue(self):
  pid=self.make();prospect.change(self.c,2,"a",pid,"qualified","Qualified")
  with self.assertRaises(ValueError):prospect.handoff(self.c,1,"a",pid,"plan","call","Follow up","2026-12-10")
  plan=strategy.create(self.c,1,"a",2,"Pipeline","Increase outreach","Calls","10","2026-12-30","high")
  action=prospect.handoff(self.c,2,"a",pid,plan,"call","Call tomorrow","2026-12-10")
  self.assertEqual(self.c.execute("SELECT stage FROM vx_prospects46 WHERE id=?",(pid,)).fetchone()[0],"converted")
  self.assertEqual(self.c.execute("SELECT contact_label FROM vx_sales_actions44 WHERE id=?",(action,)).fetchone()[0],"Acme")
  with self.assertRaises(ValueError):prospect.handoff(self.c,2,"a",pid,plan,"call","Repeat","2026-12-10")
 def test_render_escapes_and_scope(self):
  self.make(label="<script>alert(1)</script>")
  page=prospect.render(self.c,1,"a","csrf")
  self.assertNotIn("<script>",page)
  self.assertIn("&lt;script&gt;",page)
  self.assertNotIn("Acme",prospect.render(self.c,3,"b","csrf"))
if __name__=="__main__":unittest.main()
