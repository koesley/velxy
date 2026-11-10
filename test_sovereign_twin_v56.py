import unittest
from test_sovereign_intelligence_v56 import CouncilTests
import sovereign_twin_v56 as twin

class TwinTests(CouncilTests):
 def setUp(self):
  super().setUp();twin.setup(self.c)
 def test_nodes_edges_and_traversal(self):
  a=twin.add_node(self.c,1,self.w,'company','Alpha','owner')
  b=twin.add_node(self.c,1,self.w,'product','Widget','catalog')
  twin.add_edge(self.c,1,self.w,a,b,'offers','owner')
  self.assertEqual(len(twin.traverse(self.c,1,self.w,a)['nodes']),2)
  self.assertEqual(len(twin.graph(self.c,1,self.w)['edges']),1)
 def test_tenant_boundary(self):
  a=twin.add_node(self.c,1,self.w,'company','Alpha','owner')
  b=twin.add_node(self.c,2,self.other,'product','Other','owner')
  with self.assertRaises(ValueError):twin.add_edge(self.c,1,self.w,a,b,'offers','owner')
  with self.assertRaises(ValueError):twin.graph(self.c,2,self.w)
  with self.assertRaises(ValueError):twin.reconcile(self.c,2,self.w,a,1,'Stolen','owner')
 def test_invalid_relation(self):
  a=twin.add_node(self.c,1,self.w,'company','Alpha','owner');b=twin.add_node(self.c,1,self.w,'goal','Goal','owner')
  with self.assertRaises(ValueError):twin.add_edge(self.c,1,self.w,a,b,'offers','owner')
 def test_conflict_and_revision(self):
  a=twin.add_node(self.c,1,self.w,'company','Alpha','owner')
  with self.assertRaises(ValueError):twin.add_node(self.c,1,self.w,'company','Alpha','owner')
  twin.reconcile(self.c,1,self.w,a,1,'New Alpha','reviewed')
  with self.assertRaises(ValueError):twin.reconcile(self.c,1,self.w,a,1,'Old','owner')
  self.assertEqual(twin.graph(self.c,1,self.w)['nodes'][0]['revision'],2)
 def test_viewer_cannot_modify(self):
  self.c.execute('INSERT INTO empire_members VALUES(?,?,?)',(self.w,3,'viewer'))
  with self.assertRaises(ValueError):twin.add_node(self.c,3,self.w,'company','X','owner')
 def test_xss_encoded(self):
  twin.add_node(self.c,1,self.w,'company','<script>','owner')
  page=twin.render(self.c,1,'<script>',self.w)
  self.assertNotIn('<script>',page);self.assertIn('&lt;script&gt;',page)
 def test_source_required(self):
  with self.assertRaises(ValueError):twin.add_node(self.c,1,self.w,'company','Alpha','')
 def test_no_cross_tenant_traversal(self):
  a=twin.add_node(self.c,1,self.w,'company','Alpha','owner')
  with self.assertRaises(ValueError):twin.traverse(self.c,2,self.other,a)

if __name__=='__main__':unittest.main()
