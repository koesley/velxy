import unittest
from test_sovereign_opportunities_v56 import OpportunityTests
import sovereign_strategy_v56 as strategy
import sovereign_sync_v56 as sync
import sovereign_v56 as core

class StrategyTests(OpportunityTests):
 def setUp(self):
  super().setUp();strategy.setup(self.c)
 def ready(self):
  self.load();sync.apply(self.c,1,self.w)
  return strategy.snapshot(self.c,1,self.w,'revenue_decline:2026-02')
 def test_three_scenarios_and_ranking(self):
  r,_=self.ready();self.assertEqual(len(r['scenarios']),3);self.assertEqual(len(r['illustrative_ranking']),3)
  self.assertEqual(r['execution'],'none');self.assertTrue(all(x['not_a_forecast'] for x in r['scenarios']))
 def test_arithmetic_and_downside(self):
  r,_=self.ready()
  for s in r['scenarios']:
   self.assertAlmostEqual(s['hypothetical']['margin'],round(s['hypothetical']['revenue']-s['hypothetical']['expenses'],2))
   self.assertLess(s['downside']['margin'],s['hypothetical']['margin'])
 def test_determinism(self):
  a,h=self.ready();b,k=strategy.snapshot(self.c,1,self.w,'revenue_decline:2026-02')
  self.assertEqual(a,b);self.assertEqual(h,k)
 def test_history_and_staleness(self):
  self.ready();strategy.run(self.c,1,self.w,'revenue_decline:2026-02')
  self.assertFalse(strategy.history(self.c,1,self.w)[0]['stale'])
  core.import_csv(self.c,1,self.w,'later.csv',b'period,revenue,expenses,leads,customers\n2026-03,200,100,20,5\n')
  self.assertTrue(strategy.history(self.c,1,self.w)[0]['stale'])
 def test_conflict_blocks_new_run(self):
  self.ready();core.import_csv(self.c,1,self.w,'conflict.csv',b'period,revenue,expenses,leads,customers\n2026-02,800,500,100,10\n')
  with self.assertRaises(ValueError):strategy.run(self.c,1,self.w,'revenue_decline:2026-02')
 def test_unknown_opportunity(self):
  self.ready()
  with self.assertRaises(ValueError):strategy.run(self.c,1,self.w,'not-real')
 def test_cross_tenant(self):
  self.ready()
  with self.assertRaises(ValueError):strategy.run(self.c,2,self.w,'revenue_decline:2026-02')
  with self.assertRaises(ValueError):strategy.history(self.c,2,self.w)
 def test_viewer_cannot_run(self):
  self.ready();self.c.execute('INSERT INTO empire_members VALUES(?,?,?)',(self.w,3,'viewer'))
  with self.assertRaises(ValueError):strategy.run(self.c,3,self.w,'revenue_decline:2026-02')
 def test_html_escaped(self):
  self.ready();page=strategy.render(self.c,1,'<script>',self.w)
  self.assertIn('&lt;script&gt;',page);self.assertNotIn('<script>',page)
 def test_invalid_numeric_input(self):
  for value in (float('nan'),float('inf'),-1):
   with self.assertRaises(ValueError):strategy.simulate(value,100,strategy.TEMPLATES['revenue_decline'][0])
 def test_no_execution_records(self):
  self.ready();strategy.run(self.c,1,self.w,'revenue_decline:2026-02')
  self.assertEqual(core.report(self.c,1,self.w)['actions'],[])

if __name__=='__main__':unittest.main()
