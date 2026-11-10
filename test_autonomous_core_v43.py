import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
class CoreTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'VELXTRIA_DATA_DIR':self.tmp.name,'VELXTRIA_LOCAL_STUDIO':'1','VELXTRIA_DEPLOYMENT_MODE':'local'});self.env.start()
  import portal,empire_v19,autonomous_core_v43 as core
  self.p=portal;self.e=empire_v19;self.core=core;self.old=portal.DB;portal.DB=Path(self.tmp.name)/'portal.sqlite3';self.c=portal.db()
  self.c.execute("INSERT INTO users(id,email,salt,pw_hash,role,access,created) VALUES(1,'a@test.test','a','b','customer','demo',0),(2,'b@test.test','a','b','customer','demo',0)")
  self.w=self.e.create(self.c,1,'Workspace');self.other=self.e.create(self.c,2,'Private')
  self.c.execute('INSERT INTO prime_apps(id,workspace_id,name,schema_json,status,version,created_by,created) VALUES(?,?,?,?,?,?,?,?)',('app',self.w,'Sales','[]','published',1,1,1))
  self.c.execute('INSERT INTO nexus_goals VALUES(?,?,?,?,?,?,?,?,?,?)',('goal',self.w,'app','record_count','',None,3,'More records',1,1))
  self.c.commit()
 def tearDown(self):self.c.close();self.p.DB=self.old;self.env.stop();self.tmp.cleanup()
 def create(self):return self.core.propose(self.c,1,self.w,'goal','Improve data','More records should be collected','Manually review and add verified records','increase')
 def test_full_lifecycle(self):
  eid=self.create();self.assertEqual(self.core.report(self.c,1,self.w)['summary']['proposed'],1)
  with self.assertRaises(ValueError):self.core.complete(self.c,1,self.w,eid,'Measured after the experiment')
  self.core.decision(self.c,1,self.w,eid,True)
  self.c.execute('INSERT INTO prime_records(id,workspace_id,app_id,data_json,created_by,created) VALUES(?,?,?,?,?,?)',('rec',self.w,'app','{}',1,10))
  self.assertEqual(self.core.complete(self.c,1,self.w,eid,'Manually entered one verified record'),1)
  r=self.core.report(self.c,1,self.w);self.assertTrue(r['experiments'][0]['direction_matched']);self.assertEqual(len(r['events']),3)
  with self.assertRaises(ValueError):self.core.complete(self.c,1,self.w,eid,'Cannot complete it twice')
 def test_rejection_and_cancel(self):
  eid=self.create();self.core.decision(self.c,1,self.w,eid,False)
  with self.assertRaises(ValueError):self.core.decision(self.c,1,self.w,eid,True)
  eid2=self.create();self.core.decision(self.c,1,self.w,eid2,True);self.core.cancel(self.c,1,self.w,eid2)
  self.assertEqual(self.core.report(self.c,1,self.w)['summary']['cancelled'],1)
 def test_workspace_isolation(self):
  eid=self.create()
  for fn in (lambda:self.core.report(self.c,2,self.w),lambda:self.core.decision(self.c,2,self.w,eid,True),lambda:self.core.complete(self.c,2,self.w,eid,'Cannot change someone else data')):
   with self.assertRaises(ValueError):fn()
  self.assertEqual(self.core.report(self.c,2,self.other)['experiments'],[])
 def test_validation_and_read_only(self):
  before=self.c.total_changes;self.core.report(self.c,1,self.w);self.assertEqual(before,self.c.total_changes)
  with self.assertRaises(ValueError):self.core.propose(self.c,1,self.w,'goal','Short','tiny','tiny','increase')
  with self.assertRaises(ValueError):self.core.propose(self.c,1,self.w,'goal','Good title','Long enough hypothesis','Long enough human action','sideways')
 def test_html_escape(self):
  eid=self.core.propose(self.c,1,self.w,'goal','<script>alert(1)</script>','Some hypothesis with <script> tags','A safe human-controlled action','increase')
  page=self.core.render(self.c,1,'csrf',self.w)
  self.assertIn('&lt;script&gt;',page);self.assertNotIn('<script>alert(1)</script>',page)
 def test_approval_does_not_modify_business_records(self):
  eid=self.create();before=self.c.execute('SELECT count(*) FROM prime_records').fetchone()[0]
  self.core.decision(self.c,1,self.w,eid,True)
  self.assertEqual(before,self.c.execute('SELECT count(*) FROM prime_records').fetchone()[0])
if __name__=='__main__':unittest.main()
