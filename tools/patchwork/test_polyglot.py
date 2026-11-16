"""Polyglot triage regression tests."""
import tempfile
import unittest
from pathlib import Path
from polyglot import inventory

class PolyglotTests(unittest.TestCase):
    def test_multilanguage_findings(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            (base/'app.py').write_text('eval(value)\n')
            (base/'client.ts').write_text('element.innerHTML = data;\n')
            (base/'package.json').write_text('{"dependencies":{"example":"latest"}}')
            (base/'broken.json').write_text('{"bad":}')
            (base/'Dockerfile').write_text('FROM python:3.11\nUSER root\n')
            report = inventory(root)
            rules = {f['rule'] for f in report['findings']}
            self.assertTrue({'python_dynamic_execution','js_insecure_dom','unbounded_dependency','invalid_json','docker_root_user'} <= rules)
            self.assertEqual(report['files_inspected'], 5)
            self.assertTrue(report['read_only'])

    def test_ignores_dependencies_and_symlinks(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            (base/'node_modules').mkdir()
            (base/'node_modules'/'evil.js').write_text('eval(input)')
            (base/'good.js').write_text('console.log(1)')
            (base/'alias.js').symlink_to(base/'good.js')
            report = inventory(root)
            self.assertEqual(report['files_inspected'], 1)
            self.assertEqual(report['findings'], [])

    def test_limit_marks_truncated(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            (base/'a.py').write_text('x=1')
            (base/'b.py').write_text('x=2')
            report = inventory(root, max_files=1)
            self.assertTrue(report['truncated'])
            self.assertEqual(report['files_inspected'], 1)

if __name__ == '__main__':
    unittest.main()
