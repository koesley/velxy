import sqlite3,unittest
from unittest.mock import patch
import sovereign_business_graph_v57 as g
class GraphTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.access=patch('sovereign_v56.access',return_value='owner').start();self.audit=patch('sovereign_v56.audit').start()
 def tearDown(self):patch.stopall();self.c.close()
 def add(self,w='a',name='Product'):
  return g.node(self.c,1,w,'product',name,'Test description','reported','Manual test')
 def test_nodes_edges_and_insights(self):
  a=self.add();b=self.add(name='Service');e=g.edge(self.c,1,'a',a,b,'depends_on','Dependency')
  d=g.overview(self.c,1,'a');self.assertEqual(d['counts']['relationships'],1);self.assertEqual(d['counts']['unconnected'],0)
  g.archive(self.c,1,'a','node',a);self.assertEqual(g.overview(self.c,1,'a')['counts']['relationships'],0)
 def test_tenant_separation(self):
  a=self.add();b=self.add('b','Other')
  with self.assertRaises(ValueError):g.edge(self.c,1,'a',a,b,'depends_on','Cross tenant')
  self.assertEqual(g.overview(self.c,1,'b')['counts']['nodes'],1)
 def test_validation_and_duplicate(self):
  a=self.add();b=self.add(name='Second')
  g.edge(self.c,1,'a',a,b,'uses','Relationship')
  with self.assertRaises(ValueError):g.edge(self.c,1,'a',a,b,'uses','Duplicate')
  with self.assertRaises(ValueError):g.node(self.c,1,'a','invalid','x','d','reported','source')
 def test_escape(self):
  self.add(name='<script>alert(1)</script>')
  self.assertNotIn('<script>',g.render(self.c,1,'a','csrf'))
 def test_write_permissions(self):
  self.access.side_effect=lambda c,u,w,**kw: (_ for _ in ()).throw(ValueError('no access')) if kw.get('write') else 'viewer'
  with self.assertRaises(ValueError):self.add()
  self.assertEqual(g.overview(self.c,1,'a')['role'],'viewer')
if __name__=='__main__':unittest.main()
