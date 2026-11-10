"""Focused V28 tests. Run with python -m unittest test_ascension_v28."""
import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

class AscensionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.env=patch.dict(os.environ,{'VELXTRIA_DATA_DIR':self.tmp.name,'VELXTRIA_LOCAL_STUDIO':'1','VELXTRIA_DEPLOYMENT_MODE':'local'})
  self.env.start()
  import portal,empire_v19,ascension_v28
  self.portal=portal;self.empire=empire_v19;self.asc=ascension_v28
  self.old_db=portal.DB
  portal.DB=Path(self.tmp.name)/"portal.sqlite3"
  self.c=portal.db()
  self.c.execute("INSERT INTO users(id,email,salt,pw_hash,role,access,created) VALUES(1,'one@example.test','a','b','customer','demo',0),(2,'two@example.test','a','b','customer','demo',0)")
  self.w1=self.empire.create(self.c,1,'Alpha <Workspace>');self.w2=self.empire.create(self.c,2,'Beta')
  self.c.commit()
 def tearDown(self):self.c.close();self.portal.DB=self.old_db;self.env.stop();self.tmp.cleanup()
 def test_workspace_scoping_and_escaping(self):
  page=self.asc.dashboard(self.c,1,self.w1)
  self.assertIn('Alpha &lt;Workspace&gt;',page)
  self.assertNotIn('Beta',page)
  self.assertIn('/oracle?w='+self.w1,page)
  with self.assertRaises(ValueError):self.asc.dashboard(self.c,1,self.w2)
 def test_onboarding_is_data_driven(self):
  page=self.asc.dashboard(self.c,1,self.w1)
  self.assertIn('0 of 3 requirements completed',page)
  self.assertIn('aria-valuenow="0"',page)
 def test_no_mutation(self):
  before=self.c.total_changes
  self.asc.dashboard(self.c,1,self.w1)
  self.assertEqual(before,self.c.total_changes)

if __name__=='__main__':unittest.main()
