import sqlite3, unittest
from unittest.mock import patch
import sovereign_workflows_v56 as wf
import sovereign_workflow_runtime_v56 as rt
class RuntimeTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.role='owner'
  def access(c,u,w,write=False,owner=False):
   if w not in ('a','b'):raise ValueError('unauthorized')
   if owner and self.role!='owner':raise ValueError('owner required')
   if write and self.role=='viewer':raise ValueError('write forbidden')
   return self.role
  self.a=patch.object(wf.core,'access',side_effect=access);self.b=patch.object(wf.core,'audit');self.a.start();self.b.start()
  self.wid=wf.create(self.c,1,'a','Operational pathway','monitor');wf.update(self.c,1,'a',self.wid,'approve')
 def tearDown(self):self.a.stop();self.b.stop();self.c.close()
 def run_id(self):return rt.start(self.c,1,'a',self.wid)
 def test_approved_only(self):
  draft=wf.create(self.c,1,'a','Draft pathway','monitor')
  with self.assertRaises(ValueError):rt.start(self.c,1,'a',draft)
 def test_scoped(self):
  rid=self.run_id();self.assertEqual(rt.overview(self.c,1,'b')['runs'],[])
  with self.assertRaises(ValueError):rt.change(self.c,1,'b',rid,'pause')
 def test_sequential_and_approval(self):
  rid=self.run_id();tasks=rt.overview(self.c,1,'a')['runs'][0]['tasks']
  with self.assertRaises(ValueError):rt.change(self.c,1,'a',rid,'done',tasks[1]['id'])
  rt.change(self.c,1,'a',rid,'done',tasks[0]['id'])
  self.role='editor'
  for t in tasks[1:]:
   if t['key']=='approval':
    with self.assertRaises(ValueError):rt.change(self.c,1,'a',rid,'done',t['id'],'reason')
    self.role='owner'
    with self.assertRaises(ValueError):rt.change(self.c,1,'a',rid,'done',t['id'])
   rt.change(self.c,1,'a',rid,'done',t['id'],'approved after review')
  rt.change(self.c,1,'a',rid,'complete')
  self.assertEqual(rt.overview(self.c,1,'a')['runs'][0]['status'],'completed')
 def test_pause_resume_block(self):
  rid=self.run_id();task=rt.overview(self.c,1,'a')['runs'][0]['tasks'][0]['id']
  rt.change(self.c,1,'a',rid,'blocked',task,'Need data');rt.change(self.c,1,'a',rid,'pause')
  with self.assertRaises(ValueError):rt.change(self.c,1,'a',rid,'done',task)
  rt.change(self.c,1,'a',rid,'resume');rt.change(self.c,1,'a',rid,'reset',task)
  with self.assertRaises(ValueError):rt.change(self.c,1,'a',rid,'complete')
 def test_viewer(self):
  self.role='viewer'
  with self.assertRaises(ValueError):self.run_id()
 def test_escaped(self):
  rid=self.run_id();task=rt.overview(self.c,1,'a')['runs'][0]['tasks'][0]['id'];rt.change(self.c,1,'a',rid,'blocked',task,'<script>alert(1)</script>')
  page=rt.render(self.c,1,'a','csrf');self.assertNotIn('<script>',page);self.assertIn('&lt;script&gt;',page)
 def test_cancel(self):
  rid=self.run_id();rt.change(self.c,1,'a',rid,'cancel')
  with self.assertRaises(ValueError):rt.change(self.c,1,'a',rid,'resume')
if __name__=='__main__':unittest.main()
