import unittest
from test_sovereign_strategy_v56 import StrategyTests
import sovereign_execution_v56 as ex
import sovereign_strategy_v56 as strategy
import sovereign_sync_v56 as sync
import sovereign_v56 as core

class ExecutionTests(StrategyTests):
 def setUp(self):
  super().setUp();ex.setup(self.c)
 def seeded(self):
  self.load();sync.apply(self.c,1,self.w)
  sid=strategy.run(self.c,1,self.w,'revenue_decline:2026-02')
  return sid
 def job(self,key='unique-job-0001'):
  sid=self.seeded();return ex.propose(self.c,1,self.w,sid,'retention_review',key)
 def test_approval_queue_and_internal_task(self):
  j=self.job();ex.change(self.c,1,self.w,j,'approve');ex.change(self.c,1,self.w,j,'queue')
  self.assertEqual(ex.dispatch_one(self.c,1,self.w),j)
  h=ex.history(self.c,1,self.w);self.assertEqual(h['jobs'][0]['status'],'succeeded');self.assertEqual(len(h['tasks']),1)
  self.assertEqual(ex.dispatch_one(self.c,1,self.w),None)
  self.assertEqual(len(ex.history(self.c,1,self.w)['tasks']),1)
 def test_idempotent_proposal(self):
  j=self.job();sid=ex.history(self.c,1,self.w)['jobs'][0]['strategy_id']
  self.assertEqual(ex.propose(self.c,1,self.w,sid,'retention_review','unique-job-0001'),j)
  self.assertEqual(len(ex.history(self.c,1,self.w)['jobs']),1)
 def test_no_unapproved_execution(self):
  self.job();self.assertIsNone(ex.dispatch_one(self.c,1,self.w));self.assertEqual(ex.history(self.c,1,self.w)['tasks'],[])
 def test_pause_blocks_queue_and_dispatch(self):
  j=self.job();ex.change(self.c,1,self.w,j,'approve');ex.change(self.c,1,self.w,j,'queue');ex.set_pause(self.c,1,self.w,True)
  with self.assertRaises(ValueError):ex.dispatch_one(self.c,1,self.w)
  ex.set_pause(self.c,1,self.w,False);self.assertEqual(ex.dispatch_one(self.c,1,self.w),j)
 def test_invalid_transitions(self):
  j=self.job()
  with self.assertRaises(ValueError):ex.change(self.c,1,self.w,j,'queue')
  ex.change(self.c,1,self.w,j,'reject')
  with self.assertRaises(ValueError):ex.change(self.c,1,self.w,j,'approve')
 def test_stale_strategy_rejected(self):
  sid=self.seeded();core.import_csv(self.c,1,self.w,'later.csv',b'period,revenue,expenses,leads,customers\n2026-03,200,100,20,5\n')
  with self.assertRaises(ValueError):ex.propose(self.c,1,self.w,sid,'retention_review','unique-job-0002')
 def test_expiry(self):
  j=self.job();self.c.execute('UPDATE sv56_exec_jobs SET expires=0 WHERE id=?',(j,))
  with self.assertRaises(ValueError):ex.change(self.c,1,self.w,j,'approve')
 def test_cross_tenant(self):
  j=self.job()
  with self.assertRaises(ValueError):ex.history(self.c,2,self.w)
  with self.assertRaises(ValueError):ex.change(self.c,2,self.w,j,'approve')
 def test_viewer_restricted(self):
  j=self.job();self.c.execute('INSERT INTO empire_members VALUES(?,?,?)',(self.w,3,'viewer'))
  self.assertEqual(len(ex.history(self.c,3,self.w)['jobs']),1)
  with self.assertRaises(ValueError):ex.change(self.c,3,self.w,j,'approve')
  with self.assertRaises(ValueError):ex.set_pause(self.c,3,self.w,True)
 def test_editor_cannot_approve(self):
  j=self.job();self.c.execute('INSERT INTO empire_members VALUES(?,?,?)',(self.w,4,'editor'))
  with self.assertRaises(ValueError):ex.change(self.c,4,self.w,j,'approve')
 def test_audit_and_no_external(self):
  j=self.job();ex.change(self.c,1,self.w,j,'approve');ex.change(self.c,1,self.w,j,'queue');ex.dispatch_one(self.c,1,self.w)
  h=ex.history(self.c,1,self.w)
  self.assertEqual([e['event'] for e in h['events']][:2],['succeeded','running']);self.assertFalse(h['external_execution'])
 def test_invalid_key_and_scenario(self):
  sid=self.seeded()
  with self.assertRaises(ValueError):ex.propose(self.c,1,self.w,sid,'retention_review','short')
  with self.assertRaises(ValueError):ex.propose(self.c,1,self.w,sid,'unknown','unique-job-0003')
 def test_render_escapes(self):
  self.job();page=ex.render(self.c,1,'<script>',self.w)
  self.assertIn('&lt;script&gt;',page);self.assertNotIn('<script>',page)

if __name__=='__main__':unittest.main()
