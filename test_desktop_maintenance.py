import sqlite3,tempfile,unittest
from pathlib import Path
from desktop_maintenance import backup,diagnose
class MaintenanceTests(unittest.TestCase):
 def test_backup_and_integrity(self):
  with tempfile.TemporaryDirectory() as d:
   db=Path(d)/'portal.sqlite3'
   with sqlite3.connect(db) as c:
    c.execute('create table sample (name text)');c.execute('insert into sample values (?)',('hello',))
   out=backup(d)
   with sqlite3.connect(out) as c:self.assertEqual(c.execute('select name from sample').fetchone()[0],'hello')
   self.assertEqual(diagnose(d)['database_integrity'],'ok')
 def test_missing_database(self):
  with tempfile.TemporaryDirectory() as d:
   self.assertFalse(diagnose(d)['database_exists'])
   with self.assertRaises(FileNotFoundError):backup(d)
 def test_retention(self):
  with tempfile.TemporaryDirectory() as d:
   with sqlite3.connect(Path(d)/'portal.sqlite3') as c:c.execute('create table t (x integer)')
   for _ in range(4):backup(d,keep=2)
   self.assertEqual(len(list((Path(d)/'Backups').glob('*.sqlite3'))),2)
if __name__=='__main__':unittest.main()
