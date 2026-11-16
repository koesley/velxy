"""PATCHWORK read-only diagnostics with conservative repair guidance.

No code execution, network calls, automatic changes, or AI model calls.
"""
import ast
from pathlib import Path

SKIP = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', 'dist', 'build'}
MAX_FILE_BYTES = 1024 * 1024

def diagnose(root):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Repository must be a directory')
    findings = []
    scanned = 0
    for path in sorted(root.rglob('*.py')):
        if path.is_symlink() or any(part in SKIP for part in path.relative_to(root).parts):
            continue
        rel = str(path.relative_to(root))
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                findings.append({'file': rel, 'severity': 'warning', 'kind': 'size', 'message': 'File exceeds scan size limit', 'suggestion': 'Review this file manually'})
                continue
            source = path.read_text(encoding='utf-8')
            scanned += 1
            ast.parse(source, filename=rel)
        except SyntaxError as exc:
            findings.append({'file': rel, 'line': exc.lineno, 'column': exc.offset, 'severity': 'error', 'kind': 'syntax', 'message': exc.msg, 'suggestion': 'Inspect the indicated line and adjacent lines; check brackets, indentation, and missing punctuation'})
        except (OSError, UnicodeError) as exc:
            findings.append({'file': rel, 'severity': 'warning', 'kind': 'read', 'message': type(exc).__name__, 'suggestion': 'Check permissions and UTF-8 encoding'})
    return {'python_files_scanned': scanned, 'findings': findings, 'read_only': True, 'ai_enabled': False}
