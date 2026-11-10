"""V42 tenant isolation, deterministic reporting and export safety."""
import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

class InfinityEngineTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'VELXTRIA_DATA_DIR':self.tmp.name,'VELXTRIA_LOCAL_STUDIO':'1','VELXTRIA_DEPLOYMENT_MODE':'local'});self.env.start()
  import portal,empire_v19,infinity_engine_v42 as v42
  self.portal=portal;self.empire=empire_v19;self.v42=v42;self.old=portal.DB;portal.DB=Path(self.tmp.name)/'portal.sqlite3'
  self.c=portal.db();self.c.execute("INSERT INTO users(id,email,salt,pw_hash,role,access,created) VALUES(1,'one@example.test','a','b','customer','demo',0),(2,'two@example.test','a','b','customer','demo',0)")
  self.w1=self.empire.create(self.c,1,'Alpha <script>');self.w2=self.empire.create(self.c,2,'Secret');self.c.commit()
 def tearDown(self):
  self.c.close();self.portal.DB=self.old;self.env.stop();self.tmp.cleanup()
 def test_empty_and_read_only(self):
  before=self.c.total_changes;r=self.v42.report(self.c,1,self.w1)
  self.assertEqual(r['workspace_id'],self.w1);self.assertEqual(r['apps'],[]);self.assertEqual(before,self.c.total_changes)
 def test_cross_workspace_rejected(self):
  with self.assertRaises(ValueError):self.v42.report(self.c,1,self.w2)
  with self.assertRaises(ValueError):self.v42.render(self.c,1,self.w2)
 def test_escaping_and_export(self):
  html=self.v42.render(self.c,1,self.w1)
  self.assertIn('Alpha &lt;script&gt;',html);self.assertNotIn('Alpha <script>',html)
  self.assertEqual(json.loads(json.dumps(self.v42.report(self.c,1,self.w1)))['workspace_id'],self.w1)
 def test_number_safety(self):
  for value in ('nan','inf',float('inf'),True,object(),None):self.assertIsNone(self.v42.safe_number(value))
  self.assertEqual(self.v42.safe_number('12.5'),12.5)
 def test_app_scope_and_numeric_statistics(self):
  # Insert data using the existing application schema.
  from genesis_prime_v20 import setup
  schema=json.dumps([{'name':'revenue','type':'number'}])
  self.c.execute('INSERT INTO prime_apps(id,workspace_id,name,schema_json,status,version,created_by,created) VALUES(?,?,?,?,?,?,?,?)',('app1',self.w1,'Sales <bad>',schema,'published',1,1,1))
  self.c.execute('INSERT INTO prime_apps(id,workspace_id,name,schema_json,status,version,created_by,created) VALUES(?,?,?,?,?,?,?,?)',('app2',self.w2,'Private',schema,'published',1,2,1))
  for i,x in enumerate((10,20,30,40)):
   self.c.execute('INSERT INTO prime_records(id,workspace_id,app_id,data_json,created_by,created) VALUES(?,?,?,?,?,?)',(str(i),self.w1,'app1',json.dumps({'revenue':x}),1,i))
  r=self.v42.report(self.c,1,self.w1)
  self.assertEqual(len(r['apps']),1);self.assertEqual(r['apps'][0]['numeric']['revenue']['average'],25)
  self.assertEqual(r['apps'][0]['numeric']['revenue']['recent_minus_older'],20)
  self.assertNotIn('Private',json.dumps(r))
if __name__=='__main__':unittest.main()
