"""Tests for repository-wide repair campaigns."""
import tempfile
import unittest
from pathlib import Path
from campaign import build_campaign, discover

class CampaignTests(unittest.TestCase):
    def test_scans_multiple_files_without_modification(self):
        with tempfile.TemporaryDirectory() as root:
            good = Path(root)/'good.py'
            bad = Path(root)/'broken.py'
            good.write_text('x = 1\n')
            bad.write_text('if True\n    print(1)\n')
            result = build_campaign(root)
            self.assertEqual(result['files_scanned'], 2)
            self.assertEqual(result['syntax_errors'], 1)
            self.assertEqual(len(result['proposals']), 1)
            self.assertEqual(result['proposals'][0]['engine'], 'rule')
            self.assertFalse(result['applied'])
            self.assertEqual(bad.read_text(), 'if True\n    print(1)\n')

    def test_excludes_dependencies_and_symlinks(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)/'node_modules'
            folder.mkdir()
            (folder/'bad.py').write_text('broken(\n')
            (Path(root)/'good.py').write_text('x=1\n')
            (Path(root)/'alias.py').symlink_to(Path(root)/'good.py')
            self.assertEqual(discover(root), ['good.py'])

    def test_scan_limit(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root)/'a.py').write_text('x=1\n')
            (Path(root)/'b.py').write_text('y=2\n')
            with self.assertRaises(ValueError):
                discover(root, max_files=1)

    def test_ai_requires_explicit_consent(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                build_campaign(root, ai=True, api_key='test')

if __name__ == '__main__':
    unittest.main()
