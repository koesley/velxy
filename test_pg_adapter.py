"""PostgreSQL wrapper contract tests without requiring live credentials."""
import unittest
from unittest.mock import patch
import persistent


class FakeCursor:
    def __init__(self, rows, rowcount):
        self.rows = rows
        self.rowcount = rowcount
    def fetchone(self):
        return self.rows[0] if self.rows else None
    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self):
        self.statements = []
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0
        self.affected = 1
    def execute(self, sql, args=()):
        self.statements.append((sql, args))
        return FakeCursor([(1,)], self.affected)
    def commit(self):
        self.commits += 1
    def rollback(self):
        self.rollbacks += 1
    def close(self):
        self.closes += 1


class PostgreSQLAdapterTests(unittest.TestCase):
    def make_adapter(self):
        # Avoid psycopg import and any real network connection.
        adapter = persistent.PgConnection.__new__(persistent.PgConnection)
        adapter.conn = FakeConnection()
        adapter.cursor = None
        return adapter

    def test_rowcount_before_execute(self):
        adapter = self.make_adapter()
        self.assertEqual(adapter.rowcount, -1)

    def test_rowcount_after_guarded_update(self):
        adapter = self.make_adapter()
        result = adapter.execute('UPDATE reports SET status=? WHERE id=?', ('ready', 'report-1'))
        self.assertIs(result, adapter)
        self.assertEqual(result.rowcount, 1)
        self.assertEqual(adapter.conn.statements[-1], (
            'UPDATE reports SET status=%s WHERE id=%s', ('ready', 'report-1')))

    def test_zero_rows_affected(self):
        adapter = self.make_adapter()
        adapter.conn.affected = 0
        self.assertEqual(adapter.execute('DELETE FROM reports WHERE id=?', ('missing',)).rowcount, 0)

    def test_fetch_contract(self):
        adapter = self.make_adapter()
        self.assertEqual(adapter.execute('SELECT ?', (1,)).fetchone(), (1,))
        self.assertEqual(adapter.fetchall(), [(1,)])

    def test_success_commits_and_closes(self):
        adapter = self.make_adapter()
        with adapter as conn:
            conn.execute('SELECT 1')
        self.assertEqual((adapter.conn.commits, adapter.conn.rollbacks, adapter.conn.closes), (1, 0, 1))

    def test_failure_rolls_back_and_closes(self):
        adapter = self.make_adapter()
        with self.assertRaises(ValueError):
            with adapter:
                raise ValueError('test failure')
        self.assertEqual((adapter.conn.commits, adapter.conn.rollbacks, adapter.conn.closes), (0, 1, 1))


if __name__ == '__main__':
    unittest.main()
