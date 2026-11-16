#!/usr/bin/env python3
"""PATCHWORK: local, read-only Python repository diagnostics."""
import argparse
import ast
import json
from pathlib import Path

SKIP = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', 'dist', 'build'}

def scan(root: Path):
    findings = []
    files = 0
    for path in root.rglob('*.py'):
        if any(p in SKIP for p in path.relative_to(root).parts):
            continue
        files += 1
        try:
            source = path.read_text(encoding='utf-8')
            ast.parse(source, filename=str(path))
        except SyntaxError as e:
            findings.append({'file': str(path.relative_to(root)), 'line': e.lineno, 'severity': 'error', 'kind': 'syntax', 'message': e.msg})
        except (UnicodeError, OSError) as e:
            findings.append({'file': str(path.relative_to(root)), 'severity': 'warning', 'kind': 'read', 'message': str(e)})
    return {'root': str(root), 'python_files_scanned': files, 'findings': findings}

def main():
    parser = argparse.ArgumentParser(description='Read-only Python syntax audit')
    parser.add_argument('repository', help='Local repository directory')
    parser.add_argument('--json', action='store_true', help='Machine-readable output')
    args = parser.parse_args()
    root = Path(args.repository).expanduser().resolve()
    if not root.is_dir():
        parser.error('Repository must be an existing directory')
    report = scan(root)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Scanned {report['python_files_scanned']} Python files in {root}")
        for f in report['findings']:
            print(f"{f['severity'].upper()}: {f['file']}:{f.get('line', '?')}: {f['message']}")
        if not report['findings']:
            print('No Python syntax errors found (not a full security or correctness audit).')
    raise SystemExit(1 if any(f['severity'] == 'error' for f in report['findings']) else 0)

if __name__ == '__main__':
    main()
