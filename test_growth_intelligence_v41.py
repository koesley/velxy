import unittest
from unittest.mock import patch
from growth_intelligence_v41 import analyze,render

CHANNELS=[{"source":"Referral","leads":10,"won_leads":3,"cost_cents":10000,"reported_cents":12000},
          {"source":"Unspecified","leads":2,"won_leads":0,"cost_cents":0,"reported_cents":0}]
CAMPAIGNS=[{"name":"Spring","spend_cents":5000,"status":"completed"}]
DECISIONS=[{"name":"Spring","decision":"Ready for human review","reason":"Screen passed","meets_data_threshold":True}]
IMPACTS=[{"proposal":"Change A","snapshot_id":"s1","percentage_point_change":5.0},
         {"proposal":"Change B","snapshot_id":None,"percentage_point_change":None}]
class GrowthTests(unittest.TestCase):
    @patch("growth_intelligence_v41.outcomes.snapshot",return_value={"records":2})
    @patch("growth_intelligence_v41.impact.analyze",return_value=IMPACTS)
    @patch("growth_intelligence_v41.decisions.evaluate",return_value=DECISIONS)
    @patch("growth_intelligence_v41.campaigns.analyze",return_value=CAMPAIGNS)
    @patch("growth_intelligence_v41.acquisition.analyze",return_value=CHANNELS)
    @patch("growth_intelligence_v41.bos.core.access")
    def test_totals_and_nonduplicated_spend(self,access,a,b,d,i,o):
        result=analyze(None,7,"one")
        self.assertEqual(result["lead_count"],12)
        self.assertEqual(result["acquisition_spend_cents"],10000)
        self.assertEqual(result["campaign_spend_cents"],5000)
        self.assertEqual(result["reported_payment_cents"],12000)
        self.assertEqual(result["followup_snapshots"],1)
        self.assertEqual(result["pending_followups"],1)
        self.assertTrue(any("unspecified" in x for x in result["flags"]))
        access.assert_called_with(None,7,"one")
        self.assertIn("potential overlap",render(None,7,"one"))

    @patch("growth_intelligence_v41.outcomes.snapshot",return_value={})
    @patch("growth_intelligence_v41.impact.analyze",return_value=[])
    @patch("growth_intelligence_v41.decisions.evaluate",return_value=[])
    @patch("growth_intelligence_v41.campaigns.analyze",return_value=[])
    @patch("growth_intelligence_v41.acquisition.analyze",return_value=[])
    @patch("growth_intelligence_v41.bos.core.access")
    def test_empty(self,*mocks):
        self.assertEqual(analyze(None,1,"one")["lead_count"],0)
        self.assertIn("No recorded acquisition channels",render(None,1,"one"))

    @patch("growth_intelligence_v41.bos.core.access",side_effect=ValueError("Denied"))
    def test_access_denied(self,access):
        with self.assertRaises(ValueError):analyze(None,1,"other")

if __name__=="__main__":unittest.main()
