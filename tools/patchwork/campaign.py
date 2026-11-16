"""PATCHWORK V1: bounded repository-wide repair campaigns.

Read-only scanning, optional explicitly authorized AI proposals, and a
single review bundle. No execution, patch application, or deployment.
"""
import argparse
import ast
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from proposal_engine import _target, IGNORED
from repair import propose_missing_colon
from ai_repair import propose_with_ai

MAX_FILES = 500
MAX_AI_FILES = 5
MAX_FILE_BYTES = 40_000

def discover(root, max_files=MAX_FILES):
    base = Path(root).resolve(strict=True)
    if not base.is_dir():
        raise ValueError('Root must be a directory')
    if not 1 <= max_files <= MAX_FILES:
        raise ValueError('max_files must be between 1 and 500')
    candidates = []
    for path in base.rglob('*.py'):
        rel = path.relative_to(base)
        if any(part in IGNORED for part in rel.parts) or path.is_symlink():
            continue
        if not path.is_file():
            continue
        candidates.append(rel.as_posix())
        if len(candidates) > max_files:
            raise ValueError('Repository exceeds scan limit; select a smaller root')
    return sorted(candidates)

def build_campaign(root, *, max_files=MAX_FILES, ai=False, confirm_upload=False,
                   api_key=None, model='gpt-4.1-mini', transport=None):
    if ai and not confirm_upload:
        raise ValueError('Explicit source upload consent required')
    if ai and not api_key:
        raise ValueError('API key required for AI repair campaign')
    base = Path(root).resolve(strict=True)
    files = discover(base, max_files)
    findings = []
    for rel in files:
        try:
            path = _target(base, rel)
            if path.stat().st_size > MAX_FILE_BYTES:
                findings.append({'file': rel, 'status': 'skipped_large', 'bytes': path.stat().st_size})
                continue
            source = path.read_text(encoding='utf-8')
            ast.parse(source, filename=rel)
        except SyntaxError as exc:
            findings.append({'file': rel, 'status': 'syntax_error', 'line': exc.lineno,
                             'message': str(exc.msg)[:200]})
        except (OSError, UnicodeError, ValueError) as exc:
            findings.append({'file': rel, 'status': 'unreadable', 'message': type(exc).__name__})
    errors = [f for f in findings if f['status'] == 'syntax_error']
    proposals = []
    for finding in errors:
        rel = finding['file']
        path = _target(base, rel)
        source = path.read_text(encoding='utf-8')
        digest = hashlib.sha256(source.encode('utf-8')).hexdigest()
        rule = propose_missing_colon(base, rel)
        if rule['status'] == 'proposed':
            proposals.append({'file': rel, 'engine': 'rule', 'source_sha256': digest,
                              'status': 'ready_for_review', 'diff': rule['diff'],
                              'explanation': rule['explanation'], 'applied': False})
            continue
        if ai and len([p for p in proposals if p['engine'] == 'ai']) < MAX_AI_FILES:
            try:
                result = propose_with_ai(base, rel, api_key=api_key, model=model, transport=transport)
                proposals.append({'file': rel, 'engine': 'ai', 'source_sha256': digest,
                                  'status': result['status'], 'diff': result.get('diff', ''),
                                  'explanation': result.get('explanation', '')[:500],
                                  'applied': False})
            except ValueError as exc:
                proposals.append({'file': rel, 'engine': 'ai', 'status': 'provider_error',
                                  'message': str(exc)[:120], 'applied': False})
    return {'schema': 'patchwork-campaign-v1', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'root_name': base.name, 'files_scanned': len(files),
            'syntax_errors': len(errors), 'findings': findings, 'proposals': proposals,
            'ai_enabled': ai, 'source_uploaded': bool(ai and any(p['engine']=='ai' for p in proposals)),
            'tests_run': False, 'applied': False, 'deployments': 0,
            'warning': 'Read-only review. Syntax checks do not establish code correctness.'}

def main():
    parser = argparse.ArgumentParser(description='PATCHWORK repository repair campaign (read-only)')
    parser.add_argument('repository')
    parser.add_argument('--output', required=True, help='New JSON report path; never overwrites')
    parser.add_argument('--max-files', type=int, default=MAX_FILES)
    parser.add_argument('--ai', action='store_true', help='Enable OpenAI repair suggestions')
    parser.add_argument('--confirm-upload', action='store_true', help='Consent to upload affected source files')
    parser.add_argument('--model', default=os.getenv('PATCHWORK_MODEL', 'gpt-4.1-mini'))
    args = parser.parse_args()
    report = build_campaign(args.repository, max_files=args.max_files, ai=args.ai,
                            confirm_upload=args.confirm_upload, api_key=os.getenv('OPENAI_API_KEY'),
                            model=args.model)
    destination = Path(args.output).expanduser().absolute()
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as out:
        json.dump(report, out, indent=2)
    print(json.dumps({'output': str(destination), 'files_scanned': report['files_scanned'],
                      'syntax_errors': report['syntax_errors'], 'proposals': len(report['proposals'])}))
    return 0

if __name__ == '__main__':
    sys.exit(main())
