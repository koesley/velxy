import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
class FirstContactTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'VELXTRIA_DATA_DIR':self.tmp.name,'VELXTRIA_LOCAL_STUDIO':'1','VELXTRIA_DEPLOYMENT_MODE':'local'});self.env.start()
  import portal,empire_v19,launchpad_v27,first_contact_v31
  self.portal=portal;self.mod=first_contact_v31;self.old_db=portal.DB;portal.DB=Path(self.tmp.name)/'portal.sqlite3';self.c=portal.db()
  self.c.execute("INSERT INTO users(id,email,salt,pw_hash,role,access,created) VALUES(1,'a@example.test','a','b','customer','demo',0),(2,'b@example.test','a','b','customer','demo',0)")
  self.w1=empire_v19.create(self.c,1,'Pilot <script>');self.w2=empire_v19.create(self.c,2,'Private');self.p1=launchpad_v27.create(self.c,1,self.w1,'Pilot A');self.p2=launchpad_v27.create(self.c,2,self.w2,'Pilot B');self.c.commit()
 def tearDown(self):self.c.close();self.portal.DB=self.old_db;self.env.stop();self.tmp.cleanup()
 def test_isolation_and_escaping(self):
  iid=self.mod.create(self.c,1,self.w1,self.p1,'A <script> issue','An issue description', 'high');self.c.commit()
  page=self.mod.render(self.c,1,'token',self.w1)
  self.assertIn('A &lt;script&gt; issue',page);self.assertNotIn('Private',page)
  with self.assertRaises(ValueError):self.mod.render(self.c,1,'token',self.w2)
  with self.assertRaises(ValueError):self.mod.create(self.c,1,self.w1,self.p2,'Wrong pilot','This is an issue','low')
  with self.assertRaises(ValueError):self.mod.resolve(self.c,2,self.w2,iid)
 def test_status_and_validation(self):
  iid=self.mod.create(self.c,1,self.w1,self.p1,'Broken workflow','Workflow did not run','medium')
  with self.assertRaises(ValueError):self.mod.create(self.c,1,self.w1,self.p1,'bad','short','urgent')
  self.mod.resolve(self.c,1,self.w1,iid)
  with self.assertRaises(ValueError):self.mod.resolve(self.c,1,self.w1,iid)
 def test_read_only_render(self):
  before=self.c.total_changes;self.mod.render(self.c,1,'token',self.w1);self.assertEqual(before,self.c.total_changes)
if __name__=='__main__':unittest.main()
