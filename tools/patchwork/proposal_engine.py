"""PATCHWORK V0.3: bounded, offline repair-plan validation.

Accepts a candidate replacement supplied by a human or future AI provider.
Never writes to the source repository and never executes untrusted project code.
"""
import ast
import difflib
import hashlib
from pathlib import Path

MAX_BYTES = 1024 * 1024
IGNORED = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', 'dist', 'build'}

def _target(root, relative_path):
    base = Path(root).resolve(strict=True)
    if not base.is_dir():
        raise ValueError('Repository root must be a directory')
    rel = Path(relative_path)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts or any(p in IGNORED for p in rel.parts):
        raise ValueError('Invalid or excluded path')
    path = base.joinpath(rel)
    if path.is_symlink() or not path.resolve(strict=True).is_relative_to(base):
        raise ValueError('File must be within the repository')
    if not path.is_file() or path.suffix != '.py' or path.stat().st_size > MAX_BYTES:
        raise ValueError('Only Python source files up to 1 MB are supported')
    return path

def validate_proposal(root, relative_path, replacement, expected_sha256=None):
    """Validate a proposed full-file replacement; return a diff, never apply it."""
    if not isinstance(replacement, str) or len(replacement.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Replacement must be UTF-8 text up to 1 MB')
    path = _target(root, relative_path)
    original = path.read_text(encoding='utf-8')
    digest = hashlib.sha256(original.encode('utf-8')).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError('Source has changed since proposal was prepared')
    try:
        ast.parse(replacement, filename=str(relative_path))
    except SyntaxError as exc:
        return {'status': 'rejected', 'reason': 'Replacement has a Python syntax error', 'line': exc.lineno, 'applied': False}
    if replacement == original:
        return {'status': 'unchanged', 'diff': '', 'source_sha256': digest, 'applied': False}
    diff = ''.join(difflib.unified_diff(
        original.splitlines(keepends=True), replacement.splitlines(keepends=True),
        fromfile='a/' + str(relative_path), tofile='b/' + str(relative_path)))
    return {'status': 'ready_for_review', 'diff': diff, 'source_sha256': digest,
            'replacement_sha256': hashlib.sha256(replacement.encode('utf-8')).hexdigest(),
            'syntax_valid': True, 'tests_run': False, 'applied': False,
            'warning': 'Syntax validation does not establish safety or correctness. Human approval required.'}
