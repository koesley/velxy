import unittest
from decimal import Decimal
from revenue_priority import RevenueOpportunity, rank_opportunities


class RevenuePriorityTests(unittest.TestCase):
    def candidate(self, **changes):
        values = dict(identifier="a", title="Recover abandoned leads",
                      estimated_value=Decimal("1200"), confidence=0.8,
                      urgency=0.9, effort_hours=2, evidence="12 uncontacted leads")
        values.update(changes)
        return RevenueOpportunity(**values)

    def test_ordering_and_explanation(self):
        ranked = rank_opportunities([self.candidate(identifier="b", urgency=0.1),
                                     self.candidate()])
        self.assertEqual(ranked[0]["identifier"], "a")
        self.assertTrue(ranked[0]["requires_approval"])
        self.assertIn("not guaranteed", ranked[0]["explanation"])

    def test_rejects_invalid_inputs(self):
        for changes in ({"confidence": 1.5}, {"urgency": -1},
                        {"effort_hours": -2}, {"estimated_value": "NaN"},
                        {"evidence": ""}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    rank_opportunities([self.candidate(**changes)])

    def test_duplicate_identifier(self):
        with self.assertRaises(ValueError):
            rank_opportunities([self.candidate(), self.candidate()])

    def test_empty(self):
        self.assertEqual(rank_opportunities([]), [])


if __name__ == "__main__":
    unittest.main()
