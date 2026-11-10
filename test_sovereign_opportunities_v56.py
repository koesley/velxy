import unittest
from test_sovereign_sync_v56 import SyncTests
import sovereign_opportunities_v56 as opp
import sovereign_sync_v56 as sync
import sovereign_v56 as core

class OpportunityTests(SyncTests):
 def setUp(self):
  super().setUp();opp.setup(self.c)
 def test_requires_reconciled_sources(self):
  self.load();result,_=opp.snapshot(self.c,1,self.w)
  self.assertEqual(result['opportunities'],[])
  self.assertEqual(len(result['excluded_unlinked_periods']),2)
 def test_discovery_after_sync(self):
  self.load();sync.apply(self.c,1,self.w)
  result,_=opp.snapshot(self.c,1,self.w)
  self.assertEqual(result['excluded_unlinked_periods'],[])
  self.assertTrue(all(x['execution']=='none' for x in result['opportunities']))
 def test_history_stale_on_new_import(self):
  self.load();sync.apply(self.c,1,self.w);opp.run(self.c,1,self.w)
  self.assertFalse(opp.history(self.c,1,self.w)[0]['stale'])
  core.import_csv(self.c,1,self.w,'later.csv',b'period,revenue,expenses,leads,customers\n2026-03,200,100,20,5\n')
  self.assertTrue(opp.history(self.c,1,self.w)[0]['stale'])
 def test_cross_tenant(self):
  self.load()
  with self.assertRaises(ValueError):opp.run(self.c,2,self.w)
  with self.assertRaises(ValueError):opp.history(self.c,2,self.w)
 def test_viewer_cannot_run(self):
  self.c.execute('INSERT INTO empire_members VALUES(?,?,?)',(self.w,3,'viewer'))
  self.load();self.assertEqual(opp.history(self.c,3,self.w),[])
  with self.assertRaises(ValueError):opp.run(self.c,3,self.w)
 def test_conflict_excluded(self):
  self.load();sync.apply(self.c,1,self.w)
  core.import_csv(self.c,1,self.w,'conflict.csv',b'period,revenue,expenses,leads,customers\n2026-02,800,500,100,10\n')
  result,_=opp.snapshot(self.c,1,self.w)
  self.assertIn('2026-02',result['conflicting_periods'])
  self.assertEqual(result['opportunities'],[])
 def test_html_escaping(self):
  self.load();opp.run(self.c,1,self.w)
  page=opp.render(self.c,1,'<script>',self.w)
  self.assertIn('&lt;script&gt;',page);self.assertNotIn('<script>',page)

if __name__=='__main__':unittest.main()
