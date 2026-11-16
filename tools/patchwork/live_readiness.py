"""PATCHWORK V15: remote GitHub integration readiness audit (read-only).

Checks disposable-repository identity, private visibility, exact fixture
baseline, default branch and permissions without creating Git objects,
branches, pull requests or modifying repository settings.
"""
import argparse
import base64
import hashlib
import json
import os
import re
import urllib.parse

from github_publisher import api
from live_integration import FIXTURE, OLD

REPO = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')

def audit(repository, branch, *, token, expected_repository, request=api):
    if not token:
        raise ValueError('GitHub token required')
    if not REPO.fullmatch(repository) or repository == 'koesley/velxy':
        raise ValueError('Only separate disposable repositories are supported')
    if not expected_repository or expected_repository != repository:
        raise ValueError('Explicit disposable repository allowlist required')
    if not re.fullmatch('[A-Za-z0-9._/-]+',branch) or '..' in branch or branch.startswith('/'):
        raise ValueError('Invalid branch')
    prefix='/repos/'+repository
    checks=[]
    def record(name, condition, detail):
        checks.append({'check':name,'passed':bool(condition),'detail':detail})
    meta=request(token,'GET',prefix)
    record('repository-identity',meta.get('full_name')==repository,'Repository identity matches allowlist')
    record('private-repository',meta.get('private') is True,'Disposable repository must be private')
    record('repository-active',not meta.get('archived') and not meta.get('disabled'),'Repository must be active')
    record('default-branch',meta.get('default_branch')==branch,'Expected default branch must match')
    permissions=meta.get('permissions',{})
    record('push-permission',permissions.get('push') is True,'Token must have write access')
    record('pull-permission',permissions.get('pull') is True,'Token must have read access')
    # Do not query fixture if the repository is not the intended private target.
    if not all(c['passed'] for c in checks[:4]):
        return {'schema':'patchwork-live-readiness-v1','status':'blocked',
                'repository':repository,'checks':checks,'writes_performed':False}
    ref=request(token,'GET',prefix+'/git/ref/heads/'+urllib.parse.quote(branch,safe='/'))
    sha=(ref.get('object') or {}).get('sha')
    record('base-commit-sha',isinstance(sha,str) and bool(re.fullmatch('[a-f0-9]{40}',sha or '')),
           'Default branch must resolve to immutable commit')
    info=request(token,'GET',prefix+'/contents/'+FIXTURE+'?ref='+urllib.parse.quote(branch,safe=''))
    try:
        decoded=base64.b64decode(info['content'],validate=False)
        baseline=hashlib.sha256(decoded).digest()==hashlib.sha256(OLD.encode()).digest()
    except (KeyError,TypeError,ValueError):
        baseline=False
    record('fixture-baseline',baseline,'Remote fixture must exactly match the approved baseline')
    return {'schema':'patchwork-live-readiness-v1',
            'status':'ready' if all(c['passed'] for c in checks) else 'blocked',
            'repository':repository,'branch':branch,'base_sha':sha,
            'checks':checks,'writes_performed':False,
            'warning':'Readiness is a point-in-time assessment, not a guarantee of subsequent publication.'}

def main():
    parser=argparse.ArgumentParser(description='Read-only disposable GitHub integration readiness audit')
    parser.add_argument('repository')
    parser.add_argument('branch')
    args=parser.parse_args()
    result=audit(args.repository,args.branch,token=os.getenv('GITHUB_TOKEN'),
                 expected_repository=os.getenv('PATCHWORK_DISPOSABLE_REPOSITORY'))
    print(json.dumps(result,indent=2))
    if result['status']!='ready':
        raise SystemExit(1)

if __name__=='__main__':
    main()
