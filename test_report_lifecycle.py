"""Offline tests for the opt-in synthetic storage lifecycle check."""
import unittest
from unittest.mock import patch
import verify_report_lifecycle as lifecycle


class FakeStorage:
    def __init__(self, corrupt=False, fail=False):
        self.objects = {}
        self.corrupt = corrupt
        self.fail = fail

    def store(self, owner, identifier, payload, reports):
        if self.fail:
            raise OSError('write failed')
        self.objects[(owner, identifier)] = payload

    def retrieve(self, owner, identifier, reports):
        value = self.objects[(owner, identifier)]
        return value + b'corruption' if self.corrupt else value


class ReportLifecycleTests(unittest.TestCase):
    def test_requires_opt_in(self):
        self.assertEqual(lifecycle.main([]), 2)

    def test_missing_configuration(self):
        with patch('persistent.REMOTE', False):
            self.assertEqual(lifecycle.verify(storage=FakeStorage()), 'not_configured')

    def test_successful_round_trip_and_cleanup(self):
        with patch('persistent.REMOTE', True), patch('persistent.URL', 'https://example.supabase.co'), \
             patch('persistent.KEY', 'test-key'), patch.object(lifecycle, 'remove_probe_object') as remove:
            storage = FakeStorage()
            self.assertEqual(lifecycle.verify(storage=storage, identifier='synthetic'), 'connected')
            self.assertEqual(len(storage.objects), 1)
            remove.assert_called_once()

    def test_corrupted_round_trip_fails(self):
        with patch('persistent.REMOTE', True), patch('persistent.URL', 'https://example.supabase.co'), \
             patch('persistent.KEY', 'test-key'), patch.object(lifecycle, 'remove_probe_object'):
            self.assertEqual(lifecycle.verify(storage=FakeStorage(corrupt=True), identifier='synthetic'),
                             'integrity_failed')

    def test_cleanup_failure_fails_even_after_successful_round_trip(self):
        with patch('persistent.REMOTE', True), patch('persistent.URL', 'https://example.supabase.co'), \
             patch('persistent.KEY', 'test-key'), patch.object(lifecycle, 'remove_probe_object', side_effect=OSError):
            self.assertEqual(lifecycle.verify(storage=FakeStorage(), identifier='synthetic'),
                             'cleanup_failed')


if __name__ == '__main__':
    unittest.main()
