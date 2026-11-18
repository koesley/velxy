import unittest
from unittest.mock import patch
from experiment_decisions_v38 import evaluate,render

class DecisionTests(unittest.TestCase):
    def row(self,name,leads,conversions,spend,status="completed"):
        return dict(name=name,source="Ads",leads=leads,conversions=conversions,
                    spend_cents=spend,status=status,
                    conversion_pct=round(conversions/leads*100,1) if leads else None,
                    cost_per_lead_cents=round(spend/leads) if leads else None)

    @patch("experiment_decisions_v38.campaigns.analyze")
    @patch("experiment_decisions_v38.bos.core.access")
    def test_gates_and_ranking(self,access,analyze):
        analyze.return_value=[self.row("Low",5,1,1000),
                              self.row("Fast",40,10,10000),
                              self.row("Slow",40,10,20000),
                              self.row("Active",40,10,5000,"running"),
                              self.row("No cost",40,10,0)]
        rows=evaluate(None,1,"workspace")
        by_name={r["name"]:r for r in rows}
        self.assertEqual(by_name["Low"]["decision"],"Insufficient evidence")
        self.assertEqual(by_name["Active"]["decision"],"Continue measurement")
        self.assertEqual(by_name["No cost"]["decision"],"Check cost data")
        self.assertEqual(by_name["Fast"]["descriptive_rank"],1)
        self.assertEqual(by_name["Slow"]["descriptive_rank"],2)
        self.assertEqual(by_name["Fast"]["cost_per_conversion_cents"],1000)

    @patch("experiment_decisions_v38.campaigns.analyze",return_value=[])
    @patch("experiment_decisions_v38.bos.core.access")
    def test_empty(self,access,analyze):
        self.assertIn("No campaigns",render(None,1,"workspace"))

    @patch("experiment_decisions_v38.bos.core.access",side_effect=ValueError("Denied"))
    def test_denied(self,access):
        with self.assertRaises(ValueError):evaluate(None,1,"other")

if __name__=="__main__":unittest.main()
