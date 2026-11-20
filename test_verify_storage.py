"""Offline regression tests for private Supabase storage readiness."""
import io
import json
import unittest
from unittest.mock import patch
import urllib.error
import verify_storage


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, limit=-1):
        return json.dumps(self.payload).encode("utf-8")


class StorageProbeTests(unittest.TestCase):
    def probe(self, payload=None, opener=None, **kwargs):
        if opener is None:
            opener = lambda request, timeout: FakeResponse(payload)
        return verify_storage.check(
            url="https://example.supabase.co",
            key="fake-test-key",
            bucket="velxy-reports",
            opener=opener,
            **kwargs,
        )

    def test_private_bucket_connected(self):
        self.assertEqual(self.probe({"id": "velxy-reports", "public": False}), "connected")

    def test_public_bucket_rejected(self):
        self.assertEqual(self.probe({"id": "velxy-reports", "public": True}), "unsafe_public_bucket")

    def test_missing_public_flag_fails_closed(self):
        self.assertEqual(self.probe({"id": "velxy-reports"}), "unsafe_public_bucket")

    def test_wrong_bucket_fails_closed(self):
        self.assertEqual(self.probe({"id": "other", "public": False}), "failed")

    def test_malformed_response_fails_closed(self):
        self.assertEqual(self.probe(["velxy-reports"]), "failed")

    def test_provider_failure_fails_closed(self):
        def fail(request, timeout):
            raise urllib.error.URLError("simulated outage")
        self.assertEqual(self.probe(opener=fail), "failed")

    def test_no_credentials_returns_not_configured(self):
        self.assertEqual(verify_storage.check(url="", key="", bucket="velxy-reports"), "not_configured")

    def test_plain_http_rejected_without_network(self):
        self.assertEqual(verify_storage.check(url="http://example.com", key="fake", bucket="reports"), "failed")

    def test_request_uses_authenticated_bucket_endpoint(self):
        def inspect(request, timeout):
            self.assertEqual(request.full_url, "https://example.supabase.co/storage/v1/bucket/velxy-reports")
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(timeout, 10)
            self.assertEqual(request.get_header("Authorization"), "Bearer fake-test-key")
            return FakeResponse({"name": "velxy-reports", "public": False})
        self.assertEqual(self.probe(opener=inspect), "connected")


if __name__ == "__main__":
    unittest.main()
