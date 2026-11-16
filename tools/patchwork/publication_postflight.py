"""PATCHWORK V19: independently verify a published draft repair on GitHub.

Read-only postflight inspection. No GitHub writes, merges or deployments.
"""
import base64
import hashlib
import re
import urllib.parse

from github_publisher import api, load_release

SHA = re.compile(r'^[a-f0-9]{40}$')
REPO = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')

def verify_publication(repository, base_branch, archive_path, publication, *,
                       token, request=api):
    if not token or not REPO.fullmatch(repository):
        raise ValueError('GitHub token and valid repository required')
    if not isinstance(publication, dict) or publication.get('atomic_commit') is not True:
        raise ValueError('Atomic publication record required')
    sha = publication.get('commit_sha')
    branch = publication.get('branch')
    if not isinstance(sha,str) or not SHA.fullmatch(sha):
        raise ValueError('Invalid publication commit SHA')
    if not isinstance(branch,str) or not re.fullmatch(r'patchwork/review-[a-f0-9]{16}',branch):
        raise ValueError('Unexpected review branch')
    if branch != 'patchwork/review-' + sha[:16]:
        raise ValueError('Branch name and commit SHA mismatch')
    if not isinstance(base_branch,str) or not re.fullmatch(r'[A-Za-z0-9._/-]+',base_branch) or '..' in base_branch:
        raise ValueError('Invalid base branch')
    files=load_release(archive_path)
    if publication.get('files') != len(files):
        raise ValueError('Publication file count mismatch')
    prefix='/repos/'+repository
    commit=request(token,'GET',prefix+'/git/commits/'+sha)
    if commit.get('sha') != sha or len(commit.get('parents',[]))!=1:
        raise ValueError('Unexpected Git commit or parent count')
    # The GitHub commit-files endpoint exposes the full diff against the
    # commit's parent. Fail closed if the commit contains any unapproved file.
    diff=request(token,'GET',prefix+'/commits/'+sha+'?per_page=100')
    changed=diff.get('files')
    expected_paths={rel for rel,_,_ in files}
    if (not isinstance(changed,list) or len(changed)!=len(expected_paths)
            or diff.get('sha')!=sha
            or len(diff.get('parents',[]))!=1
            or diff['parents'][0].get('sha')!=commit['parents'][0].get('sha')):
        raise ValueError('Commit diff is incomplete or differs from approved file count')
    observed_paths=set()
    for item in changed:
        if (not isinstance(item,dict) or item.get('status')!='modified'
                or not isinstance(item.get('filename'),str)
                or item['filename'] in observed_paths):
            raise ValueError('Unexpected file operation in published commit')
        observed_paths.add(item['filename'])
    if observed_paths != expected_paths:
        raise ValueError('Published commit includes unapproved file changes')
    ref=request(token,'GET',prefix+'/git/ref/heads/'+urllib.parse.quote(branch,safe='/'))
    if ref.get('object',{}).get('sha') != sha:
        raise ValueError('Review branch changed after publication')
    for rel,replacement,_ in files:
        info=request(token,'GET',prefix+'/contents/'+urllib.parse.quote(rel,safe='/')+'?ref='+sha)
        try:
            actual=base64.b64decode(info['content'],validate=True)
        except (KeyError,ValueError,TypeError) as exc:
            raise ValueError('Cannot decode published source: '+rel) from exc
        if hashlib.sha256(actual).digest()!=hashlib.sha256(replacement).digest():
            raise ValueError('Published source differs from approved release: '+rel)
    owner=repository.split('/')[0]
    query='?state=open&head='+urllib.parse.quote(owner+':'+branch,safe=':')+'&base='+urllib.parse.quote(base_branch,safe='')
    prs=request(token,'GET',prefix+'/pulls'+query)
    if not isinstance(prs,list) or len(prs)!=1:
        raise ValueError('Exactly one open review PR required')
    pr=prs[0]
    if (pr.get('draft') is not True or pr.get('head',{}).get('sha')!=sha
            or pr.get('head',{}).get('ref')!=branch
            or pr.get('base',{}).get('ref')!=base_branch
            or pr.get('html_url')!=publication.get('draft_pull_request')):
        raise ValueError('Draft PR identity mismatch')
    return {'schema':'patchwork-publication-postflight-v1',
            'status':'verified','repository':repository,'head_sha':sha,
            'draft_pull_request':pr['html_url'],'files_verified':len(files),'commit_file_set_verified':True,
            'github_writes_performed':False,'merged':False,'deployed':False,
            'warning':'Read-only point-in-time verification; human review and CI still required.'}
