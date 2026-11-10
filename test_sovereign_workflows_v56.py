import sqlite3,unittest
from unittest.mock import patch
import sovereign_workflows_v56 as wf
class WorkflowTests(unittest.TestCase):
 def setUp(self):self.c=sqlite3.connect(':memory:');self.audit=patch('sovereign_workflows_v56.core.audit').start();self.access=patch('sovereign_workflows_v56.core.access',return_value='owner').start()
 def tearDown(self):patch.stopall();self.c.close()
 def test_lifecycle(self):
  x=wf.create(self.c,1,'one','My workflow','discover');self.assertEqual(len(wf.overview(self.c,1,'one')['workflows']),1)
  wf.update(self.c,1,'one',x,'approve');self.assertEqual(wf.overview(self.c,1,'one')['workflows'][0]['status'],'approved')
  with self.assertRaises(ValueError):wf.update(self.c,1,'one',x,'add','guardian')
  wf.update(self.c,1,'one',x,'review');self.assertEqual(self.c.execute('SELECT count(*) FROM sv56_workflow_reviews').fetchone()[0],1)
 def test_scope(self):
  x=wf.create(self.c,1,'one','First plan','plan');self.assertEqual(wf.overview(self.c,1,'two')['workflows'],[])
  with self.assertRaises(ValueError):wf.update(self.c,1,'two',x,'archive')
 def test_approval_owner_only(self):
  x=wf.create(self.c,1,'one','First plan','monitor');self.access.side_effect=lambda c,u,w,**kw: (_ for _ in ()).throw(ValueError('owner required')) if kw.get('owner') else 'editor'
  with self.assertRaises(ValueError):wf.update(self.c,1,'one',x,'approve')
 def test_input_validation(self):
  with self.assertRaises(ValueError):wf.create(self.c,1,'one','x','discover')
  with self.assertRaises(ValueError):wf.create(self.c,1,'one','good name','bogus')
 def test_escaping(self):
  wf.create(self.c,1,'one','<script>alert(1)</script>','discover');page=wf.render(self.c,1,'one','abc')
  self.assertNotIn('<script>',page);self.assertIn('&lt;script&gt;',page)
 def test_steps(self):
  x=wf.create(self.c,1,'one','First plan','discover');wf.update(self.c,1,'one',x,'remove','approval')
  with self.assertRaises(ValueError):wf.update(self.c,1,'one',x,'approve')
  wf.update(self.c,1,'one',x,'add','approval');wf.update(self.c,1,'one',x,'up','approval');self.assertEqual(wf.overview(self.c,1,'one')['workflows'][0]['steps'][-2]['key'],'approval')
if __name__=='__main__':unittest.main()
