"""Offline regression tests for the read-only private storage probe."""
import io
import json
import unittest
from unittest.mock import patch
import verify_storage


class FakeResponse:
    def __init__(self, metadata):
        self.data = json.dumps(metadata).encode()
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, n=-1): return self.data[:n]


class StorageProbeTests(unittest.TestCase):
    def test_missing_configuration(self):
        self.assertEqual(verify_storage.check(url='', key='', bucket='reports'), 'not_configured')

    def test_http_is_rejected_without_request(self):
        self.assertEqual(verify_storage.check(url='http://example.test', key='key', bucket='reports'), 'failed')

    def test_private_bucket_connected(self):
        calls = []
        def opener(req, timeout):
            calls.append((req.full_url, req.get_method(), timeout))
            return FakeResponse({'id': 'private-reports', 'public': False})
        self.assertEqual(verify_storage.check(url='https://example.supabase.co', key='secret',
                                              bucket='private-reports', opener=opener), 'connected')
        self.assertEqual(calls, [('https://example.supabase.co/storage/v1/bucket/private-reports', 'GET', 10)])

    def test_public_bucket_rejected(self):
        self.assertEqual(verify_storage.check(
            url='https://example.supabase.co', key='secret', bucket='reports',
            opener=lambda req, timeout: FakeResponse({'id': 'reports', 'public': True})
        ), 'unsafe_public_bucket')

    def test_wrong_bucket_rejected(self):
        self.assertEqual(verify_storage.check(
            url='https://example.supabase.co', key='secret', bucket='reports',
            opener=lambda req, timeout: FakeResponse({'id': 'other', 'public': False})
        ), 'failed')

    def test_unreachable_storage_rejected(self):
        def offline(req, timeout):
            raise OSError('offline')
        self.assertEqual(verify_storage.check(url='https://example.supabase.co', key='secret',
                                              bucket='reports', opener=offline), 'failed')


if __name__ == '__main__':
    unittest.main()
