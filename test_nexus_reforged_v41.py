"""V41: navigation, tenant isolation, safe rendering and read-only behavior."""
import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

class NexusReforgedTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.env=patch.dict(os.environ,{'VELXTRIA_DATA_DIR':self.tmp.name,'VELXTRIA_LOCAL_STUDIO':'1','VELXTRIA_DEPLOYMENT_MODE':'local'})
  self.env.start()
  import portal,empire_v19,nexus_reforged_v41
  self.portal=portal;self.empire=empire_v19;self.v41=nexus_reforged_v41
  self.old_db=portal.DB;portal.DB=Path(self.tmp.name)/'portal.sqlite3'
  self.c=portal.db()
  self.c.execute("INSERT INTO users(id,email,salt,pw_hash,role,access,created) VALUES(1,'one@example.test','a','b','customer','demo',0),(2,'two@example.test','a','b','customer','demo',0)")
  self.w1=self.empire.create(self.c,1,'Alpha <script>');self.w2=self.empire.create(self.c,2,'Private Beta')
  self.c.commit()
 def tearDown(self):
  self.c.close();self.portal.DB=self.old_db;self.env.stop();self.tmp.cleanup()
 def test_escapes_workspace_and_scopes_links(self):
  html=self.v41.render(self.c,1,self.w1)
  self.assertIn('Alpha &lt;script&gt;',html)
  self.assertNotIn('Alpha <script>',html)
  self.assertNotIn('Private Beta',html)
  self.assertIn('/oracle?w='+self.w1,html)
 def test_cross_tenant_workspace_denied(self):
  with self.assertRaises(ValueError):self.v41.render(self.c,1,self.w2)
 def test_unknown_workspace_denied(self):
  with self.assertRaises(ValueError):self.v41.render(self.c,1,'does-not-exist')
 def test_no_data_mutation(self):
  before=self.c.total_changes
  self.v41.render(self.c,1,self.w1)
  self.assertEqual(before,self.c.total_changes)
 def test_new_navigation_is_short_and_hub_is_available(self):
  shell=self.portal.shell('Test','<p>test</p>',{'id':1},'csrf')
  self.assertIn('/nexus-reforged',shell)
  self.assertNotIn('Omniscience V7',shell)
  self.assertIn('Nexus Reforged',self.v41.render(self.c,1,self.w1).replace('NEXUS REFORGED','Nexus Reforged'))
 def test_categories_and_search_are_present(self):
  html=self.v41.render(self.c,1,self.w1)
  for category in ('Operate','Understand','Grow','Trust'):self.assertIn(category,html)
  self.assertIn('id="v41search"',html)
if __name__=='__main__':unittest.main()
