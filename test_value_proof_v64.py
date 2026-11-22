import unittest
from datetime import datetime, timedelta, timezone
from value_proof_v64 import OutcomeEvidence, build_value_receipt

T = datetime(2026, 1, 1, tzinfo=timezone.utc)

def ev(w, key, kind="recovered_revenue", amount="12.50", verified=True, when=T):
    return OutcomeEvidence(w, key, kind, amount, when, "invoice:"+key, verified)

class ValueProofTests(unittest.TestCase):
    def test_verified_totals_and_tenant_isolation(self):
        r = build_value_receipt([ev("a","1"),ev("b","2","recovered_revenue","999"),
                                 ev("a","3","hours_saved","2.5")], "a", T)
        self.assertEqual(r["verified_totals"]["recovered_revenue"], "12.50")
        self.assertEqual(r["verified_totals"]["hours_saved"], "2.5")
        self.assertEqual(r["verified_evidence_count"], 2)

    def test_unverified_and_future_excluded(self):
        r = build_value_receipt([ev("a","1",verified=False),
                                 ev("a","2",when=T+timedelta(seconds=1))], "a", T)
        self.assertEqual(r["verified_evidence_count"], 0)
        self.assertEqual(r["excluded"], {"unverified":1,"future":1})

    def test_duplicate_fails_closed(self):
        with self.assertRaises(ValueError):
            build_value_receipt([ev("a","1"),ev("a","1")], "a", T)

    def test_invalid_values_rejected(self):
        for amount in ("NaN", "Infinity", "-1", "0", "invalid"):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                build_value_receipt([ev("a","1",amount=amount)], "a", T)

    def test_timezone_required(self):
        with self.assertRaises(ValueError):
            build_value_receipt([ev("a","1")], "a", datetime(2026,1,1))

    def test_missing_source_rejected(self):
        with self.assertRaises(ValueError):
            build_value_receipt([OutcomeEvidence("a","1","hours_saved","2",T,"",True)],"a",T)

if __name__ == "__main__":
    unittest.main()
