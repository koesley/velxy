import os
import unittest
from unittest.mock import patch
import btcpay_production as prod


class ProductionBTCPayTests(unittest.TestCase):
    def test_rejects_testnet(self):
        with patch.dict(os.environ, {"VELXTRIA_BTCPAY_PROD_URL": "https://testnet.demo.btcpayserver.org"}):
            self.assertFalse(prod.configured())

    def test_rejects_insecure_and_local_origins(self):
        for url in ("http://payments.example.com", "https://localhost",
                    "https://127.0.0.1", "https://10.0.0.1",
                    "https://payments.example.com:8443",
                    "https://user:pass@payments.example.com"):
            with self.subTest(url=url), patch.dict(os.environ, {"VELXTRIA_BTCPAY_PROD_URL": url}):
                self.assertFalse(prod.configured())

    def test_requires_credentials(self):
        with patch.dict(os.environ, {"VELXTRIA_BTCPAY_PROD_URL": "https://payments.example.com",
                                     "VELXTRIA_BTCPAY_PROD_API_KEY": "",
                                     "VELXTRIA_BTCPAY_PROD_STORE_ID": ""}):
            self.assertFalse(prod.configured())

    def test_verified_settlement_requires_provider_confirmation(self):
        valid = {"id": "inv-1", "metadata": {"orderId": "order-1"},
                 "status": "Settled", "amount": "49.00", "currency": "USD"}
        with patch.object(prod, "api_request", return_value=valid):
            self.assertTrue(prod.verified_settlement("inv-1", "order-1"))
        for changed in ({"status": "Processing"}, {"amount": "0.01"},
                        {"currency": "BTC"}, {"id": "another"},
                        {"metadata": {"orderId": "someone-else"}}):
            with self.subTest(changed=changed), patch.object(prod, "api_request", return_value={**valid, **changed}):
                self.assertFalse(prod.verified_settlement("inv-1", "order-1"))

    def test_invoice_checkout_is_restricted_to_configured_host(self):
        env = {"VELXTRIA_BTCPAY_PROD_URL": "https://payments.example.com"}
        good = {"id": "invoice1", "checkoutLink": "https://payments.example.com/i/invoice1"}
        with patch.dict(os.environ, env), patch.object(prod, "api_request", return_value=good):
            self.assertEqual(prod.issue_invoice("vx-prod-order1"), ("invoice1", good["checkoutLink"]))
        for link in ("https://evil.example/i/invoice1",
                     "http://payments.example.com/i/invoice1",
                     "https://payments.example.com.evil.example/i/invoice1",
                     "https://payments.example.com/account"):
            with self.subTest(link=link), patch.dict(os.environ, env), patch.object(prod, "api_request", return_value={"id": "invoice1", "checkoutLink": link}):
                with self.assertRaises(RuntimeError):
                    prod.issue_invoice("vx-prod-order1")

    def test_invoice_requires_production_order(self):
        with self.assertRaises(ValueError):
            prod.issue_invoice("vx-test-order1")

    def test_no_empty_identifiers(self):
        with patch.object(prod, "api_request") as request:
            self.assertFalse(prod.verified_settlement("", "order"))
            self.assertFalse(prod.verified_settlement("invoice", ""))
            request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
