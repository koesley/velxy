"""Adversarial release archive regression tests."""
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from github_publisher import load_release

def sha(data):
    return hashlib.sha256(data).hexdigest()

class ArchiveSafetyTests(unittest.TestCase):
    def manifest(self, paths):
        return {'schema':'patchwork-staged-release-v1','approved_for_staging':True,
                'files':[{'file':p,'original_sha256':sha(b'old'),
                          'replacement_sha256':sha(b'new')} for p in paths]}

    def test_duplicate_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'release.zip'
            with zipfile.ZipFile(path,'w') as archive:
                archive.writestr('patchwork-manifest.json',
                                 json.dumps(self.manifest(['a.py','a.py'])))
                archive.writestr('proposed/a.py',b'new')
            with self.assertRaises(ValueError):
                load_release(path)

    def test_oversized_compressed_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'release.zip'
            payload=b'x'*(4*1024*1024+1)
            with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('patchwork-manifest.json',
                                 json.dumps(self.manifest(['a.py'])))
                archive.writestr('proposed/a.py',payload)
            with self.assertRaises(ValueError):
                load_release(path)

    def test_symlink_entry_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'release.zip'
            link=zipfile.ZipInfo('proposed/a.py')
            link.create_system=3
            link.external_attr=(0o120777 << 16)
            with zipfile.ZipFile(path,'w') as archive:
                archive.writestr('patchwork-manifest.json',
                                 json.dumps(self.manifest(['a.py'])))
                archive.writestr(link,b'new')
            with self.assertRaises(ValueError):
                load_release(path)

    def test_valid_archive_still_loads(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'release.zip'
            with zipfile.ZipFile(path,'w') as archive:
                archive.writestr('patchwork-manifest.json',
                                 json.dumps(self.manifest(['a.py'])))
                archive.writestr('proposed/a.py',b'new')
            self.assertEqual(load_release(path)[0][0],'a.py')

if __name__=='__main__':
    unittest.main()
