"""Recovery must never delete a committed customer report."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from recover_report_writes import reconcile, main, inspect_stranded, verify_storage_absent
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

    def test_abandon_never_deletes_committed_customer_report(self):
        import portal
        with self.connect() as c:
            c.execute("UPDATE report_write_journal SET state='committed' WHERE report_id='ready'")
        with patch.object(portal, 'db', self.connect), \
             patch.object(portal.persistent, 'remove') as remove:
            self.assertFalse(portal.abandon_report_write(1, 'ready'))
        remove.assert_not_called()

    def test_abandon_never_deletes_when_report_exists_even_if_pending(self):
        import portal
        with patch.object(portal, 'db', self.connect), \
             patch.object(portal.persistent, 'remove') as remove:
            self.assertFalse(portal.abandon_report_write(1, 'ready'))
        remove.assert_not_called()

    def test_apply_without_verifier_fails_before_deletion(self):
        with self.assertRaisesRegex(ValueError, 'requires an object-absence verifier'):
            reconcile(self.connect, self.remove, apply=True,
                      current_time=100000, min_age_seconds=86400)
        self.assertEqual(self.removed, [])

    def test_absence_verification_accepts_only_explicit_missing(self):
        class Missing(FileNotFoundError):
            pass
        def missing(owner, identifier, root):
            raise Missing('not found')
        verify_storage_absent(missing, Missing, 1, 'orphan')
        def unavailable(owner, identifier, root):
            raise RuntimeError('storage unavailable')
        with self.assertRaises(RuntimeError):
            verify_storage_absent(unavailable, Missing, 1, 'orphan')
        with self.assertRaises(RuntimeError):
            verify_storage_absent(lambda *args: b'existing', Missing, 1, 'orphan')

    def test_recovery_does_not_mark_cleaned_when_object_remains(self):
        result = reconcile(self.connect, self.remove, apply=True,
                           current_time=100000, min_age_seconds=86400,
                           verify_absent=lambda owner, identifier: (_ for _ in ()).throw(
                               RuntimeError('object still exists')))
        self.assertEqual(result['failed'], 1)
        self.assertEqual(result['cleaned'], 0)
        with self.connect() as c:
            self.assertEqual(c.execute(
                "SELECT state FROM report_write_journal WHERE report_id='orphan'"
            ).fetchone()[0], 'pending')

    def test_stranded_audit_is_read_only_and_conservative(self):
        with self.connect() as c:
            c.execute("INSERT INTO report_write_journal VALUES ('stranded-present',1,100,'recovering')")
            c.execute("INSERT INTO report_write_journal VALUES ('stranded-unknown',1,100,'recovering')")
            c.execute("INSERT INTO report_write_journal VALUES ('stranded-ready',1,100,'recovering')")
            c.execute("INSERT INTO reports VALUES ('stranded-ready',1)")
        def retrieve(owner, identifier, root):
            if identifier == 'stranded-unknown':
                raise RuntimeError('Storage unreachable, not confirmed missing')
            return b'ZIP'
        result = inspect_stranded(self.connect, retrieve, current_time=100000,
                                  min_age_seconds=86400)
        self.assertEqual(result, {
            'stranded': 3, 'report_present': 1,
            'object_present': 1, 'storage_unverified': 1
        })
        self.assertEqual(self.removed, [])
        with self.connect() as c:
            self.assertEqual(c.execute(
                "SELECT COUNT(*) FROM report_write_journal WHERE state='recovering'"
            ).fetchone()[0], 3)

    def test_stranded_recovery_is_reported_without_deletion(self):
        with self.connect() as c:
            c.execute("INSERT INTO report_write_journal VALUES ('stranded',1,100,'recovering')")
        result = reconcile(self.connect, self.remove, apply=True,
                           current_time=100000, min_age_seconds=86400, verify_absent=lambda *_: None)
        self.assertEqual(result['recovering_needs_review'], 1)
        self.assertNotIn((1, 'stranded'), self.removed)
        with self.connect() as c:
            self.assertEqual(c.execute(
                "SELECT state FROM report_write_journal WHERE report_id='stranded'"
            ).fetchone()[0], 'recovering')

    def test_dry_run_never_deletes(self):
        result = reconcile(self.connect, self.remove, current_time=100000, min_age_seconds=86400)
        self.assertEqual(result['stale'], 2)
        self.assertEqual(self.removed, [])

    def test_apply_deletes_only_stale_orphan(self):
        result = reconcile(self.connect, self.remove, apply=True,
                           current_time=100000, min_age_seconds=86400, verify_absent=lambda *_: None)
        self.assertEqual(result['cleaned'], 1)
        self.assertEqual(result['protected'], 1)
        self.assertEqual(self.removed, [(1, 'orphan')])
        with self.connect() as c:
            self.assertEqual(c.execute("SELECT state FROM report_write_journal WHERE report_id='orphan'").fetchone()[0], 'cleaned')
            self.assertEqual(c.execute("SELECT state FROM report_write_journal WHERE report_id='ready'").fetchone()[0], 'pending')

    def test_recovery_claim_blocks_late_commit(self):
        def competing_remove(owner, identifier):
            with self.connect() as c:
                attempted = c.execute(
                    "UPDATE report_write_journal SET state='committed' "
                    "WHERE report_id=? AND state='pending'", (identifier,)
                )
                self.assertEqual(attempted.rowcount, 0)
            self.removed.append((owner, identifier))
        result = reconcile(self.connect, competing_remove, apply=True,
                           current_time=100000, min_age_seconds=86400, verify_absent=lambda *_: None)
        self.assertEqual(result['cleaned'], 1)
        self.assertEqual(self.removed, [(1, 'orphan')])

    def test_failed_cleanup_keeps_pending_for_retry(self):
        def fail(owner, identifier):
            raise RuntimeError('offline')
        result = reconcile(self.connect, fail, apply=True,
                           current_time=100000, min_age_seconds=86400, verify_absent=lambda *_: None)
        self.assertEqual(result['failed'], 1)
        with self.connect() as c:
            self.assertEqual(c.execute("SELECT state FROM report_write_journal WHERE report_id='orphan'").fetchone()[0], 'pending')


if __name__ == '__main__':
    unittest.main()
