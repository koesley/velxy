import unittest
from test_sovereign_executive_v56 import ExecutiveTests
import sovereign_connectors_v56 as connector

CSV=b'external_id,period,revenue,expenses,leads,customers\na,2026-01,100,50,10,2\n'
class ConnectorTests(ExecutiveTests):
 def setUp(self):
  super().setUp();connector.setup(self.c)
 def test_register_stage_approve_history(self):
  sid=connector.create_source(self.c,1,self.w,'Store export')
  p=connector.preview(self.c,1,self.w,sid,CSV)
  self.assertEqual(p['new_ids'],['a'])
  bid=connector.ingest(self.c,1,self.w,sid,'store.csv',CSV)
  self.assertEqual(connector.history(self.c,1,self.w)['batches'][0]['status'],'staged')
  self.assertEqual(connector.apply(self.c,1,self.w,bid)['status'],'applied')
  self.assertEqual(connector.preview(self.c,1,self.w,sid,CSV)['unchanged_ids'],['a'])
  with self.assertRaises(ValueError):connector.ingest(self.c,1,self.w,sid,'store.csv',CSV)
  with self.assertRaises(ValueError):connector.apply(self.c,1,self.w,bid)
 def test_conflicts_block(self):
  sid=connector.create_source(self.c,1,self.w,'Store export')
  connector.apply(self.c,1,self.w,connector.ingest(self.c,1,self.w,sid,'a.csv',CSV))
  changed=CSV.replace(b'100,50',b'200,50')
  bid=connector.ingest(self.c,1,self.w,sid,'b.csv',changed)
  self.assertEqual(len(connector.preview(self.c,1,self.w,sid,changed)['conflicts']),1)
  with self.assertRaises(ValueError):connector.apply(self.c,1,self.w,bid)
 def test_permissions_and_scope(self):
  sid=connector.create_source(self.c,1,self.w,'Store export')
  with self.assertRaises(ValueError):connector.history(self.c,2,self.w)
  with self.assertRaises(ValueError):connector.ingest(self.c,2,self.w,sid,'a.csv',CSV)
  self.c.execute('INSERT INTO empire_members VALUES(?,?,?)',(self.w,3,'viewer'))
  with self.assertRaises(ValueError):connector.create_source(self.c,3,self.w,'No write')
  bid=connector.ingest(self.c,1,self.w,sid,'a.csv',CSV)
  with self.assertRaises(ValueError):connector.apply(self.c,3,self.w,bid)
 def test_invalid_inputs(self):
  sid=connector.create_source(self.c,1,self.w,'Store export')
  for data in [b'',CSV.replace(b'2026-01',b'2026-13'),CSV.replace(b'100,50',b'nan,50'),CSV+CSV.splitlines()[1]+b'\n',CSV.replace(b'10,2',b'1,2')]:
   with self.assertRaises(ValueError):connector.ingest(self.c,1,self.w,sid,'bad.csv',data)
 def test_dashboard_escaping(self):
  connector.create_source(self.c,1,self.w,'<script>alert(1)</script>')
  page=connector.render(self.c,1,'<csrf>',self.w)
  self.assertIn('&lt;script&gt;',page);self.assertNotIn('<script>',page)
if __name__=='__main__':unittest.main()
