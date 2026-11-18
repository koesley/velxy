import unittest
from decimal import Decimal
from revenue_action_evidence import RevenueAction, rank_actions

class RevenueActionEvidenceTests(unittest.TestCase):
    def test_deterministic_order_and_no_verified_revenue(self):
        items = [RevenueAction("b", "retention", 10000, Decimal("0.5")),
                 RevenueAction("a", "lead_followup", 20000, Decimal("0.5"))]
        result = rank_actions(items)
        self.assertEqual([x["source_id"] for x in result], ["a", "b"])
        self.assertTrue(all(x["verified_revenue_cents"] is None for x in result))
        self.assertTrue(all(x["status"] == "proposal" for x in result))

    def test_reject_invalid_confidence(self):
        for bad in ["NaN", "Infinity", "-0.1", "1.1"]:
            with self.assertRaises(ValueError):
                rank_actions([RevenueAction("a", "retention", 100, bad)])

    def test_reject_duplicate_and_bad_amount(self):
        a = RevenueAction("a", "retention", 100, Decimal("0.5"))
        with self.assertRaises(ValueError):
            rank_actions([a, a])
        with self.assertRaises(ValueError):
            rank_actions([RevenueAction("x", "retention", -1, Decimal("0.5"))])

if __name__ == "__main__":
    unittest.main()
