"""Regression tests for one-time, thread-safe schema initialization.

Extract the production functions via AST to avoid importing the entire portal
and its optional integration dependencies in this focused offline test.
"""
import ast
import pathlib
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


if __name__ == '__main__':
    unittest.main()
