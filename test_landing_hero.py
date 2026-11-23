"""Tests for the hero stage's real before/after: the landing page hero no
longer shows a decorative "ILLUSTRATIVE VISUAL" diagram — it shows the
real sample run (the messy input, the exact flagged rows and their issues,
and the clean output), all from the same cached engine result as the
sample report, so the hero and the report below it can never disagree.
The page still renders with the static stage when the engine result is
unavailable. Run with:
  python -m unittest test_landing_hero -v
"""
import unittest
from unittest.mock import patch


class LandingHeroTests(unittest.TestCase):
    def setUp(self):
        import portal
        self.portal = portal
        # Force the engine to run fresh so each test sees the real result.
        portal._SAMPLE_ENGINE = None
        portal._SAMPLE_REPORT_HTML = None

    def test_hero_shows_real_flagged_rows_and_issues(self):
        html = self.portal.landing_page()
        # The exact flagged rows from the real sample, with the engine's
        # own issue strings — not hand-written values.
        self.assertIn('S-1001', html)
        self.assertIn('duplicate order ID', html)
        self.assertIn('S-1007', html)
        self.assertIn('invalid date', html)
        self.assertIn('S-1008', html)
        self.assertIn('quantity must be a positive integer', html)
        self.assertIn('REAL SAMPLE DATA', html)

    def test_hero_shows_real_counts_and_revenue(self):
        html = self.portal.landing_page()
        self.assertIn('9 ROWS', html)
        self.assertIn('3 rows', html)
        self.assertIn('6 ACCEPTED', html)
        self.assertIn('3 FLAGGED', html)
        self.assertIn('$800.00', html)

    def test_hero_no_longer_claims_to_be_an_illustration(self):
        html = self.portal.landing_page()
        self.assertNotIn('ILLUSTRATIVE VISUAL', html)
        self.assertNotIn('VISUAL DEMONSTRATION', html)

    def test_hero_numbers_match_the_engine_not_handwritten_values(self):
        # The hero and the sample report read the same cached engine
        # result, so assert the hero's figures against the engine itself.
        report = self.portal._sample_engine()
        self.assertIsNotNone(report)
        html = self.portal.landing_page()
        self.assertIn(str(report['accepted']) + ' ACCEPTED', html)
        self.assertIn(str(report['rejected']) + ' FLAGGED', html)
        self.assertIn(str(report['accepted'] + report['rejected']) + ' ROWS', html)
        for row in (report.get('rejected_rows') or [])[1:]:
            self.assertIn(row[1], html)
            self.assertIn(row[9].split(';')[0].strip(), html)

    def test_sample_report_still_renders_after_refactor(self):
        html = self.portal.landing_page()
        # The sample report section below the hero still shows the real
        # report (monthly + product summaries from the same engine run).
        self.assertIn('A REAL REPORT', html)
        self.assertIn('Monthly summary', html)
        self.assertIn('Product summary', html)
        self.assertIn('$470', html)

    def test_hero_falls_back_to_static_stage_when_engine_fails(self):
        with patch.object(self.portal, '_sample_engine', return_value=None):
            html = self.portal.landing_page()
        # The page still renders, with the old static stage.
        self.assertIn('RUN YOUR BUSINESS', html)
        self.assertIn('ILLUSTRATIVE VISUAL', html)
        self.assertIn('VISUAL DEMONSTRATION', html)
        # And no half-built real stage leaks through.
        self.assertNotIn('v8-hero-flags', html)
