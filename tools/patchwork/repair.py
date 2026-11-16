"""PATCHWORK repair proposals: conservative, review-only unified diffs.

Supports one narrow syntax repair: a missing colon on a Python compound
statement. Does not execute source code, change files, or deploy anything.
"""
import ast
import difflib
from pathlib import Path

KEYWORDS = ('if ', 'elif ', 'else', 'for ', 'while ', 'def ', 'async def ', 'class ', 'try', 'except', 'finally', 'with ', 'async with ')

def propose_missing_colon(root, relative_path):
    root = Path(root).resolve(strict=True)
    path = (root / relative_path).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file() or path.is_symlink():
        raise ValueError('Invalid repository file')
    if path.suffix != '.py' or path.stat().st_size > 1024 * 1024:
        raise ValueError('Only Python files up to 1 MB are supported')
    original = path.read_text(encoding='utf-8')
    try:
        ast.parse(original)
        return {'status': 'clean', 'diff': '', 'explanation': 'No Python syntax error detected'}
    except SyntaxError as exc:
        line_no = exc.lineno
        if not line_no:
            return {'status': 'unsupported', 'diff': '', 'explanation': 'No reliable error location'}
        lines = original.splitlines(keepends=True)
        line = lines[line_no - 1]
        stripped = line.strip()
        # Avoid guessing on comments, multiline headers, and existing colons.
        if ('#' in stripped or ':' in stripped or '\\' in stripped or
            not stripped.startswith(KEYWORDS) or not stripped.endswith((')', 'else', 'try', 'finally'))):
            return {'status': 'unsupported', 'diff': '', 'explanation': 'Manual review required'}
        candidate = list(lines)
        ending = '\r\n' if line.endswith('\r\n') else ('\n' if line.endswith('\n') else '')
        candidate[line_no - 1] = line[:-len(ending)] + ':' + ending if ending else line + ':'
        try:
            ast.parse(''.join(candidate))
        except SyntaxError:
            return {'status': 'unsupported', 'diff': '', 'explanation': 'Candidate did not pass Python syntax validation'}
        diff = ''.join(difflib.unified_diff(lines, candidate, fromfile='a/' + str(relative_path), tofile='b/' + str(relative_path)))
        return {'status': 'proposed', 'diff': diff, 'explanation': 'Suggested missing colon; review before applying. Syntax validation is not a behavioral test.', 'applied': False}
