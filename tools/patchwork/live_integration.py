"""PATCHWORK V14: guarded live GitHub integration probe.

Opt-in only. Creates a controlled repair in a separately designated disposable
repository, publishes a draft PR, and verifies the resulting remote commit and
PR via GitHub REST. Does not merge, close, delete, or deploy anything.
"""
import argparse
import hashlib
import json
import os
import re
import tempfile
import urllib.parse
from pathlib import Path

from atomic_publisher import publish_atomic
from github_publisher import api
from isolated_verify import verify
from release_gate import prepare_release
from release_policy import analyze

REPO_PATTERN = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
FIXTURE = 'patchwork_integration_fixture.py'
OLD = 'def patchwork_fixture():\n    return 1\n'
NEW = 'def patchwork_fixture():\n    return 2\n'
TEST = 'import unittest\nfrom patchwork_integration_fixture import patchwork_fixture\nclass FixtureTest(unittest.TestCase):\n    def test_repair(self):\n        self.assertEqual(patchwork_fixture(), 2)\n'

def _digest(data):
    return hashlib.sha256(data).hexdigest()

def run(repository, base_branch, *, token, approve=False, request=api,
        expected_repository=None):
    if not approve:
        raise ValueError('Explicit --approve-live-disposable-test required')
    if not REPO_PATTERN.fullmatch(repository):
        raise ValueError('Invalid repository')
    if repository == 'koesley/velxy':
        raise ValueError('Live integration is forbidden against the production repository')
    if not expected_repository or repository != expected_repository:
        raise ValueError('Repository must match PATCHWORK_DISPOSABLE_REPOSITORY exactly')
    if not token:
        raise ValueError('GitHub token required')
    if not re.fullmatch(r'[A-Za-z0-9._/-]+',base_branch) or '..' in base_branch:
        raise ValueError('Invalid base branch')
    prefix = '/repos/' + repository
    repo_info = request(token,'GET',prefix)
    if repo_info.get('full_name') != repository or repo_info.get('archived') or repo_info.get('disabled'):
        raise ValueError('Repository identity or state mismatch')
    if repo_info.get('private') is not True:
        raise ValueError('Disposable integration repository must be private')
    if repo_info.get('default_branch') != base_branch:
        raise ValueError('Only the disposable repository default branch is supported')
    info = request(token,'GET',prefix+'/contents/'+FIXTURE+'?ref='+urllib.parse.quote(base_branch,safe=''))
    import base64
    if _digest(base64.b64decode(info['content'])) != _digest(OLD.encode()):
        raise ValueError('Disposable repository fixture does not match expected baseline')
    with tempfile.TemporaryDirectory(prefix='patchwork-live-probe-') as temp:
        work=Path(temp)
        source=work/'source'
        source.mkdir()
        (source/FIXTURE).write_text(OLD)
        (source/'test_patchwork_integration.py').write_text(TEST)
        bundle=work/'review.json'
        bundle.write_text(json.dumps({'schema':'patchwork-review-v1','file':FIXTURE,
                                      'original':OLD,'replacement':NEW}))
        archive=work/'release.zip'
        prepare_release(source,[bundle],archive,approve=True)
        policy=analyze(source,archive)
        if policy['status']!='eligible':
            raise ValueError('Fixture rejected by policy')
        verification=verify(source,archive,approve=True)
        if verification['status']!='passed':
            raise ValueError('Actual Docker verification failed: '+verification['status'])
        report=work/'evidence.json'
        report.write_text(json.dumps(verification))
        published=publish_atomic(repository,base_branch,archive,approve=True,
                                 token=token,evidence_path=report,source_root=source,
                                 request=request)
    sha=published['commit_sha']
    remote=request(token,'GET',prefix+'/git/commits/'+sha)
    if remote.get('sha')!=sha or not remote.get('parents') or not re.fullmatch('[a-f0-9]{40}',remote['parents'][0]['sha']):
        raise ValueError('Published commit could not be verified')
    branch=published['branch']
    remote_ref=request(token,'GET',prefix+'/git/ref/heads/'+urllib.parse.quote(branch,safe='/'))
    if remote_ref.get('object',{}).get('sha')!=sha:
        raise ValueError('Published branch SHA differs from expected commit')
    repaired=request(token,'GET',prefix+'/contents/'+FIXTURE+'?ref='+sha)
    if _digest(base64.b64decode(repaired['content'])) != _digest(NEW.encode()):
        raise ValueError('Published commit does not contain the approved replacement')
    prs=request(token,'GET',prefix+'/pulls?state=open&head='+urllib.parse.quote(repository.split('/')[0]+':'+branch,safe=':')+'&base='+urllib.parse.quote(base_branch,safe=''))
    matching=[pr for pr in prs if pr.get('draft') is True and pr.get('head',{}).get('sha')==sha]
    if len(matching)!=1:
        raise ValueError('Could not confirm exactly one open draft PR for immutable head')
    if matching[0].get('base',{}).get('ref')!=base_branch or matching[0].get('head',{}).get('ref')!=branch:
        raise ValueError('Draft PR targets an unexpected branch')
    return {'schema':'patchwork-live-integration-v1','status':'published_for_review',
            'repository':repository,'draft_pr':matching[0]['html_url'],
            'head_sha':sha,'source_unchanged':True,
            'real_docker_executed':True,'github_verified':True,
            'merged':False,'deployed':False,
            'note':'Draft PR intentionally left open for human review; no cleanup is automatic.'}

def main():
    parser=argparse.ArgumentParser(description='Opt-in disposable-repository live GitHub probe')
    parser.add_argument('repository')
    parser.add_argument('base_branch')
    parser.add_argument('--approve-live-disposable-test',action='store_true')
    args=parser.parse_args()
    print(json.dumps(run(args.repository,args.base_branch,token=os.getenv('GITHUB_TOKEN'),
                         approve=args.approve_live_disposable_test,
                         expected_repository=os.getenv('PATCHWORK_DISPOSABLE_REPOSITORY')),indent=2))

if __name__=='__main__':
    main()
