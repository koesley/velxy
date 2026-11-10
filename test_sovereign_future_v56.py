import unittest
from test_sovereign_strategy_v56 import StrategyTests
import sovereign_future_v56 as future
import sovereign_v56 as core

class FutureTests(StrategyTests):
 def setUp(self):
  super().setUp();future.setup(self.c)
 def ready_future(self):
  self.load()
  return future.preview(self.c,1,self.w,'6','1','2','10','1000')
 def test_six_months_and_source(self):
  r,_=self.ready_future();self.assertEqual(len(r['months']),6);self.assertTrue(r['not_a_forecast']);self.assertIn('source_import_id',r['baseline'])
 def test_cash_arithmetic(self):
  r,_=self.ready_future();prior=1000
  for m in r['months']:
   self.assertAlmostEqual(m['ending_cash'],round(prior+m['net_cash_flow'],2),places=2);prior=m['ending_cash']
 def test_repeatable(self):
  a,h=self.ready_future();b,k=future.preview(self.c,1,self.w,'6','1','2','10','1000');self.assertEqual((a,h),(b,k))
 def test_history_and_stale(self):
  self.ready_future();future.run(self.c,1,self.w,'6','1','2','10','1000');self.assertFalse(future.history(self.c,1,self.w)[0]['stale'])
  core.import_csv(self.c,1,self.w,'new.csv',b'period,revenue,expenses,leads,customers\n2026-04,900,400,20,5\n');self.assertTrue(future.history(self.c,1,self.w)[0]['stale'])
 def test_reject_invalid(self):
  self.ready_future()
  for x in ('0','37','1.5','nan','-1'):
   with self.assertRaises(ValueError):future.preview(self.c,1,self.w,x,'0','0','0','0')
  for x in ('nan','inf','-60','60'):
   with self.assertRaises(ValueError):future.preview(self.c,1,self.w,'6',x,'0','0','0')
 def test_isolation(self):
  self.ready_future()
  with self.assertRaises(ValueError):future.run(self.c,2,self.w,'6','0','0','0','0')
  with self.assertRaises(ValueError):future.history(self.c,2,self.w)
 def test_viewer_read_only(self):
  self.ready_future();self.c.execute('INSERT INTO empire_members VALUES(?,?,?)',(self.w,3,'viewer'))
  with self.assertRaises(ValueError):future.run(self.c,3,self.w,'6','0','0','0','0')
 def test_conflict_rejected(self):
  self.ready_future();latest=future.evidence(self.c,1,self.w)[0]['period'];core.import_csv(self.c,1,self.w,'overlap.csv',('period,revenue,expenses,leads,customers\n'+latest+',100,200,20,5\n').encode())
  with self.assertRaises(ValueError):future.preview(self.c,1,self.w,'6','0','0','0','0')
 def test_html_escape(self):
  self.ready_future();page=future.render(self.c,1,'<script>',self.w);self.assertIn('&lt;script&gt;',page);self.assertNotIn('<script>',page)
 def test_shortfall(self):
  r=future.calculate({'revenue':0,'expenses':100,'period':'2026-01','source_import_id':'x'},future.validated('3','0','0','0','0'))
  self.assertEqual(r['first_shortfall_month'],1)

if __name__=='__main__':unittest.main()
