import unittest
from strategy_evaluation import evaluate


class StrategyEvaluationTests(unittest.TestCase):
    def test_signals(self):
        self.assertEqual(evaluate(20, 100, 60, 100)['signal'], 'positive')
        self.assertEqual(evaluate(60, 100, 20, 100)['signal'], 'negative')
        self.assertEqual(evaluate(20, 100, 20, 100)['signal'], 'inconclusive')
        self.assertEqual(evaluate(0, 100, 0, 100)['signal'], 'inconclusive')
        self.assertAlmostEqual(evaluate(20, 100, 60, 100)['absolute_lift'], .4)
    def test_insufficient(self):
        self.assertEqual(evaluate(0, 0, 10, 20)['status'], 'insufficient_data')
    def test_invalid(self):
        for counts in [(True, 100, 10, 100), (101, 100, 10, 100), (-1, 100, 10, 100), (1, 1.5, 10, 100)]:
            with self.assertRaises(ValueError):
                evaluate(*counts)
