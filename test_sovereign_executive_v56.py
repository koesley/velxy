import unittest
from test_sovereign_future_v56 import FutureTests
import sovereign_executive_v56 as executive
import sovereign_v56 as core

class ExecutiveTests(FutureTests):
 def setUp(self):
  super().setUp();executive.setup(self.c)
 def test_review_history_and_stale(self):
  self.load();rid=executive.run(self.c,1,self.w,'overview');h=executive.history(self.c,1,self.w)
  self.assertEqual(h[0]['id'],rid);self.assertFalse(h[0]['stale']);self.assertEqual(len(h[0]['result']['specialists']),4)
  core.import_csv(self.c,1,self.w,'changed.csv',b'period,revenue,expenses,leads,customers\n2026-05,1000,500,20,5\n')
  self.assertTrue(executive.history(self.c,1,self.w)[0]['stale'])
 def test_no_evidence(self):
  r=executive.evaluate({'facts':[],'conflicting_periods':[],'opportunities':[]},'overview',None)
  self.assertEqual(r['verdict'],'INSUFFICIENT_EVIDENCE');self.assertFalse(r['recommendations'])
 def test_conflict_blocks(self):
  r=executive.evaluate({'facts':[],'conflicting_periods':['2026-01'],'opportunities':[]},'overview','2026-01')
  self.assertEqual(r['verdict'],'BLOCKED_DATA_QUALITY');self.assertTrue(r['critic_objections'])
 def test_cross_workspace(self):
  self.load()
  with self.assertRaises(ValueError):executive.run(self.c,2,self.w,'overview')
  with self.assertRaises(ValueError):executive.history(self.c,2,self.w)
 def test_invalid_objective(self):
  self.load()
  with self.assertRaises(ValueError):executive.run(self.c,1,self.w,'other')
 def test_viewer_cannot_run(self):
  self.load();self.c.execute('INSERT INTO empire_members VALUES(?,?,?)',(self.w,3,'viewer'))
  with self.assertRaises(ValueError):executive.run(self.c,3,self.w,'overview')
 def test_escaped_dashboard(self):
  self.load();self.assertIn('&lt;script&gt;',executive.render(self.c,1,'<script>',self.w))

if __name__=='__main__':unittest.main()
