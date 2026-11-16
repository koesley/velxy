"""PATCHWORK V9: fail-closed release policy and blast-radius analyzer.

Static, read-only policy analysis of an approved staged repair archive.
No source execution, repository modification, GitHub writes, or deployments.
"""
import ast
from collections import Counter
import hashlib
import json
import re
from pathlib import Path

from github_publisher import load_release
from proposal_engine import _target

SENSITIVE = ('auth', 'security', 'payment', 'billing', 'secret', 'credential',
             'permission', 'token', 'session', 'migration', 'database')
DANGEROUS = {'eval', 'exec', 'compile', '__import__'}
MAX_CHANGED_LINES = 1200
MAX_FILES = 25

def _calls(tree):
    found = Counter()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            found[func.id] += 1
        elif isinstance(func, ast.Attribute):
            parts = [func.attr]
            obj = func.value
            while isinstance(obj, ast.Attribute):
                parts.append(obj.attr)
                obj = obj.value
            if isinstance(obj, ast.Name):
                parts.append(obj.id)
            found['.'.join(reversed(parts))] += 1
    return found

def _imports(tree):
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split('.')[0])
    return found

def analyze(root, archive_path, *, max_changed_lines=MAX_CHANGED_LINES):
    if not isinstance(max_changed_lines, int) or not 1 <= max_changed_lines <= MAX_CHANGED_LINES:
        raise ValueError('Invalid change budget')
    base = Path(root).resolve(strict=True)
    candidates = load_release(archive_path)
    if len(candidates) > MAX_FILES or len({rel for rel, _, _ in candidates}) != len(candidates):
        raise ValueError('Invalid release file count or duplicate paths')
    findings = []
    changed_total = 0
    summaries = []
    for rel, replacement, expected in candidates:
        source = _target(base, rel).read_bytes()
        if hashlib.sha256(source).hexdigest() != expected:
            raise ValueError('Stale source: ' + rel)
        try:
            old = source.decode('utf-8')
            new = replacement.decode('utf-8')
            old_ast = ast.parse(old, filename=rel)
            new_ast = ast.parse(new, filename=rel)
        except (UnicodeDecodeError, SyntaxError) as exc:
            raise ValueError('Invalid Python source in ' + rel) from exc
        import difflib
        additions = removals = 0
        for line in difflib.ndiff(old.splitlines(), new.splitlines()):
            if line.startswith('+ '):
                additions += 1
            elif line.startswith('- '):
                removals += 1
        changed_total += additions + removals
        if old == new:
            findings.append({'file':rel,'severity':'block','rule':'no-op',
                             'message':'Replacement does not change source'})
        if any(part.lower().find(word) >= 0 for part in Path(rel).parts for word in SENSITIVE):
            findings.append({'file':rel,'severity':'review','rule':'sensitive-path',
                             'message':'Sensitive module requires specialist review'})
        # Compare occurrence counts, not just membership: a second exec() is
        # dangerous even when the original module already contained one.
        old_calls = _calls(old_ast)
        new_calls = _calls(new_ast)
        introduced = new_calls - old_calls
        high_risk = DANGEROUS | {'os.system', 'subprocess.Popen', 'subprocess.run',
                                 'subprocess.call', 'pickle.loads', 'yaml.load',
                                 'shutil.rmtree', 'os.remove', 'os.unlink',
                                 'os.chmod', 'os.chown', 'subprocess.check_output',
                                 'subprocess.check_call'}
        flagged = sorted(x for x, count in introduced.items() if count > 0 and x in high_risk)
        if flagged:
            findings.append({'file':rel,'severity':'block','rule':'dangerous-call',
                             'message':'New high-risk call(s): ' + ', '.join(flagged)})
        added_imports = sorted(_imports(new_ast) - _imports(old_ast))
        if added_imports:
            findings.append({'file':rel,'severity':'review','rule':'new-dependency',
                             'message':'New imports: ' + ', '.join(added_imports)})
        summaries.append({'file':rel,'added_lines':additions,'removed_lines':removals,
                          'new_imports':added_imports,'new_high_risk_calls':flagged})
    if changed_total > max_changed_lines:
        findings.append({'file':None,'severity':'block','rule':'change-budget',
                         'message':'Total changed lines exceed configured budget'})
    blocks = sum(f['severity']=='block' for f in findings)
    reviews = sum(f['severity']=='review' for f in findings)
    return {'schema':'patchwork-release-policy-v1',
            'release_sha256':hashlib.sha256(Path(archive_path).read_bytes()).hexdigest(),
            'status':'blocked' if blocks else ('needs_review' if reviews else 'eligible'),
            'blockers':blocks,'review_flags':reviews,'changed_lines':changed_total,
            'files':summaries,'findings':findings,
            'source_repository_modified':False,'code_executed':False,
            'warning':'Heuristic policy checks are not a security audit. Human review is mandatory.'}

def main():
    import argparse
    parser=argparse.ArgumentParser(description='Analyze blast radius of staged PATCHWORK repairs')
    parser.add_argument('repository')
    parser.add_argument('release_zip')
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    result=analyze(args.repository,args.release_zip)
    import os
    fd=os.open(Path(args.output).absolute(),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2)
    print(json.dumps({'status':result['status'],'blockers':result['blockers'],
                      'review_flags':result['review_flags']}))
    if result['status']=='blocked':
        raise SystemExit(1)

if __name__=='__main__':
    main()
