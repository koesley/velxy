"""PATCHWORK V2: polyglot repository inventory and security triage.

Static, read-only heuristics for Python, JavaScript, TypeScript, JSON, YAML,
Dockerfiles and dependency manifests. Findings are leads for human review,
not confirmed vulnerabilities. Never runs project code or reads symlinks.
"""
import json
import re
from pathlib import Path

SKIP = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', 'dist', 'build', '.next', '.cache'}
SUFFIXES = {'.py', '.js', '.jsx', '.ts', '.tsx', '.json', '.yaml', '.yml', '.toml'}
NAMES = {'Dockerfile', 'requirements.txt', 'Pipfile', 'package-lock.json', 'package.json', 'pyproject.toml'}
MAX_FILES = 2000
MAX_BYTES = 256 * 1024

PATTERNS = (
    ('python_dynamic_execution', 'high', re.compile(r'\b(?:eval|exec)\s*\('), {'.py'}, 'Dynamic execution can be unsafe with untrusted input'),
    ('python_shell_execution', 'high', re.compile(r'\bsubprocess\.(?:run|Popen|call|check_output)\s*\('), {'.py'}, 'Review subprocess arguments and shell settings'),
    ('js_dynamic_execution', 'high', re.compile(r'\b(?:eval|new\s+Function)\s*\('), {'.js', '.jsx', '.ts', '.tsx'}, 'Review dynamic JavaScript execution'),
    ('js_insecure_dom', 'medium', re.compile(r'\.innerHTML\s*='), {'.js', '.jsx', '.ts', '.tsx'}, 'Review DOM injection and sanitization'),
    ('docker_root_user', 'medium', re.compile(r'^\s*USER\s+root\s*$', re.I | re.M), set(), 'Review container privileges'),
)

def inventory(root, *, max_files=MAX_FILES):
    base = Path(root).resolve(strict=True)
    if not base.is_dir() or not 1 <= max_files <= MAX_FILES:
        raise ValueError('Invalid repository or file limit')
    files = []
    findings = []
    counts = {}
    truncated = False
    for path in base.rglob('*'):
        rel = path.relative_to(base)
        if any(part in SKIP for part in rel.parts) or path.is_symlink() or not path.is_file():
            continue
        if path.suffix not in SUFFIXES and path.name not in NAMES:
            continue
        if len(files) >= max_files:
            truncated = True
            break
        name = rel.as_posix()
        files.append(name)
        kind = path.suffix or path.name
        counts[kind] = counts.get(kind, 0) + 1
        if path.stat().st_size > MAX_BYTES:
            findings.append({'file': name, 'rule': 'oversized_file', 'severity': 'info', 'line': None,
                             'message': 'File skipped because it exceeds the static inspection limit'})
            continue
        try:
            source = path.read_text(encoding='utf-8')
        except (UnicodeError, OSError):
            findings.append({'file': name, 'rule': 'unreadable', 'severity': 'info', 'line': None,
                             'message': 'Could not read as UTF-8'})
            continue
        if path.suffix == '.json':
            try:
                json.loads(source)
            except json.JSONDecodeError as exc:
                findings.append({'file': name, 'rule': 'invalid_json', 'severity': 'medium',
                                 'line': exc.lineno, 'message': 'Invalid JSON syntax'})
        for rule, severity, pattern, suffixes, message in PATTERNS:
            if suffixes and path.suffix not in suffixes:
                continue
            if not suffixes and path.name != 'Dockerfile':
                continue
            for match in list(pattern.finditer(source))[:20]:
                findings.append({'file': name, 'rule': rule, 'severity': severity,
                                 'line': source.count('\n', 0, match.start()) + 1,
                                 'message': message})
        if path.name == 'package.json':
            try:
                package = json.loads(source)
                if isinstance(package, dict):
                    for field in ('dependencies', 'devDependencies'):
                        dependencies = package.get(field)
                        if isinstance(dependencies, dict):
                            for dependency, version in list(dependencies.items())[:500]:
                                if isinstance(version, str) and (version == '*' or version.lower() == 'latest'):
                                    findings.append({'file': name, 'rule': 'unbounded_dependency',
                                                     'severity': 'medium', 'line': None,
                                                     'message': 'Unbounded dependency version: ' + str(dependency)[:100]})
            except (ValueError, TypeError):
                pass
    return {'schema': 'patchwork-polyglot-v1', 'files_inspected': len(files),
            'language_file_counts': counts, 'findings': findings[:5000], 'truncated': truncated,
            'read_only': True, 'tests_run': False,
            'note': 'Heuristic triage only; matches may be false positives and missing matches do not imply safety.'}
