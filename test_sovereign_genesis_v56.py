import unittest
from test_sovereign_future_v56 import FutureTests
import sovereign_genesis_v56 as g
import sovereign_v56 as core

class GenesisTests(FutureTests):
 def setUp(self):
  super().setUp();g.setup(self.c)
 def ready_genesis(self):
  self.load();return g.create_session(self.c,1,self.w)
 def test_discovery_worlds(self):
  self.ready_genesis();r=g.discover(self.c,1,self.w)
  self.assertEqual(len(r['hypotheses']),5)
  self.assertTrue(all(len(x['worlds'])==3 for x in r['hypotheses']))
  self.assertIn('UNVERIFIED',r['hypotheses'][0]['referee'])
 def test_deterministic(self):
  self.ready_genesis();self.assertEqual(g.discover(self.c,1,self.w),g.discover(self.c,1,self.w))
 def test_lifecycle(self):
  sid=self.ready_genesis();eid=g.propose(self.c,1,self.w,sid,'premium')
  self.assertEqual(g.experiments(self.c,1,self.w)[0]['status'],'draft')
  g.update(self.c,1,self.w,eid,'approve')
  with self.assertRaises(ValueError):g.update(self.c,1,self.w,eid,'complete','nan','source')
  with self.assertRaises(ValueError):g.update(self.c,1,self.w,eid,'complete','50','')
  g.update(self.c,1,self.w,eid,'complete','50','Measured in owner-provided CSV; uncontrolled')
  self.assertEqual(g.experiments(self.c,1,self.w)[0]['observed'],50)
  with self.assertRaises(ValueError):g.update(self.c,1,self.w,eid,'approve')
 def test_stale(self):
  sid=self.ready_genesis()
  core.import_csv(self.c,1,self.w,'new.csv',b'period,revenue,expenses,leads,customers\n2026-12,900,400,20,5\n')
  self.assertTrue(g.history(self.c,1,self.w)[0]['stale'])
  with self.assertRaises(ValueError):g.propose(self.c,1,self.w,sid,'premium')
 def test_access(self):
  sid=self.ready_genesis()
  with self.assertRaises(ValueError):g.history(self.c,2,self.w)
  with self.assertRaises(ValueError):g.propose(self.c,2,self.w,sid,'premium')
  eid=g.propose(self.c,1,self.w,sid,'premium')
  with self.assertRaises(ValueError):g.update(self.c,2,self.w,eid,'approve')
 def test_escaping(self):
  self.ready_genesis();page=g.render(self.c,1,'<script>',self.w)
  self.assertIn('&lt;script&gt;',page);self.assertNotIn('<script>',page)
 def test_invalid_hypothesis(self):
  sid=self.ready_genesis()
  with self.assertRaises(ValueError):g.propose(self.c,1,self.w,sid,'__fake__')
 def test_no_data(self):
  with self.assertRaises(ValueError):g.create_session(self.c,1,self.w)

if __name__=='__main__':unittest.main()
