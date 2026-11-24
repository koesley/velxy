import unittest
from pathlib import Path

class DemoAutofillTests(unittest.TestCase):
    def test_demo_signup_autocomplete(self):
        source = Path(__file__).with_name('portal.py').read_text(encoding='utf-8')
        section = source.split('def demo_result_html(', 1)[1].split('def ledger_panel_html(', 1)[0]
        self.assertEqual(section.count('autocomplete="new-password"'), 2)
        self.assertEqual(section.count('autocomplete="email"'), 3)
