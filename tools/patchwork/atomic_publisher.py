"""PATCHWORK V8: atomic Git tree publisher for approved repair archives.

Builds one Git tree and one commit for all proposed files, then creates a
review branch pointing to that complete commit. No partial file-by-file
uploads. GitHub draft PR is still mandatory; no merges or deployments.
"""
import argparse
import base64
import hashlib
import json
import os
import re
import urllib.parse

from github_publisher import api, load_release, validate_test_evidence
from release_policy import analyze as analyze_release_policy

REPO = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
BRANCH = re.compile(r'^[A-Za-z0-9._/-]+$')
SHA = re.compile(r'^[0-9a-f]{40}$')

def publish_atomic(repository, base_branch, archive_path, *, approve=False,
                   token=None, evidence_path=None, request=api,
                   source_root=None, approve_sensitive=False):
    if not approve:
        raise ValueError('Explicit --approve-draft-pr is required')
    if not token:
        raise ValueError('GITHUB_TOKEN is required')
    if not REPO.fullmatch(repository):
        raise ValueError('Invalid repository')
    if (not BRANCH.fullmatch(base_branch) or '..' in base_branch
            or base_branch.startswith('/') or base_branch.endswith('/')
            or base_branch.endswith('.lock')):
        raise ValueError('Invalid base branch')
    validate_test_evidence(archive_path, evidence_path)
    if source_root is None:
        raise ValueError('Local source repository is required for policy enforcement')
    policy = analyze_release_policy(source_root, archive_path)
    if policy['status'] == 'blocked':
        raise ValueError('Release policy blocked this repair')
    if policy['status'] == 'needs_review' and not approve_sensitive:
        raise ValueError('Sensitive repair requires explicit --approve-sensitive-review')
    release_digest = hashlib.sha256(__import__('pathlib').Path(archive_path).read_bytes()).hexdigest()
    files = load_release(archive_path)
    if len({rel for rel, _, _ in files}) != len(files):
        raise ValueError('Duplicate release target paths')
    prefix = '/repos/' + repository
    ref = request(token, 'GET', prefix + '/git/ref/heads/' +
                  urllib.parse.quote(base_branch, safe='/'))
    base_sha = ref['object']['sha']
    if not SHA.fullmatch(base_sha):
        raise ValueError('Invalid base commit SHA')
    commit = request(token, 'GET', prefix + '/git/commits/' + base_sha)
    tree_sha = commit['tree']['sha']
    if not SHA.fullmatch(tree_sha):
        raise ValueError('Invalid base tree SHA')
    # All source checks happen before creating any Git objects.
    for rel, replacement, digest in files:
        path = prefix + '/contents/' + urllib.parse.quote(rel, safe='/')
        info = request(token, 'GET', path + '?ref=' + base_sha)
        if hashlib.sha256(base64.b64decode(info['content'])).hexdigest() != digest:
            raise ValueError('Source differs from approved release: ' + rel)
    # Git objects are immutable; these writes do not change refs or branches.
    entries = []
    for rel, replacement, _ in files:
        blob = request(token, 'POST', prefix + '/git/blobs',
                       {'content': base64.b64encode(replacement).decode('ascii'),
                        'encoding': 'base64'})
        blob_sha = blob['sha']
        if not SHA.fullmatch(blob_sha):
            raise ValueError('Invalid blob SHA')
        entries.append({'path': rel, 'mode': '100644', 'type': 'blob', 'sha': blob_sha})
    tree = request(token, 'POST', prefix + '/git/trees',
                   {'base_tree': tree_sha, 'tree': entries})
    new_commit = request(token, 'POST', prefix + '/git/commits',
                         {'message': 'PATCHWORK: atomic reviewed repair (' +
                          str(len(files)) + ' files)\n\nPatchwork-Release-SHA256: ' + release_digest + '\nPatchwork-Base-SHA: ' + base_sha, 'tree': tree['sha'],
                          'parents': [base_sha]})
    new_sha = new_commit['sha']
    if not SHA.fullmatch(new_sha):
        raise ValueError('Invalid new commit SHA')
    # Guard against the base branch moving during object construction.
    latest = request(token, 'GET', prefix + '/git/ref/heads/' +
                     urllib.parse.quote(base_branch, safe='/'))
    if latest['object']['sha'] != base_sha:
        raise ValueError('Base branch moved during preparation; no repair branch created')
    branch = 'patchwork/review-' + new_sha[:16]
    # Recover from a previous partial attempt without moving an existing ref.
    # A pre-existing review branch must point to exactly this immutable commit.
    ref_path = prefix + '/git/ref/heads/' + urllib.parse.quote(branch, safe='/')
    try:
        existing = request(token, 'GET', ref_path)
    except Exception as exc:
        # GitHub's standard 404 means absent. Other errors (401/403/5xx,
        # network failures) must fail closed, not be interpreted as absence.
        if getattr(exc, 'code', None) != 404:
            raise
        existing = None
    if existing is not None:
        if existing.get('object', {}).get('sha') != new_sha:
            raise ValueError('Existing review branch points to a different commit')
    else:
        try:
            request(token, 'POST', prefix + '/git/refs',
                    {'ref': 'refs/heads/' + branch, 'sha': new_sha})
        except Exception:
            # A concurrent retry may have created the same branch.
            current = request(token, 'GET', ref_path)
            if current.get('object', {}).get('sha') != new_sha:
                raise
    owner = repository.split('/')[0]
    query = ('?state=open&head=' + urllib.parse.quote(owner + ':' + branch, safe=':')
             + '&base=' + urllib.parse.quote(base_branch, safe=''))
    existing_prs = request(token, 'GET', prefix + '/pulls' + query)
    if not isinstance(existing_prs, list):
        raise ValueError('Invalid GitHub PR listing')
    matches = [item for item in existing_prs
               if item.get('head', {}).get('sha') == new_sha
               and item.get('head', {}).get('ref') == branch
               and item.get('base', {}).get('ref') == base_branch]
    if len(matches) > 1 or (existing_prs and len(matches) != len(existing_prs)):
        raise ValueError('Conflicting review pull request already exists')
    if matches:
        if matches[0].get('draft') is not True:
            raise ValueError('Existing review pull request is not a draft')
        pr = matches[0]
        reused = True
    else:
        try:
            pr = request(token, 'POST', prefix + '/pulls',
                         {'title': 'PATCHWORK: atomic repair review (' + str(len(files)) + ' files)',
                          'head': branch, 'base': base_branch, 'draft': True,
                          'body': 'Atomic multi-file repair commit. Human review and GitHub CI required. '
                                  'Local verification report is not a trusted CI attestation. '
                                  'No automatic merge or deployment.'})
            reused = False
        except Exception:
            # If GitHub accepted the POST but the response was lost, detect
            # the resulting draft instead of blindly creating another one.
            recovered = request(token, 'GET', prefix + '/pulls' + query)
            matches = [item for item in recovered
                       if item.get('head', {}).get('sha') == new_sha
                       and item.get('draft') is True
                       and item.get('base', {}).get('ref') == base_branch]
            if len(matches) != 1 or len(recovered) != 1:
                raise
            pr = matches[0]
            reused = True
    publication = {'draft_pull_request': pr['html_url'], 'branch': branch,
                   'commit_sha': new_sha, 'base_commit_sha': base_sha,
                   'release_sha256': release_digest, 'files': len(files), 'merged': False,
                   'deployed': False, 'atomic_commit': True, 'reused_existing_pr': reused}
    # Fail closed: a successful POST response is not publication proof.
    # Import lazily to avoid the compatibility publisher import cycle.
    from publication_postflight import verify_publication
    verification = verify_publication(repository, base_branch, archive_path,
                                      publication, token=token, request=request)
    publication['postflight_verified'] = verification['status'] == 'verified'
    publication['postflight_schema'] = verification['schema']
    return publication

def main():
    parser = argparse.ArgumentParser(description='Publish one atomic repair commit as a draft PR')
    parser.add_argument('repository')
    parser.add_argument('base_branch')
    parser.add_argument('release_zip')
    parser.add_argument('--verification-report', required=True)
    parser.add_argument('--source-root', required=True, help='Repository checkout used for policy verification')
    parser.add_argument('--approve-sensitive-review', action='store_true')
    parser.add_argument('--approve-draft-pr', action='store_true')
    args = parser.parse_args()
    print(json.dumps(publish_atomic(args.repository, args.base_branch, args.release_zip,
                                    approve=args.approve_draft_pr,
                                    evidence_path=args.verification_report,
                                    source_root=args.source_root,
                                    approve_sensitive=args.approve_sensitive_review,
                                    token=os.getenv('GITHUB_TOKEN')), indent=2))

if __name__ == '__main__':
    main()
