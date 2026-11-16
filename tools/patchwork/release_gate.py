"""PATCHWORK V3: approval-gated, offline repair release packaging.

Consumes review bundles, verifies source hashes, stages candidate files in a
separate directory and creates a ZIP for human review. Never executes code,
changes the repository, pushes commits or deploys.
"""
import argparse
import ast
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from proposal_engine import _target

MAX_BUNDLE = 4 * 1024 * 1024
MAX_FILES = 25
MAX_TOTAL = 4 * 1024 * 1024

def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def prepare_release(root, bundle_paths, output, *, approve=False):
    if not approve:
        raise ValueError('Explicit --approve-staging is required')
    if not 1 <= len(bundle_paths) <= MAX_FILES:
        raise ValueError('Choose between 1 and 25 review bundles')
    root = Path(root).resolve(strict=True)
    output = Path(output).expanduser().absolute()
    if output.exists():
        raise ValueError('Output already exists')
    if output.is_relative_to(root):
        raise ValueError('Output must be outside the source repository')
    candidates = []
    seen = set()
    total = 0
    for bundle_path in bundle_paths:
        bundle_file = Path(bundle_path).resolve(strict=True)
        if bundle_file.stat().st_size > MAX_BUNDLE:
            raise ValueError('Bundle too large')
        bundle = json.loads(bundle_file.read_text(encoding='utf-8'))
        if bundle.get('schema') != 'patchwork-review-v1':
            raise ValueError('Unsupported review bundle schema')
        rel = bundle.get('file')
        original = bundle.get('original')
        replacement = bundle.get('replacement')
        if not isinstance(rel, str) or not isinstance(original, str) or not isinstance(replacement, str):
            raise ValueError('Invalid review bundle')
        if rel in seen:
            raise ValueError('Duplicate target file')
        seen.add(rel)
        path = _target(root, rel)
        if path.read_bytes() != original.encode('utf-8'):
            raise ValueError('Original file changed since review: ' + rel)
        if original == replacement:
            raise ValueError('Unchanged replacement: ' + rel)
        ast.parse(replacement, filename=rel)
        data = replacement.encode('utf-8')
        total += len(data)
        if total > MAX_TOTAL:
            raise ValueError('Release exceeds 4 MB')
        candidates.append((rel, data, sha(original), sha(replacement)))
    manifest = {
        'schema': 'patchwork-staged-release-v1',
        'files': [{'file': rel, 'original_sha256': old, 'replacement_sha256': new}
                  for rel, _, old, new in candidates],
        'approved_for_staging': True, 'approved_for_merge': False,
        'tests_run': False, 'source_repository_modified': False,
        'automatically_deployed': False,
        'warning': 'Staged code has only been syntax-checked. Review and test before merging.'
    }
    # ZIP entries are explicitly validated relative repository paths, never extracted.
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('patchwork-manifest.json', json.dumps(manifest, indent=2))
                for rel, data, _, _ in candidates:
                    archive.writestr('proposed/' + rel, data)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return manifest

def main():
    parser = argparse.ArgumentParser(description='Stage reviewed PATCHWORK fixes in a ZIP, never apply them')
    parser.add_argument('repository')
    parser.add_argument('bundles', nargs='+')
    parser.add_argument('--output', required=True)
    parser.add_argument('--approve-staging', action='store_true',
                        help='Explicitly authorize creating a review ZIP outside the repository')
    args = parser.parse_args()
    result = prepare_release(args.repository, args.bundles, args.output, approve=args.approve_staging)
    print(json.dumps({'staged_files': len(result['files']), 'output': args.output,
                      'repository_modified': False}))

if __name__ == '__main__':
    sys.exit(main())
