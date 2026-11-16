"""PATCHWORK staged release gate tests."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from release_gate import prepare_release

class ReleaseGateTests(unittest.TestCase):
    def make_bundle(self, folder, name='a.py', before='x = 1\n', after='x = 2\n'):
        p = folder/'review.json'
        p.write_text(json.dumps({'schema': 'patchwork-review-v1', 'file': name,
                                 'original': before, 'replacement': after}))
        return p

    def test_explicit_approval_and_no_source_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base/'repo'
            root.mkdir()
            (root/'a.py').write_text('x = 1\n')
            bundle = self.make_bundle(base)
            output = base/'release.zip'
            with self.assertRaises(ValueError):
                prepare_release(root, [bundle], output)
            result = prepare_release(root, [bundle], output, approve=True)
            self.assertFalse(result['source_repository_modified'])
            self.assertEqual((root/'a.py').read_text(), 'x = 1\n')
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.read('proposed/a.py'), b'x = 2\n')

    def test_rejects_stale_source(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base/'repo'
            root.mkdir()
            (root/'a.py').write_text('x = 9\n')
            bundle = self.make_bundle(base)
            with self.assertRaises(ValueError):
                prepare_release(root, [bundle], base/'out.zip', approve=True)

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base/'repo'
            root.mkdir()
            bundle = self.make_bundle(base, name='../a.py')
            with self.assertRaises(ValueError):
                prepare_release(root, [bundle], base/'out.zip', approve=True)

    def test_rejects_invalid_syntax(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base/'repo'
            root.mkdir()
            (root/'a.py').write_text('x = 1\n')
            bundle = self.make_bundle(base, after='def bad(:\n')
            with self.assertRaises(SyntaxError):
                prepare_release(root, [bundle], base/'out.zip', approve=True)

    def test_rejects_output_inside_repo(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base/'repo'
            root.mkdir()
            (root/'a.py').write_text('x = 1\n')
            bundle = self.make_bundle(base)
            with self.assertRaises(ValueError):
                prepare_release(root, [bundle], root/'out.zip', approve=True)

if __name__ == '__main__':
    unittest.main()
