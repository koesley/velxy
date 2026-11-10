import sqlite3,unittest
from unittest.mock import patch
import sovereign_council_v57 as m
import sovereign_business_graph_v57 as g
class CouncilTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.a=patch('sovereign_v56.access',return_value='owner').start();self.b=patch('sovereign_v56.audit').start()
  self.n=g.node(self.c,1,'a','product','Widget','Widget description','reported','Manual')
 def tearDown(self):patch.stopall();self.c.close()
 def test_lifecycle(self):
  i=m.create(self.c,1,'a',self.n,'What could go wrong?');m.generate(self.c,1,'a',i);m.generate(self.c,1,'a',i)
  self.assertEqual(len(m.overview(self.c,1,'a')['investigations'][0]['notes']),4)
  m.note(self.c,1,'a',i,'finance','evidence','Revenue changed','Spreadsheet reference')
  m.review(self.c,1,'a',i,'needs_evidence','More proof required')
  self.assertEqual(m.overview(self.c,1,'a')['counts']['needs_evidence'],1)
  with self.assertRaises(ValueError):m.note(self.c,1,'a',i,'risk','hypothesis','test','test')
 def test_cross_workspace(self):
  i=m.create(self.c,1,'a',self.n,'Question?')
  with self.assertRaises(ValueError):m.generate(self.c,1,'b',i)
  with self.assertRaises(ValueError):m.review(self.c,1,'b',i,'accepted','reason')
  self.assertEqual(m.overview(self.c,1,'b')['counts']['total'],0)
 def test_permission(self):
  i=m.create(self.c,1,'a',self.n,'Question?')
  self.a.side_effect=lambda c,u,w,**kw: (_ for _ in ()).throw(ValueError('denied')) if kw.get('owner') else 'editor'
  with self.assertRaises(ValueError):m.review(self.c,1,'a',i,'accepted','reason')
 def test_validation_escape(self):
  with self.assertRaises(ValueError):m.create(self.c,1,'a','missing','Question?')
  i=m.create(self.c,1,'a',self.n,'<script>alert(1)</script>')
  self.assertNotIn('<script>',m.render(self.c,1,'a','token'))
  with self.assertRaises(ValueError):m.note(self.c,1,'a',i,'other','evidence','a','b')
if __name__=='__main__':unittest.main()
