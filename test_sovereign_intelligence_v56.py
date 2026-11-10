import unittest
from test_sovereign_v56 import SovereignTests
import sovereign_intelligence_v56 as council
import sovereign_v56 as base

class CouncilTests(SovereignTests):
 def setUp(self):
  super().setUp();council.setup(self.c)
 def test_evidence_and_agent_routing(self):
  self.load();r=council.evaluate(base.report(self.c,1,self.w),'revenue')
  self.assertEqual(r['agents_used'],['growth','risk','synthesizer'])
  self.assertEqual(r['findings'][0]['evidence']['previous_revenue'],1000)
 def test_council_history_and_staleness(self):
  self.load();rid=council.run(self.c,1,self.w,'overview')
  self.assertEqual(council.history(self.c,1,self.w)[0]['id'],rid)
  self.assertFalse(council.history(self.c,1,self.w)[0]['stale'])
  base.import_csv(self.c,1,self.w,'new.csv',b'period,revenue,expenses,leads,customers\n2026-03,700,600,100,10\n')
  self.assertTrue(council.history(self.c,1,self.w)[0]['stale'])
 def test_tenant_isolation_and_permission(self):
  self.load();council.run(self.c,1,self.w,'costs')
  with self.assertRaises(ValueError):council.history(self.c,2,self.w)
  with self.assertRaises(ValueError):council.run(self.c,2,self.w,'overview')
  self.assertEqual(council.history(self.c,2,self.other),[])
 def test_invalid_objective_no_persist(self):
  with self.assertRaises(ValueError):council.run(self.c,1,self.w,'transfer_money')
  self.assertEqual(council.history(self.c,1,self.w),[])
 def test_no_fabricated_evidence(self):
  r=council.evaluate(base.report(self.c,1,self.w),'overview')
  self.assertTrue(all(f['kind']=='missing_evidence' for f in r['findings'] if f['agent']!='risk'))
 def test_html_escape(self):
  self.load();council.run(self.c,1,self.w,'overview')
  page=council.render(self.c,1,'<script>',self.w)
  self.assertNotIn('<script>',page)
  self.assertIn('&lt;script&gt;',page)
 def test_no_external_actions(self):
  self.load();result=council.evaluate(base.report(self.c,1,self.w),'overview')
  self.assertIn('Observation only',result['execution_policy'])
 def test_conflicting_data_stays_out_of_evidence(self):
  self.load();base.import_csv(self.c,1,self.w,'conflict.csv',b'period,revenue,expenses,leads,customers\n2026-02,900,600,100,9\n')
  result=council.evaluate(base.report(self.c,1,self.w),'overview')
  self.assertTrue(any(f['kind']=='data_quality' for f in result['findings']))

if __name__=='__main__':unittest.main()
