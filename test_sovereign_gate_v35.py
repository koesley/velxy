import unittest,sqlite3,tempfile,time,json
from pathlib import Path
from unittest.mock import patch
import sovereign_gate_v35 as g
import sentinel_v34 as s

class GateTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name)
  self.c=sqlite3.connect(':memory:');self.addCleanup(self.c.close)
  g.setup(self.c)
  self.c.execute('CREATE TABLE evolution_releases(id TEXT,workspace_id TEXT,status TEXT,title TEXT,version_label TEXT,created INTEGER)')
  self.c.execute("INSERT INTO evolution_releases VALUES('r1','w1','testing','Test release','35.0',1)")
  self.report={'schema':1,'run_id':'a'*32,'started':int(time.time())-2,'finished':int(time.time()),'status':'passed','exit_code':0,'tests':['test_foo.py'],'output':'ok','output_truncated':False,'python':'3.11'}
  self.report['sha256']=s._digest(self.report)
  folder=s.evidence_dir(self.root);folder.mkdir();(folder/('a'*32+'.json')).write_text(json.dumps(self.report))
 def test_verified_evidence_and_tamper(self):
  with patch.object(g.empire_v19,'role',return_value='owner'):
   g.attach(self.c,1,'w1','r1','a'*32,self.root)
  self.assertEqual(g.verify_gate(self.c,'w1','r1',self.root)['status'],'passed')
  self.report['output']='tampered'
  (s.evidence_dir(self.root)/('a'*32+'.json')).write_text(json.dumps(self.report))
  with self.assertRaises(ValueError):g.verify_gate(self.c,'w1','r1',self.root)
 def test_workspace_isolation(self):
  with patch.object(g.empire_v19,'role',return_value='owner'):
   with self.assertRaises(ValueError):g.attach(self.c,1,'w2','r1','a'*32,self.root)
  with self.assertRaises(ValueError):g.verify_gate(self.c,'w2','r1',self.root)
 def test_expired_and_failed_rejected(self):
  self.report['finished']-=90000;self.report['sha256']=s._digest({k:v for k,v in self.report.items() if k!='sha256'})
  (s.evidence_dir(self.root)/('a'*32+'.json')).write_text(json.dumps(self.report))
  with self.assertRaises(ValueError):g.evidence(self.root,'a'*32)
 def test_render_escapes(self):
  self.c.execute('CREATE TABLE empire_workspaces(id TEXT,name TEXT,created INTEGER)')
  self.c.execute('CREATE TABLE empire_members(workspace_id TEXT,user_id INTEGER,role TEXT)')
  self.c.execute("INSERT INTO empire_workspaces VALUES('w1','<script>oops</script>',1)")
  self.c.execute("INSERT INTO empire_members VALUES('w1',1,'owner')")
  with patch.object(g.empire_v19,'role',return_value='owner'):
   out=g.render(self.c,1,'token','w1',self.root)
  self.assertNotIn('<script>',out)
  self.assertIn('&lt;script&gt;',out)
if __name__=='__main__':unittest.main()
