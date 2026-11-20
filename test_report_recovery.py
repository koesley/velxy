"""Recovery must never delete a committed customer report."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from recover_report_writes import reconcile, main
from unittest.mock import patch


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / 'test.sqlite')
        with self.connect() as c:
            c.execute('CREATE TABLE reports (id TEXT PRIMARY KEY, user_id INTEGER)')
            c.execute('CREATE TABLE report_write_journal (report_id TEXT PRIMARY KEY, user_id INTEGER, created INTEGER, state TEXT)')
            c.executemany('INSERT INTO report_write_journal VALUES (?,?,?,?)', [
                ('orphan', 1, 100, 'pending'),
                ('ready', 1, 100, 'pending'),
                ('recent', 1, 99990, 'pending'),
                ('completed', 1, 100, 'committed'),
            ])
            c.execute("INSERT INTO reports VALUES ('ready',1)")
        self.removed = []

    def connect(self):
        return sqlite3.connect(self.path)

    def remove(self, owner, identifier):
        self.removed.append((owner, identifier))

    def test_apply_requires_explicit_maintenance_authorization(self):
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(SystemExit) as error:
                main(['--apply'])
        self.assertEqual(error.exception.code, 2)

    def test_apply_rejects_weak_maintenance_value(self):
        with patch.dict('os.environ', {'VELXTRIA_REPORT_RECOVERY_MAINTENANCE': 'yes'}):
            with self.assertRaises(SystemExit) as error:
                main(['--apply'])
        self.assertEqual(error.exception.code, 2)

    def test_dry_run_never_deletes(self):
        result = reconcile(self.connect, self.remove, current_time=100000, min_age_seconds=86400)
        self.assertEqual(result['stale'], 2)
        self.assertEqual(self.removed, [])

    def test_apply_deletes_only_stale_orphan(self):
        result = reconcile(self.connect, self.remove, apply=True,
                           current_time=100000, min_age_seconds=86400)
        self.assertEqual(result['cleaned'], 1)
        self.assertEqual(result['protected'], 1)
        self.assertEqual(self.removed, [(1, 'orphan')])
        with self.connect() as c:
            self.assertEqual(c.execute("SELECT state FROM report_write_journal WHERE report_id='orphan'").fetchone()[0], 'cleaned')
            self.assertEqual(c.execute("SELECT state FROM report_write_journal WHERE report_id='ready'").fetchone()[0], 'pending')

    def test_failed_cleanup_keeps_pending_for_retry(self):
        def fail(owner, identifier):
            raise RuntimeError('offline')
        result = reconcile(self.connect, fail, apply=True,
                           current_time=100000, min_age_seconds=86400)
        self.assertEqual(result['failed'], 1)
        with self.connect() as c:
            self.assertEqual(c.execute("SELECT state FROM report_write_journal WHERE report_id='orphan'").fetchone()[0], 'pending')


if __name__ == '__main__':
    unittest.main()
