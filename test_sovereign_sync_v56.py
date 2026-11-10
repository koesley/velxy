import unittest
from test_sovereign_twin_v56 import TwinTests
import sovereign_sync_v56 as sync
import sovereign_twin_v56 as twin
import sovereign_v56 as core

class SyncTests(TwinTests):
 def setUp(self):
  super().setUp();sync.setup(self.c)
 def test_preview_and_apply(self):
  iid=self.load();p=sync.preview(self.c,1,self.w)
  self.assertEqual(len(p['to_create']),2)
  self.assertEqual(sync.apply(self.c,1,self.w)['created'],2)
  g=twin.graph(self.c,1,self.w)
  self.assertEqual([n['kind'] for n in g['nodes']],['metric_period','metric_period'])
  self.assertTrue(all(n['source']=='sv56_import:'+iid for n in g['nodes']))
 def test_idempotent(self):
  self.load();sync.apply(self.c,1,self.w)
  self.assertEqual(sync.apply(self.c,1,self.w)['created'],0)
  self.assertEqual(len(sync.status(self.c,1,self.w)['links']),2)
 def test_conflicting_period_excluded(self):
  self.load();core.import_csv(self.c,1,self.w,'extra.csv',b'period,revenue,expenses,leads,customers\n2026-02,900,500,100,20\n')
  p=sync.preview(self.c,1,self.w);self.assertEqual([x['period'] for x in p['conflicts']],['2026-02'])
  self.assertEqual(sync.apply(self.c,1,self.w)['created'],1)
 def test_existing_source_change_requires_review(self):
  self.load();sync.apply(self.c,1,self.w)
  core.import_csv(self.c,1,self.w,'extra.csv',b'period,revenue,expenses,leads,customers\n2026-01,900,500,100,20\n')
  self.assertEqual(len(sync.preview(self.c,1,self.w)['conflicts']),1)
  self.assertEqual(sync.apply(self.c,1,self.w)['created'],0)
 def test_cross_workspace(self):
  self.load()
  with self.assertRaises(ValueError):sync.preview(self.c,2,self.w)
  with self.assertRaises(ValueError):sync.apply(self.c,2,self.w)
  self.assertEqual(sync.status(self.c,2,self.other)['links'],[])
 def test_viewer_read_only(self):
  self.c.execute('INSERT INTO empire_members VALUES(?,?,?)',(self.w,3,'viewer'))
  self.load();self.assertEqual(len(sync.preview(self.c,3,self.w)['to_create']),2)
  with self.assertRaises(ValueError):sync.apply(self.c,3,self.w)
 def test_html_escape(self):
  self.load();page=sync.render(self.c,1,'<script>',self.w)
  self.assertIn('&lt;script&gt;',page);self.assertNotIn('<script>',page)

if __name__=='__main__':unittest.main()
