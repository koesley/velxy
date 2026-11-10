import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
class HorizonTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'VELXTRIA_DATA_DIR':self.tmp.name,'VELXTRIA_LOCAL_STUDIO':'1','VELXTRIA_DEPLOYMENT_MODE':'local'});self.env.start()
  import portal,empire_v19,launchpad_v27,first_contact_v31,horizon_v32
  self.portal=portal;self.mod=horizon_v32;self.old_db=portal.DB;portal.DB=Path(self.tmp.name)/'portal.sqlite3';self.c=portal.db()
  self.c.execute("INSERT INTO users(id,email,salt,pw_hash,role,access,created) VALUES(1,'a@example.test','a','b','customer','demo',0),(2,'b@example.test','a','b','customer','demo',0)")
  self.w1=empire_v19.create(self.c,1,'Pilot <script>');self.w2=empire_v19.create(self.c,2,'Private')
  p1=launchpad_v27.create(self.c,1,self.w1,'Pilot A');p2=launchpad_v27.create(self.c,2,self.w2,'Pilot B')
  self.i1=first_contact_v31.create(self.c,1,self.w1,p1,'Broken workflow','Workflow failed during test','high')
  self.i2=first_contact_v31.create(self.c,2,self.w2,p2,'Other workflow','Private issue description','low');self.c.commit()
 def tearDown(self):self.c.close();self.portal.DB=self.old_db;self.env.stop();self.tmp.cleanup()
 def test_isolation_and_escaping(self):
  pid=self.mod.create(self.c,1,self.w1,self.i1,'critical','Fix <script> failed process','Failures per 100 runs',20,5)
  page=self.mod.render(self.c,1,'token',self.w1)
  self.assertIn('Fix &lt;script&gt;',page);self.assertNotIn('Private issue',page)
  with self.assertRaises(ValueError):self.mod.render(self.c,1,'token',self.w2)
  with self.assertRaises(ValueError):self.mod.create(self.c,1,self.w1,self.i2,'high','Do not allow this','Failure count',10,2)
  with self.assertRaises(ValueError):self.mod.update(self.c,2,self.w2,pid,'verified',3)
 def test_measurement_validation(self):
  pid=self.mod.create(self.c,1,self.w1,self.i1,'high','Fix failing workflow','Failures per 100 runs',20,5)
  with self.assertRaises(ValueError):self.mod.create(self.c,1,self.w1,self.i1,'high','Duplicate plan title','Failures per 100 runs',20,5)
  with self.assertRaises(ValueError):self.mod.update(self.c,1,self.w1,pid,'verified','')
  with self.assertRaises(ValueError):self.mod.update(self.c,1,self.w1,pid,'verified','nan')
  self.mod.update(self.c,1,self.w1,pid,'verified',4)
  self.assertEqual(self.c.execute('SELECT result FROM horizon_plans WHERE id=?',(pid,)).fetchone()[0],4)
 def test_read_only_render(self):
  before=self.c.total_changes;self.mod.render(self.c,1,'token',self.w1);self.assertEqual(before,self.c.total_changes)
if __name__=='__main__':unittest.main()
