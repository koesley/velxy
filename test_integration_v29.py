"""Focused V29 integration tests."""
import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

class IntegrationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.env=patch.dict(os.environ,{'VELXTRIA_DATA_DIR':self.tmp.name,'VELXTRIA_LOCAL_STUDIO':'1','VELXTRIA_DEPLOYMENT_MODE':'local'})
  self.env.start()
  import portal,empire_v19,integration_v29,launchpad_v27
  self.portal=portal;self.empire=empire_v19;self.mod=integration_v29;self.launchpad=launchpad_v27
  self.old_db=portal.DB;portal.DB=Path(self.tmp.name)/'portal.sqlite3'
  self.c=portal.db()
  self.c.execute("INSERT INTO users(id,email,salt,pw_hash,role,access,created) VALUES(1,'a@example.test','a','b','customer','demo',0),(2,'b@example.test','a','b','customer','demo',0)")
  self.w1=self.empire.create(self.c,1,'Alpha <Corp>');self.w2=self.empire.create(self.c,2,'Private Beta')
  self.c.commit()
 def tearDown(self):
  self.c.close();self.portal.DB=self.old_db;self.env.stop();self.tmp.cleanup()
 def test_workspace_isolation_and_escaping(self):
  page=self.mod.render(self.c,1,self.w1)
  self.assertIn('Alpha &lt;Corp&gt;',page)
  self.assertNotIn('Private Beta',page)
  with self.assertRaises(ValueError):self.mod.render(self.c,1,self.w2)
 def test_evidence_is_real_and_read_only(self):
  before=self.c.total_changes
  self.assertEqual(self.mod.journey(self.c,1,self.w1),[True,False,False,False,False])
  self.assertEqual(before,self.c.total_changes)
  self.assertIn('1 / 5',self.mod.render(self.c,1,self.w1))
 def test_schema_diagnostics_and_feedback_scoping(self):
  self.assertTrue(all(ok for _,ok in self.mod.diagnostics(self.c)))
  pilot=self.launchpad.create(self.c,2,self.w2,'Beta trial')
  self.launchpad.feedback(self.c,2,self.w2,pilot,5,'Excellent experience')
  self.assertEqual(self.mod.journey(self.c,1,self.w1)[-1],False)
  self.assertEqual(self.mod.journey(self.c,2,self.w2)[-1],True)

if __name__=='__main__':unittest.main()
