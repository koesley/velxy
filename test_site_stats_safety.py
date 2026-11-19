"""Regression tests for founder analytics HTML safety and funnel wording."""
import unittest
import site_stats


class FounderStatsTests(unittest.TestCase):
    def test_event_detail_is_html_escaped(self):
        page = site_stats.stats_html(
            {'landing_view': 2, 'demo_run': 1}, [],
            [(1732000000, 'demo_run', '<script>alert("x")</script>')])
        self.assertNotIn('<script>', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertIn('&quot;x&quot;', page)

    def test_unknown_event_label_is_escaped(self):
        page = site_stats.stats_html({}, [],
            [(1732000000, '<img src=x onerror=alert(1)>', 'ok')])
        self.assertNotIn('<img', page)
        self.assertIn('&lt;img', page)

    def test_funnel_does_not_claim_cohort_conversion(self):
        page = site_stats.stats_html({}, [], [])
        self.assertIn('not unique visitors or cohorts', page)


if __name__ == '__main__':
    unittest.main()
