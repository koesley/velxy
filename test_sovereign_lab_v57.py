import sqlite3,unittest
from unittest.mock import patch
import sovereign_lab_v57 as m
import sovereign_business_graph_v57 as g
import sovereign_council_v57 as council
class LabTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.a=patch('sovereign_v56.access',return_value='owner').start();self.b=patch('sovereign_v56.audit').start()
  node=g.node(self.c,1,'a','product','Widget','Description','reported','Spreadsheet');self.i=council.create(self.c,1,'a',node,'Can we improve retention?')
 def tearDown(self):patch.stopall();self.c.close()
 def make(self):return m.plan(self.c,1,'a',self.i,'Retention scenario','Monthly revenue',100,'USD',30,'Hypothesis only')
 def test_lifecycle(self):
  p=self.make();m.option(self.c,1,'a',p,'Offer discount',10,20,15)
  d=m.overview(self.c,1,'a');self.assertEqual(d['plans'][0]['options'][0]['projected'],110)
  m.review(self.c,1,'a',p,'approved','Reviewed assumptions');m.measure(self.c,1,'a',p,120,'Internal dashboard, unverified')
  self.assertEqual(m.overview(self.c,1,'a')['plans'][0]['measurements'][0]['delta_pct'],20)
  with self.assertRaises(ValueError):m.option(self.c,1,'a',p,'Too late',1,0,0)
 def test_cross_workspace(self):
  p=self.make()
  with self.assertRaises(ValueError):m.option(self.c,1,'b',p,'No',1,0,0)
  with self.assertRaises(ValueError):m.review(self.c,1,'b',p,'approved','No')
  self.assertEqual(m.overview(self.c,1,'b')['counts']['plans'],0)
 def test_permission(self):
  p=self.make();m.option(self.c,1,'a',p,'A',2,0,0)
  self.a.side_effect=lambda c,u,w,**kw: (_ for _ in ()).throw(ValueError('denied')) if kw.get('owner') else 'editor'
  with self.assertRaises(ValueError):m.review(self.c,1,'a',p,'approved','No')
 def test_validation_and_escape(self):
  with self.assertRaises(ValueError):m.plan(self.c,1,'a',self.i,'A','B','nan','USD',30,'x')
  p=m.plan(self.c,1,'a',self.i,'<script>','Revenue',0,'USD',30,'Assumptions')
  self.assertNotIn('<script>',m.render(self.c,1,'a','token'))
  with self.assertRaises(ValueError):m.option(self.c,1,'a',p,'Bad',1001,0,0)
  with self.assertRaises(ValueError):m.review(self.c,1,'a',p,'approved','No option')
 def test_zero_baseline(self):
  p=m.plan(self.c,1,'a',self.i,'Zero','Revenue',0,'USD',30,'Unknown');m.option(self.c,1,'a',p,'A',20,0,0);m.review(self.c,1,'a',p,'approved','Approved');m.measure(self.c,1,'a',p,10,'Manual evidence')
  self.assertIsNone(m.overview(self.c,1,'a')['plans'][0]['measurements'][0]['delta_pct'])
if __name__=='__main__':unittest.main()
