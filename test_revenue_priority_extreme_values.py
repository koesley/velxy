import math
import unittest
from decimal import Decimal
from revenue_priority import RevenueOpportunity, rank_opportunities


class ExtremeValueTests(unittest.TestCase):
    def score(self, value, confidence):
        item = RevenueOpportunity('id', 'Lead', Decimal(value), confidence, 0.5, 1.0, 'Entered value')
        return rank_opportunities([item])[0]['priority_score']

    def test_extreme_values_are_bounded(self):
        self.assertEqual(self.score('1e1000000', 1.0), self.score('1000000000', 1.0))
        self.assertEqual(self.score('1e1000000', 0.0), 0)
        self.assertEqual(self.score('1e-1000000', 1.0), 0)
        self.assertEqual(self.score('1e1000000', 5e-324), self.score('1000000000', 1.0))
        self.assertTrue(math.isfinite(self.score('1250.50', 0.5)))
        self.assertEqual(self.score('1250.50', 0.5), round(math.log1p(625.25) / 2, 4))
