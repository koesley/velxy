import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
class EvolutionaryCoreTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'VELXTRIA_DATA_DIR':self.tmp.name,'VELXTRIA_LOCAL_STUDIO':'1','VELXTRIA_DEPLOYMENT_MODE':'local'});self.env.start()
  import portal,empire_v19,launchpad_v27,first_contact_v31,horizon_v32,evolutionary_core_v33
  self.portal=portal;self.mod=evolutionary_core_v33;self.horizon=horizon_v32;self.old_db=portal.DB;portal.DB=Path(self.tmp.name)/'portal.sqlite3';self.c=portal.db()
  self.c.execute("INSERT INTO users(id,email,salt,pw_hash,role,access,created) VALUES(1,'a@example.test','a','b','customer','demo',0),(2,'b@example.test','a','b','customer','demo',0)")
  self.w1=empire_v19.create(self.c,1,'First <script>');self.w2=empire_v19.create(self.c,2,'Other workspace')
  pilot=launchpad_v27.create(self.c,1,self.w1,'Pilot');other=launchpad_v27.create(self.c,2,self.w2,'Other')
  issue=first_contact_v31.create(self.c,1,self.w1,pilot,'Broken workflow','The workflow failed in testing','high')
  self.plan=self.horizon.create(self.c,1,self.w1,issue,'high','Repair the failing workflow','Failures per 100 runs',20,5)
  self.c.commit()
 def tearDown(self):self.c.close();self.portal.DB=self.old_db;self.env.stop();self.tmp.cleanup()
 def test_review_gate(self):
  rid=self.mod.create(self.c,1,self.w1,self.plan,'Workflow reliability patch','33.0-rc1')
  with self.assertRaises(ValueError):self.mod.review(self.c,1,self.w1,rid,'approved','Reviewed and looks fine')
  self.mod.record_test(self.c,1,self.w1,rid,'failed','Failure reproduced in staging')
  with self.assertRaises(ValueError):self.mod.review(self.c,1,self.w1,rid,'approved','Reviewed and looks fine')
  self.mod.record_test(self.c,1,self.w1,rid,'passed','Manual regression checks passed in local staging')
  with self.assertRaises(ValueError):self.mod.review(self.c,1,self.w1,rid,'approved','Reviewed and looks fine')
  self.horizon.update(self.c,1,self.w1,self.plan,'verified',4)
  self.mod.review(self.c,1,self.w1,rid,'approved','Approved for controlled pilot review')
  with self.assertRaises(ValueError):self.mod.record_test(self.c,1,self.w1,rid,'failed','Change result after approval')
  with self.assertRaises(ValueError):self.mod.review(self.c,1,self.w1,rid,'rejected','Try changing the decision')
 def test_workspace_and_escaping(self):
  rid=self.mod.create(self.c,1,self.w1,self.plan,'Patch <script> failing workflow','33.0-rc1')
  page=self.mod.render(self.c,1,'csrf',self.w1)
  self.assertIn('Patch &lt;script&gt;',page)
  self.assertNotIn('Patch <script>',page)
  with self.assertRaises(ValueError):self.mod.render(self.c,2,'csrf',self.w1)
  with self.assertRaises(ValueError):self.mod.create(self.c,2,self.w2,self.plan,'Attempt to steal plan','33.0')
  with self.assertRaises(ValueError):self.mod.record_test(self.c,2,self.w2,rid,'passed','I should not be able to update this')
 def test_read_only_render_and_validation(self):
  changes=self.c.total_changes
  self.mod.render(self.c,1,'csrf',self.w1)
  self.assertEqual(changes,self.c.total_changes)
  with self.assertRaises(ValueError):self.mod.create(self.c,1,self.w1,self.plan,'a','v')
  rid=self.mod.create(self.c,1,self.w1,self.plan,'Fix workflow errors','33.0')
  with self.assertRaises(ValueError):self.mod.record_test(self.c,1,self.w1,rid,'passed','too short')
  with self.assertRaises(ValueError):self.mod.review(self.c,1,self.w1,rid,'approved','too short')
if __name__=='__main__':unittest.main()
