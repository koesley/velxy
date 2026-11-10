import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
class SovereignCoreTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'VELXTRIA_DATA_DIR':self.tmp.name,'VELXTRIA_LOCAL_STUDIO':'1','VELXTRIA_DEPLOYMENT_MODE':'local'});self.env.start()
  import portal,empire_v19,sovereign_core_v30
  self.portal=portal;self.empire=empire_v19;self.mod=sovereign_core_v30
  self.old_db=portal.DB;portal.DB=Path(self.tmp.name)/'portal.sqlite3';self.c=portal.db()
  self.c.execute("INSERT INTO users(id,email,salt,pw_hash,role,access,created) VALUES(1,'a@example.test','a','b','customer','demo',0),(2,'b@example.test','a','b','customer','demo',0)")
  self.w1=self.empire.create(self.c,1,'A <b>');self.w2=self.empire.create(self.c,2,'Private');self.c.commit()
 def tearDown(self):self.c.close();self.portal.DB=self.old_db;self.env.stop();self.tmp.cleanup()
 def test_release_fails_closed(self):
  checks=self.mod.assess(self.c,1,self.w1,self.portal.DB)
  self.assertIn(('Production release','BLOCKED','Blocked until outstanding checks are verified independently'),checks)
  self.assertIn('NOT READY',self.mod.render(self.c,1,self.w1,self.portal.DB))
 def test_workspace_access_and_html(self):
  page=self.mod.render(self.c,1,self.w1,self.portal.DB)
  self.assertIn('A &lt;b&gt;',page);self.assertNotIn('Private',page)
  with self.assertRaises(ValueError):self.mod.render(self.c,1,self.w2,self.portal.DB)
 def test_read_only(self):
  before=self.c.total_changes;self.mod.render(self.c,1,self.w1,self.portal.DB)
  self.assertEqual(before,self.c.total_changes)
if __name__=='__main__':unittest.main()
