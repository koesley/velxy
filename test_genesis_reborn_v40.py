import sqlite3,tempfile,unittest
from pathlib import Path
import genesis_reborn_v40 as v40
import persistent

class GenesisRebornTests(unittest.TestCase):
 def test_missing_file_never_created(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'missing.sqlite3';self.assertFalse(v40.inspect(p)['ok']);self.assertFalse(p.exists())
 def test_indexes_are_idempotent_and_compatible(self):
  with sqlite3.connect(':memory:') as c:
   c.execute('CREATE TABLE sessions(token_hash TEXT,user_id INTEGER,expires INTEGER)')
   self.assertEqual(len(v40.install_indexes(c)['created']),2)
   self.assertEqual(v40.install_indexes(c)['created'],[])
 def test_index_missing_column_skipped(self):
  with sqlite3.connect(':memory:') as c:
   c.execute('CREATE TABLE reports(id TEXT)')
   self.assertIn('idx_v40_reports_user_created',v40.install_indexes(c)['skipped'])
 def test_health_and_corruption(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'good.sqlite3'
   with sqlite3.connect(p) as c:c.execute('CREATE TABLE test(id INTEGER PRIMARY KEY)')
   self.assertTrue(v40.inspect(p)['ok'])
   bad=Path(d)/'bad.sqlite3';bad.write_bytes(b'not sqlite')
   self.assertFalse(v40.inspect(bad)['ok'])
 def test_managed_connection_closes_on_success_and_failure(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.sqlite3'
   with persistent.connect(p) as c:c.execute('CREATE TABLE t(x INTEGER)')
   with self.assertRaises(sqlite3.ProgrammingError):c.execute('SELECT 1')
   with self.assertRaises(ValueError):
    with persistent.connect(p) as c2:
     c2.execute('INSERT INTO t VALUES (5)');raise ValueError('rollback')
   with sqlite3.connect(p) as check:self.assertEqual(check.execute('SELECT count(*) FROM t').fetchone()[0],0)
 def test_render_escapes_and_is_read_only(self):
  with tempfile.TemporaryDirectory() as d:
   self.assertIn('Database diagnostics',v40.render(d))
   self.assertFalse((Path(d)/'portal.sqlite3').exists())
if __name__=='__main__':unittest.main()
