import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
class SynapseTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'VELXTRIA_DATA_DIR':self.tmp.name,'VELXTRIA_LOCAL_STUDIO':'1','VELXTRIA_DEPLOYMENT_MODE':'local'});self.env.start()
  import portal,empire_v19,autonomous_core_v43 as core,synapse_v44 as syn
  self.p=portal;self.e=empire_v19;self.core=core;self.syn=syn;self.old=portal.DB;portal.DB=Path(self.tmp.name)/'portal.sqlite3';self.c=portal.db()
  self.c.execute("INSERT INTO users(id,email,salt,pw_hash,role,access,created) VALUES(1,'a@test.test','a','b','customer','demo',0),(2,'b@test.test','a','b','customer','demo',0)")
  self.w=self.e.create(self.c,1,'Workspace');self.other=self.e.create(self.c,2,'Private')
  self.c.execute('INSERT INTO prime_apps(id,workspace_id,name,schema_json,status,version,created_by,created) VALUES(?,?,?,?,?,?,?,?)',('app',self.w,'Sales','[]','published',1,1,1))
  self.c.execute('INSERT INTO nexus_goals VALUES(?,?,?,?,?,?,?,?,?,?)',('goal',self.w,'app','record_count','',None,3,'More records',1,1))
  self.eid=self.core.propose(self.c,1,self.w,'goal','Improve data','Collect more records over time','Manually review and add verified records','increase')
  self.c.commit()
 def tearDown(self):self.c.close();self.p.DB=self.old;self.env.stop();self.tmp.cleanup()
 def approve(self):self.core.decision(self.c,1,self.w,self.eid,True)
 def test_approval_gate(self):
  with self.assertRaises(ValueError):self.syn.create_task(self.c,1,self.w,self.eid,'Review sales','Manually review the sales records')
  with self.assertRaises(ValueError):self.syn.snapshot(self.c,1,self.w,self.eid,'Initial baseline record')
 def test_task_lifecycle_and_evidence(self):
  self.approve();tid=self.syn.create_task(self.c,1,self.w,self.eid,'Review sales','Manually review the sales records')
  with self.assertRaises(ValueError):self.syn.update_task(self.c,1,self.w,tid,'done','short')
  self.syn.update_task(self.c,1,self.w,tid,'in_progress')
  self.syn.update_task(self.c,1,self.w,tid,'done','Checked all available records')
  with self.assertRaises(ValueError):self.syn.update_task(self.c,1,self.w,tid,'cancelled')
  r=self.syn.report(self.c,1,self.w);self.assertEqual(r['progress'][self.eid]['tasks_done'],1)
 def test_finalize_requires_closed_tasks(self):
  self.approve();tid=self.syn.create_task(self.c,1,self.w,self.eid,'Review sales','Manually review the sales records')
  with self.assertRaises(ValueError):self.syn.finalize(self.c,1,self.w,self.eid,'Reviewed everything in detail')
  self.syn.update_task(self.c,1,self.w,tid,'cancelled')
  self.assertEqual(self.syn.finalize(self.c,1,self.w,self.eid,'Reviewed everything in detail'),0)
  with self.assertRaises(ValueError):self.syn.snapshot(self.c,1,self.w,self.eid,'Cannot measure after completion')
 def test_snapshots_and_isolation(self):
  self.approve();self.syn.snapshot(self.c,1,self.w,self.eid,'First measurement of records')
  self.c.execute('INSERT INTO prime_records(id,workspace_id,app_id,data_json,created_by,created) VALUES(?,?,?,?,?,?)',('rec',self.w,'app','{}',1,10))
  self.syn.snapshot(self.c,1,self.w,self.eid,'Second measurement after update')
  r=self.syn.report(self.c,1,self.w);self.assertEqual(r['progress'][self.eid]['snapshots'],2);self.assertEqual(r['progress'][self.eid]['change_from_baseline'],1)
  for fn in (lambda:self.syn.report(self.c,2,self.w),lambda:self.syn.create_task(self.c,2,self.w,self.eid,'Review sales','Manually review the sales records'),lambda:self.syn.snapshot(self.c,2,self.w,self.eid,'Cross tenant measurement')):
   with self.assertRaises(ValueError):fn()
 def test_readonly_and_html(self):
  self.approve();self.syn.create_task(self.c,1,self.w,self.eid,'<script>bad</script>','Manually review the sales records')
  before=self.c.total_changes;self.syn.report(self.c,1,self.w);self.assertEqual(before,self.c.total_changes)
  page=self.syn.render(self.c,1,'csrf',self.w);self.assertIn('&lt;script&gt;',page);self.assertNotIn('<script>bad</script>',page)
 def test_no_business_record_side_effects(self):
  self.approve();before=self.c.execute('SELECT count(*) FROM prime_records').fetchone()[0]
  self.syn.create_task(self.c,1,self.w,self.eid,'Review sales','Manually review the sales records')
  self.syn.snapshot(self.c,1,self.w,self.eid,'Measurement without mutation')
  self.assertEqual(before,self.c.execute('SELECT count(*) FROM prime_records').fetchone()[0])
if __name__=='__main__':unittest.main()
