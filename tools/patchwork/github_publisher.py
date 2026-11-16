"""PATCHWORK V17: compatibility facade for policy-enforced atomic publishing.

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
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if any(item.is_dir() or item.flag_bits & 1 or
               ((item.external_attr >> 16) & 0o170000) == 0o120000
               for item in infos):
            raise ValueError('Directories, encrypted entries and symlinks are forbidden')
        if any(item.file_size > MAX_TOTAL or item.compress_size > MAX_TOTAL
               for item in infos):
            raise ValueError('Oversized ZIP entry')
        if sum(item.file_size for item in infos) > MAX_TOTAL + 65536:
            raise ValueError('ZIP exceeds uncompressed size budget')
        if not names or len(names) > MAX_FILES + 1 or len(names) != len(set(names)):
            raise ValueError('Invalid ZIP entry count or duplicates')
        if 'patchwork-manifest.json' not in names:
            raise ValueError('Missing release manifest')
        manifest_info = archive.getinfo('patchwork-manifest.json')
        if manifest_info.file_size > 65536:
            raise ValueError('Oversized release manifest')
        manifest = json.loads(archive.read('patchwork-manifest.json'))
        if manifest.get('schema') != 'patchwork-staged-release-v1' or manifest.get('approved_for_staging') is not True:
            raise ValueError('Invalid release manifest')
        files = manifest.get('files')
        if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
            raise ValueError('Invalid release files')
        if len(names) != len(files) + 1:
            raise ValueError('Unexpected ZIP entries')
        results = []
        seen_paths = set()
        total = 0
        for item in files:
            if not isinstance(item, dict):
                raise ValueError('Invalid file record')
            rel = item.get('file')
            if not isinstance(rel, str) or not rel.endswith('.py') or not rel or rel.startswith('/') or '\\' in rel or any(part in ('', '.', '..') for part in rel.split('/')):
                raise ValueError('Unsafe path')
            if rel in seen_paths:
                raise ValueError('Duplicate release target path')
            seen_paths.add(rel)
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
        if set(names) != {'patchwork-manifest.json'} | {'proposed/' + rel for rel in seen_paths}:
            raise ValueError('Unexpected ZIP entries')
        return results

def validate_test_evidence(archive_path, evidence_path):
    if not evidence_path:
        raise ValueError('A passing isolated verification report is required')
    evidence_file = __import__('pathlib').Path(evidence_path)
    if evidence_file.stat().st_size > 100_000:
        raise ValueError('Verification report too large')
    report = json.loads(evidence_file.read_text(encoding='utf-8'))
    archive_digest = hashlib.sha256(__import__('pathlib').Path(archive_path).read_bytes()).hexdigest()
    if (report.get('schema') != 'patchwork-isolated-verification-v1'
            or report.get('status') != 'passed'
            or report.get('exit_code') != 0
            or not isinstance(report.get('tests_discovered'), int)
            or report['tests_discovered'] < 1
            or report.get('release_sha256') != archive_digest
            or report.get('source_repository_modified') is not False
            or report.get('tests_executed_on_host') is not False):
        raise ValueError('Missing, stale or unsuccessful isolated verification')
    return report

def publish(repository, base_branch, archive_path, *, approve=False, token=None,
            request=api, evidence_path=None, source_root=None,
            approve_sensitive=False):
    """Compatibility API: delegate exclusively to policy-enforced atomic publisher.

    The legacy per-file GitHub Contents API write path has been retired.
    """
    from atomic_publisher import publish_atomic
    return publish_atomic(
        repository, base_branch, archive_path, approve=approve, token=token,
        evidence_path=evidence_path, request=request, source_root=source_root,
        approve_sensitive=approve_sensitive)


def main():
    parser = argparse.ArgumentParser(description='Publish reviewed ZIP as a GitHub draft PR')
    parser.add_argument('repository', help='owner/repo')
    parser.add_argument('base_branch')
    parser.add_argument('release_zip')
    parser.add_argument('--approve-draft-pr', action='store_true')
    parser.add_argument('--source-root', required=True,
                        help='Checkout required for fail-closed release policy')
    parser.add_argument('--approve-sensitive-review', action='store_true')
    parser.add_argument('--verification-report', required=True, help='Passing Docker verification JSON for this exact ZIP')
    args = parser.parse_args()
    print(json.dumps(publish(args.repository, args.base_branch, args.release_zip,
                             approve=args.approve_draft_pr, token=os.getenv('GITHUB_TOKEN'),
                             evidence_path=args.verification_report,
                             source_root=args.source_root,
                             approve_sensitive=args.approve_sensitive_review), indent=2))

if __name__ == '__main__':
    sys.exit(main())
