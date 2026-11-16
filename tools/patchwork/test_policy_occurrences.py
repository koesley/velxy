"""V16 policy regression tests: repeated dangerous calls cannot evade checks."""
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from release_policy import analyze

def sha(data):
    return hashlib.sha256(data).hexdigest()

def assess(old,new):
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)/'repo'
        root.mkdir()
        (root/'app.py').write_bytes(old.encode())
        archive=Path(temp)/'release.zip'
        manifest={'schema':'patchwork-staged-release-v1',
                  'approved_for_staging':True,
                  'files':[{'file':'app.py','original_sha256':sha(old.encode()),
                            'replacement_sha256':sha(new.encode())}]}
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('patchwork-manifest.json',json.dumps(manifest))
            z.writestr('proposed/app.py',new)
        return analyze(root,archive)

class PolicyOccurrenceTests(unittest.TestCase):
    def test_second_exec_is_blocked(self):
        old='exec("x=1")\n'
        new='exec("x=1")\nexec("y=2")\n'
        report=assess(old,new)
        self.assertEqual(report['status'],'blocked')
        self.assertTrue(any(f['rule']=='dangerous-call' for f in report['findings']))

    def test_new_destructive_filesystem_call_blocked(self):
        old='import shutil\n'
        new='import shutil\nshutil.rmtree("data")\n'
        report=assess(old,new)
        self.assertEqual(report['status'],'blocked')

    def test_existing_high_risk_call_not_automatically_new(self):
        old='exec("x=1")\ndef answer():\n    return 1\n'
        new='exec("x=1")\ndef answer():\n    return 2\n'
        report=assess(old,new)
        self.assertEqual(report['status'],'eligible')

    def test_new_subprocess_check_output_blocked(self):
        old='import subprocess\n'
        new='import subprocess\nsubprocess.check_output(["echo","hi"])\n'
        report=assess(old,new)
        self.assertEqual(report['status'],'blocked')

if __name__=='__main__':
    unittest.main()
