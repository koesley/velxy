import sqlite3
import unittest
from unittest.mock import patch
import sovereign_unified_v56 as unified

class UnifiedTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:')
  self.c.execute('CREATE TABLE sv56_genesis_sessions(id TEXT,workspace_id TEXT)')
  self.c.execute('CREATE TABLE sv56_guardian_alerts(id TEXT,workspace_id TEXT)')
  self.c.execute("INSERT INTO sv56_genesis_sessions VALUES('a','mine')")
  self.c.execute("INSERT INTO sv56_genesis_sessions VALUES('b','other')")
 def tearDown(self):self.c.close()
 @patch('sovereign_unified_v56.core.access',return_value='viewer')
 def test_scope(self,access):
  x=unified.overview(self.c,1,'mine')
  self.assertEqual(next(m for m in x['modules'] if m['name']=='Project Genesis')['count'],1)
  self.assertEqual(next(m for m in x['modules'] if m['name']=='Business Guardian')['count'],0)
  self.assertTrue(x['read_only']);access.assert_called_once_with(self.c,1,'mine')
 @patch('sovereign_unified_v56.core.access',side_effect=ValueError('forbidden'))
 def test_reject_nonmember(self,_):
  with self.assertRaises(ValueError):unified.overview(self.c,2,'other')
 @patch('sovereign_unified_v56.core.access',return_value='owner')
 def test_escape(self,_):
  output=unified.render(self.c,1,'"><script>alert(1)</script>')
  self.assertNotIn('<script>',output)
  self.assertIn('&lt;script&gt;',output)
 @patch('sovereign_unified_v56.core.access',return_value='owner')
 def test_empty_module_counter(self,_):
  self.assertIsNone(next(m for m in unified.overview(self.c,1,'mine')['modules'] if m['name']=='Ask VELXTRIA')['count'])
if __name__=='__main__':unittest.main()

class UnifiedPlusTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:')
  self.c.execute('CREATE TABLE sv56_connector_batches(id TEXT,workspace_id TEXT)')
  self.c.execute('CREATE TABLE sv56_exec_jobs(id TEXT,workspace_id TEXT)')
  self.c.execute("INSERT INTO sv56_connector_batches VALUES('a','one')")
  self.c.execute("INSERT INTO sv56_exec_jobs VALUES('a','two')")
 def tearDown(self):self.c.close()
 @patch('sovereign_unified_v56.core.access',return_value='viewer')
 def test_priority_workspace_isolation(self,_):
  a=unified.overview(self.c,1,'one');b=unified.overview(self.c,1,'two')
  self.assertEqual(a['summary']['recorded_items'],1)
  self.assertEqual(b['summary']['recorded_items'],1)
  self.assertNotIn('Connect approved business data',[x['title'] for x in a['priorities']])
  self.assertIn('Connect approved business data',[x['title'] for x in b['priorities']])
  self.assertNotIn('Inspect approved execution jobs',[x['title'] for x in a['priorities']])
  self.assertIn('Inspect approved execution jobs',[x['title'] for x in b['priorities']])
 @patch('sovereign_unified_v56.core.access',return_value='owner')
 def test_search_markup_and_escaping(self,_):
  output=unified.render(self.c,1,'<svg/onload=alert(1)>')
  self.assertIn('id="unified-search"',output)
  self.assertIn('Suggested next steps',output)
  self.assertNotIn('<svg/onload',output)
 @patch('sovereign_unified_v56.core.access',return_value='viewer')
 def test_priority_links_workspace_scoped(self,_):
  d=unified.overview(self.c,1,'two')
  self.assertTrue(all('w=two' in x['path'] for x in d['priorities']))
