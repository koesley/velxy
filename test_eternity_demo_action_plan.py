import unittest
from unittest.mock import patch
import portal

class DemoActionPlanTests(unittest.TestCase):
    def test_recommendations_follow_report_evidence(self):
        for accepted, rejected, phrase in [(2,1,'Review flagged rows'),(2,0,'Compare monthly and product summaries'),(0,0,'Upload a CSV containing sales records')]:
            result = dict(accepted=accepted,rejected=rejected,monthly_rows=[],product_rows=[],stats=[])
            with patch.object(portal,'report_diagnosis_html',return_value=''), patch.object(portal,'report_summaries_html',return_value=''):
                page = portal.demo_result_html(result,'token')
            self.assertIn('Recommended next step',page)
            self.assertIn(phrase,page)
