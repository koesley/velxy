"""Regression tests for one-time, thread-safe schema initialization.

Extract the production functions via AST to avoid importing the entire portal
and its optional integration dependencies in this focused offline test.
"""
import ast
import os
import pathlib
import tempfile
import threading
import unittest
from unittest.mock import patch


def load_functions():
    source = pathlib.Path(__file__).with_name('portal.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name in ('db', '_initialize_schema')]
    assert len(selected) == 2, 'Production schema initializer missing'
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    return compile(module, 'portal.py', 'exec')


class FakeConnection:
    def __init__(self):
        self.closed = False
    def close(self):
        self.closed = True


class SchemaLifecycleTests(unittest.TestCase):
    def make_environment(self, initializer):
        connections = []
        def connect(_):
            c = FakeConnection()
            connections.append(c)
            return c
        env = {
            'Lock': threading.Lock,
            '_SCHEMA_LOCK': threading.Lock(),
            '_SCHEMA_READY': False,
            'persistent': type('Persistent', (), {'connect': staticmethod(connect)}),
            'DB': 'unused',
        }
        exec(load_functions(), env)
        env['_initialize_schema'] = initializer
        return env, connections

    def test_postgres_schema_lock_precedes_table_creation(self):
        """Protect the cross-instance lock ordering in the real initializer."""
        tree = ast.parse(pathlib.Path(__file__).with_name('portal.py').read_text(encoding='utf-8'))
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == '_initialize_schema')
        # ast.walk is breadth-first, so a nested call (the advisory lock,
        # inside `if persistent.REMOTE:`) sorts after the top-level calls
        # even though it comes first in the source. Sort by line number so
        # the order tested is the order the code actually runs in.
        statements = sorted(
            (node for node in ast.walk(function)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and node.func.attr == 'execute'),
            key=lambda node: node.lineno)
        sql = [node.args[0].value for node in statements
               if node.args and isinstance(node.args[0], ast.Constant)
               and isinstance(node.args[0].value, str)]
        self.assertTrue(sql)
        self.assertIn('pg_advisory_xact_lock', sql[0])
        self.assertTrue(any('CREATE TABLE' in statement for statement in sql[1:]))

    def test_multiple_requests_initialize_once(self):
        calls = []
        env, connections = self.make_environment(lambda c: calls.append(c))
        self.assertIsNot(env['db'](), env['db']())
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(connections), 2)

    def test_failure_closes_connection_and_allows_retry(self):
        attempts = []
        def initialize(c):
            attempts.append(c)
            if len(attempts) == 1:
                raise RuntimeError('simulated setup failure')
        env, connections = self.make_environment(initialize)
        with self.assertRaises(RuntimeError):
            env['db']()
        self.assertTrue(connections[0].closed)
        self.assertFalse(env['_SCHEMA_READY'])
        env['db']()
        self.assertEqual(len(attempts), 2)
        self.assertTrue(env['_SCHEMA_READY'])

    def test_parallel_requests_initialize_once(self):
        calls = []
        calls_lock = threading.Lock()
        def initialize(c):
            with calls_lock:
                calls.append(c)
        env, _ = self.make_environment(initialize)
        errors = []
        def request():
            try:
                env['db']()
            except Exception as exc:
                errors.append(exc)
        threads = [threading.Thread(target=request) for _ in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        self.assertFalse(errors)
        self.assertEqual(len(calls), 1)


# The AST tests above cover the once-per-process flag in isolation. The
# tests below cover it against the real database: the flag must not survive
# the database file being replaced mid-process.
_TMP = None
_ENV = None


def setUpModule():
    global _TMP, _ENV
    _TMP = tempfile.TemporaryDirectory()
    _ENV = patch.dict(os.environ, {
        'VELXTRIA_DATA_DIR': _TMP.name,
        'VELXTRIA_DEPLOYMENT_MODE': 'local',
        'VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT': '0',
    })
    _ENV.start()
    import portal  # noqa: F401  (imported for its module-level DATA_ROOT)
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


def tearDownModule():
    import portal
    with portal.db() as c:
        c.execute(
            'DELETE FROM sessions WHERE user_id IN '
            "(SELECT id FROM users WHERE email LIKE 'recovery%@example.test')")
        c.execute(
            "DELETE FROM users WHERE email LIKE 'recovery%@example.test'")
    _ENV.stop()
    _TMP.cleanup()
    portal.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    portal.REPORTS.mkdir(parents=True, exist_ok=True)


class SchemaRecoveryTests(unittest.TestCase):
    def test_schema_recreated_after_database_file_deleted(self):
        import portal
        with portal.db() as c:
            c.execute(
                'INSERT INTO users(email,salt,pw_hash,created) VALUES (?,?,?,?)',
                ('recovery@example.test', 's', 'h', portal.now()))
        # Simulate a test module deleting its temp data dir (and the sqlite
        # file with it) between modules: the file is gone, but the process
        # flag still says the schema is ready.
        portal.DB.unlink(missing_ok=True)
        self.assertTrue(portal._SCHEMA_READY)
        with portal.db() as c:
            row = c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
            ).fetchone()
            self.assertIsNotNone(row, 'users table was not re-created')
            c.execute(
                'INSERT INTO users(email,salt,pw_hash,created) VALUES (?,?,?,?)',
                ('recovery2@example.test', 's', 'h', portal.now()))


if __name__ == '__main__':
    unittest.main()
