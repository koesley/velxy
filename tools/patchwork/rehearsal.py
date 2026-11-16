"""PATCHWORK V12: end-to-end release rehearsal, entirely offline.

Exercises review bundles -> staged ZIP -> static release policy -> isolated
test command construction -> atomic Git commit/draft PR -> immutable CI gate.
GitHub and Docker are simulated. Never sends requests or executes project code.
"""
import base64
import hashlib
import json
import subprocess
import urllib.error
import tempfile
from pathlib import Path

from release_gate import prepare_release
from release_policy import analyze
from isolated_verify import verify
from atomic_publisher import publish_atomic
from github_ci_gate import inspect_pr

def sha(data):
    return hashlib.sha256(data).hexdigest()

def rehearse():
    with tempfile.TemporaryDirectory(prefix='patchwork-rehearsal-') as temp:
        work = Path(temp)
        root = work/'source'
        root.mkdir()
        originals = {'app.py': 'def answer():\n    return 1\n',
                     'test_app.py': 'import unittest\nclass TestApp(unittest.TestCase):\n    def test_one(self):\n        self.assertTrue(True)\n'}
        replacements = {'app.py': 'def answer():\n    return 2\n',
                        'test_app.py': 'import unittest\nclass TestApp(unittest.TestCase):\n    def test_one(self):\n        self.assertEqual(2, 2)\n'}
        bundles = []
        for rel, original in originals.items():
            (root/rel).write_text(original, encoding='utf-8')
            bundle = work/(rel+'.json')
            bundle.write_text(json.dumps({'schema':'patchwork-review-v1','file':rel,
                                          'original':original,'replacement':replacements[rel]}))
            bundles.append(bundle)
        before = {rel:sha((root/rel).read_bytes()) for rel in originals}
        archive = work/'staged.zip'
        prepare_release(root,bundles,archive,approve=True)
        policy = analyze(root,archive)
        if policy['status'] != 'eligible':
            raise AssertionError('Unexpected policy findings: '+str(policy['findings']))
        docker_commands = []
        def docker_mock(command, **kwargs):
            docker_commands.append(command)
            return subprocess.CompletedProcess(command,0,'','Ran 2 tests in 0.001s\nOK')
        verification = verify(root,archive,approve=True,runner=docker_mock)
        if verification['status'] != 'passed' or verification['tests_discovered'] != 2:
            raise AssertionError('Isolated verifier contract failed')
        report = work/'verification.json'
        report.write_text(json.dumps(verification))
        base_sha='a'*40
        commit_sha='f'*40
        calls=[]
        def github(token, method, path, payload=None):
            calls.append((method,path,payload))
            if '/git/ref/heads/patchwork/' in path:
                count=sum('/git/ref/heads/patchwork/' in p for _,p,_ in calls)
                if count == 1:
                    raise urllib.error.HTTPError(path,404,'Not Found',{},None)
                return {'object':{'sha':commit_sha}}
            if '/git/ref/heads/' in path:
                return {'object':{'sha':base_sha}}
            if path.endswith('/git/commits/'+base_sha):
                return {'tree':{'sha':'b'*40}}
            if path.endswith('/git/commits/'+commit_sha):
                return {'sha':commit_sha,'parents':[{'sha':base_sha}],
                        'message':'Patchwork-Release-SHA256: '+sha(archive.read_bytes())+'\nPatchwork-Base-SHA: '+base_sha}
            if '/commits/' in path and method == 'GET' and '/git/commits/' not in path:
                return {'sha':commit_sha,'parents':[{'sha':base_sha}],
                        'files':[{'filename':rel,'status':'modified'} for rel in originals]}
            if '/contents/' in path:
                rel=path.split('/contents/',1)[1].split('?',1)[0]
                content = replacements[rel].encode() if '?ref='+commit_sha in path else originals[rel].encode()
                return {'content':base64.b64encode(content).decode()}
            if path.endswith('/git/blobs'):
                return {'sha':'c'*40}
            if path.endswith('/git/trees'):
                return {'sha':'d'*40}
            if path.endswith('/git/commits'):
                return {'sha':commit_sha}
            if '/pulls?' in path:
                count=sum('/pulls?' in p for _,p,_ in calls)
                if count == 1:
                    return []
                return [{'draft':True,'head':{'sha':commit_sha,'ref':'patchwork/review-'+commit_sha[:16]},
                         'base':{'ref':'main'},'html_url':'https://github.com/owner/repo/pull/42'}]
            if path.endswith('/pulls'):
                return {'html_url':'https://github.com/owner/repo/pull/42'}
            return {}
        published = publish_atomic('owner/repo','main',archive,approve=True,
                                   token='fake',evidence_path=report,source_root=root,
                                   request=github)
        def checks(token,method,path,payload=None):
            if '/pulls/' in path:
                return {'state':'open','draft':True,'head':{'sha':commit_sha,
                        'repo':{'full_name':'owner/repo'}}}
            return {'total_count':1,'check_runs':[{
                'name':'patchwork-repair-ci','status':'completed',
                'conclusion':'success','head_sha':commit_sha,
                'app':{'slug':'github-actions'}}]}
        ci=inspect_pr('owner/repo',42,token='fake',expected_sha=commit_sha,request=checks)
        if ci['status']!='passed':
            raise AssertionError('Immutable CI gate failed')
        after={rel:sha((root/rel).read_bytes()) for rel in originals}
        if before!=after:
            raise AssertionError('Original source modified')
        if len([x for x in calls if x[0]=='POST' and x[1].endswith('/git/commits')])!=1:
            raise AssertionError('Expected exactly one atomic commit')
        if any(x[0]=='PUT' for x in calls):
            raise AssertionError('Per-file GitHub writes are forbidden')
        if not any('--network' in cmd and 'none' in cmd for cmd in docker_commands):
            raise AssertionError('Docker network isolation missing')
        return {'schema':'patchwork-rehearsal-v1','status':'passed',
                'files':len(originals),'release_sha256':sha(archive.read_bytes()),
                'policy_status':policy['status'],'simulated_tests':verification['tests_discovered'],
                'atomic_commit_sha':published['commit_sha'],
                'immutable_ci_status':ci['status'],
                'source_unchanged':True,'github_requests_simulated':True,
                'docker_execution_simulated':True,'merged':False,'deployed':False}

if __name__=='__main__':
    print(json.dumps(rehearse(),indent=2))
