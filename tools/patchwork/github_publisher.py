"""PATCHWORK V4: GitHub draft pull request publisher.

Explicitly approved, review-only release ZIP -> dedicated branch -> draft PR.
No auto-merge, execution or deployment. Uses stdlib HTTPS GitHub API.
"""
import argparse
import base64
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile

MAX_FILES = 25
MAX_TOTAL = 4 * 1024 * 1024

def api(token, method, path, payload=None):
    if not path.startswith('/repos/'):
        raise ValueError('Unsupported GitHub API path')
    url = 'https://api.github.com' + path
    body = None if payload is None else json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(url, data=body, method=method, headers={
        'Authorization': 'Bearer ' + token,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'VELXTRIA-PATCHWORK',
        'Content-Type': 'application/json',
    })
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)

def load_release(archive_path):
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if not names or len(names) > MAX_FILES + 1 or len(names) != len(set(names)):
            raise ValueError('Invalid ZIP entry count or duplicates')
        if 'patchwork-manifest.json' not in names:
            raise ValueError('Missing release manifest')
        manifest = json.loads(archive.read('patchwork-manifest.json'))
        if manifest.get('schema') != 'patchwork-staged-release-v1' or manifest.get('approved_for_staging') is not True:
            raise ValueError('Invalid release manifest')
        files = manifest.get('files')
        if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
            raise ValueError('Invalid release files')
        if len(names) != len(files) + 1:
            raise ValueError('Unexpected ZIP entries')
        results = []
        total = 0
        for item in files:
            if not isinstance(item, dict):
                raise ValueError('Invalid file record')
            rel = item.get('file')
            if not isinstance(rel, str) or not rel.endswith('.py') or not rel or rel.startswith('/') or '\\' in rel or any(part in ('', '.', '..') for part in rel.split('/')):
                raise ValueError('Unsafe path')
            entry = 'proposed/' + rel
            if entry not in names:
                raise ValueError('Missing proposed file')
            data = archive.read(entry)
            total += len(data)
            if total > MAX_TOTAL or hashlib.sha256(data).hexdigest() != item.get('replacement_sha256'):
                raise ValueError('Invalid replacement digest or total size')
            if not re.fullmatch('[a-f0-9]{64}', str(item.get('original_sha256', ''))):
                raise ValueError('Invalid source digest')
            results.append((rel, data, item['original_sha256']))
        return results

def publish(repository, base_branch, archive_path, *, approve=False, token=None, request=api):
    if not approve:
        raise ValueError('Explicit --approve-draft-pr required')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Invalid repository')
    if not re.fullmatch(r'[A-Za-z0-9._/-]+', base_branch) or '..' in base_branch or base_branch.startswith('/'):
        raise ValueError('Invalid base branch')
    if not token:
        raise ValueError('GITHUB_TOKEN is required')
    files = load_release(archive_path)
    prefix = '/repos/' + repository
    head = request(token, 'GET', prefix + '/git/ref/heads/' + urllib.parse.quote(base_branch, safe='/'))
    base_sha = head['object']['sha']
    # Verify every original against the base branch BEFORE any writes.
    originals = []
    for rel, replacement, digest in files:
        file_info = request(token, 'GET', prefix + '/contents/' + urllib.parse.quote(rel, safe='/') + '?ref=' + urllib.parse.quote(base_branch, safe=''))
        original = base64.b64decode(file_info['content'])
        if hashlib.sha256(original).hexdigest() != digest:
            raise ValueError('Stale source on GitHub: ' + rel)
        originals.append((rel, replacement, file_info['sha']))
    branch = 'patchwork/review-' + hashlib.sha256((base_sha + ''.join(rel for rel, _, _ in originals) + ''.join(hashlib.sha256(data).hexdigest() for _, data, _ in originals)).encode()).hexdigest()[:16]
    request(token, 'POST', prefix + '/git/refs', {'ref': 'refs/heads/' + branch, 'sha': base_sha})
    for rel, replacement, _ in originals:
        # Read SHA from the new branch; do not blindly overwrite concurrent changes.
        info = request(token, 'GET', prefix + '/contents/' + urllib.parse.quote(rel, safe='/') + '?ref=' + urllib.parse.quote(branch, safe=''))
        if hashlib.sha256(base64.b64decode(info['content'])).hexdigest() != next(d for p, _, d in files if p == rel):
            raise ValueError('Source changed during publication: ' + rel)
        request(token, 'PUT', prefix + '/contents/' + urllib.parse.quote(rel, safe='/'), {
            'message': 'PATCHWORK: stage reviewed repair for ' + rel,
            'branch': branch, 'sha': info['sha'],
            'content': base64.b64encode(replacement).decode('ascii')})
    pr = request(token, 'POST', prefix + '/pulls', {
        'title': 'PATCHWORK: review staged repairs (' + str(len(files)) + ' files)',
        'head': branch, 'base': base_branch, 'draft': True,
        'body': 'PATCHWORK staged repair proposals. Human review required.\\n\\n'
                'No tests were run by the publisher. No automatic merge or deployment.\\n'
                'Review source changes and required CI before approving.'})
    return {'draft_pull_request': pr['html_url'], 'branch': branch, 'files': len(files), 'merged': False}

def main():
    parser = argparse.ArgumentParser(description='Publish reviewed ZIP as a GitHub draft PR')
    parser.add_argument('repository', help='owner/repo')
    parser.add_argument('base_branch')
    parser.add_argument('release_zip')
    parser.add_argument('--approve-draft-pr', action='store_true')
    args = parser.parse_args()
    print(json.dumps(publish(args.repository, args.base_branch, args.release_zip,
                             approve=args.approve_draft_pr, token=os.getenv('GITHUB_TOKEN')), indent=2))

if __name__ == '__main__':
    sys.exit(main())
