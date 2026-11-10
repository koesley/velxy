import unittest
from test_sovereign_execution_v56 import ExecutionTests
import sovereign_memory_v56 as mem
import sovereign_execution_v56 as ex

class MemoryTests(ExecutionTests):
 def setUp(self):
  super().setUp();mem.setup(self.c)
 def completed(self):
  j=self.job();ex.change(self.c,1,self.w,j,'approve');ex.change(self.c,1,self.w,j,'queue');ex.dispatch_one(self.c,1,self.w);return j
 def test_record_search_and_timeline(self):
  j=self.completed();mid=mem.record(self.c,1,self.w,'outcome','Customer review','Follow-up done','mixed',job_id=j)
  self.assertEqual(mem.history(self.c,1,self.w,'Customer')[0]['id'],mid)
  self.assertEqual(mem.timeline(self.c,1,self.w)['entries'][0]['job_id'],j)
 def test_outcome_requires_successful_job(self):
  j=self.job()
  with self.assertRaises(ValueError):mem.record(self.c,1,self.w,'outcome','Result','Unverified','positive',job_id=j)
 def test_outcome_requires_job(self):
  with self.assertRaises(ValueError):mem.record(self.c,1,self.w,'outcome','Result','Missing','positive')
 def test_cross_workspace_reference(self):
  j=self.completed()
  with self.assertRaises(ValueError):mem.record(self.c,2,self.w,'outcome','Result','No','positive',job_id=j)
 def test_viewer_read_only(self):
  mem.record(self.c,1,self.w,'lesson','Note','Remember this')
  self.c.execute('INSERT INTO empire_members VALUES(?,?,?)',(self.w,3,'viewer'))
  self.assertEqual(len(mem.history(self.c,3,self.w)),1)
  with self.assertRaises(ValueError):mem.record(self.c,3,self.w,'lesson','Note','No writing')
 def test_supersession_immutable(self):
  a=mem.record(self.c,1,self.w,'lesson','Old','Old description')
  b=mem.record(self.c,1,self.w,'lesson','New','Corrected description',supersedes_id=a)
  self.assertEqual([m['id'] for m in mem.history(self.c,1,self.w)],[b])
  self.assertEqual(len(mem.history(self.c,1,self.w,include_superseded=True)),2)
  with self.assertRaises(ValueError):mem.record(self.c,1,self.w,'lesson','Third','No second correction',supersedes_id=a)
 def test_search_wildcards_literal(self):
  mem.record(self.c,1,self.w,'lesson','100% plan','Revenue')
  mem.record(self.c,1,self.w,'lesson','Ordinary plan','Revenue')
  self.assertEqual(len(mem.history(self.c,1,self.w,'%')),1)
 def test_invalid_inputs(self):
  for kind,title,body in [('bad','A','B'),('lesson','','B'),('lesson','A','')]:
   with self.assertRaises(ValueError):mem.record(self.c,1,self.w,kind,title,body)
  with self.assertRaises(ValueError):mem.record(self.c,1,self.w,'lesson','A','B','positive')
 def test_render_escape(self):
  mem.record(self.c,1,self.w,'lesson','<script>','<b>')
  page=mem.render(self.c,1,'<script>',self.w)
  self.assertNotIn('<script>',page);self.assertIn('&lt;script&gt;',page)
 def test_audit(self):
  mid=mem.record(self.c,1,self.w,'decision','Decision','Wait')
  self.assertEqual(self.c.execute('SELECT event FROM sv56_memory_events WHERE entry_id=?',(mid,)).fetchone()[0],'created')

if __name__=='__main__':unittest.main()
