"""PATCHWORK V5: isolated, approval-gated repair verification.

Creates a private temporary copy of a Python repository, applies verified
staged replacements only to that copy, then runs unittest in a locked-down
Docker container. Never executes project code on the host, touches original
source, merges or deploys. Requires locally installed Docker.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from github_publisher import load_release
from proposal_engine import _target, IGNORED

MAX_COPY_FILES = 3000
MAX_COPY_BYTES = 30 * 1024 * 1024
DEFAULT_IMAGE = 'python:3.11-alpine'
TIMEOUT_SECONDS = 120

def copy_sources(root, destination):
    count = total = 0
    for path in root.rglob('*'):
        rel = path.relative_to(root)
        if any(part in IGNORED or part == '.git' for part in rel.parts) or path.is_symlink():
            continue
        if not path.is_file():
            continue
        # Only Python sources are needed for the bounded unittest suite.
        if path.suffix != '.py':
            continue
        size = path.stat().st_size
        count += 1
        total += size
        if count > MAX_COPY_FILES or total > MAX_COPY_BYTES:
            raise ValueError('Repository exceeds isolated verification limits')
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    return count

def verify(root, release_zip, *, approve=False, image=DEFAULT_IMAGE,
           timeout=TIMEOUT_SECONDS, runner=subprocess.run):
    if not approve:
        raise ValueError('Explicit --approve-isolated-tests required')
    if not isinstance(timeout, int) or not 10 <= timeout <= TIMEOUT_SECONDS:
        raise ValueError('Invalid timeout')
    if image != DEFAULT_IMAGE:
        raise ValueError('Only the allowlisted Python container image is supported')
    base = Path(root).resolve(strict=True)
    if not base.is_dir():
        raise ValueError('Repository root must be a directory')
    release_digest = hashlib.sha256(Path(release_zip).read_bytes()).hexdigest()
    candidates = load_release(release_zip)
    # Validate all source hashes before staging any files.
    for rel, replacement, digest in candidates:
        path = _target(base, rel)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Source changed since staged release: ' + rel)
    with tempfile.TemporaryDirectory(prefix='patchwork-verify-') as temp:
        workspace = Path(temp) / 'workspace'
        workspace.mkdir()
        copied = copy_sources(base, workspace)
        for rel, replacement, _ in candidates:
            staged = workspace / rel
            if not staged.is_file():
                raise ValueError('Staged source file missing: ' + rel)
            staged.write_bytes(replacement)
        # No network, no additional Linux capabilities, no privilege escalation,
        # limited resources, read-only root and workspace, writable isolated tmpfs.
        command = ['docker', 'run', '--rm', '--network', 'none', '--cap-drop', 'ALL',
                   '--security-opt', 'no-new-privileges', '--pids-limit', '128',
                   '--memory', '512m', '--cpus', '1', '--read-only',
                   '--tmpfs', '/tmp:rw,noexec,nosuid,size=32m',
                   '--mount', 'type=bind,src=' + str(workspace) + ',dst=/workspace,readonly',
                   '--workdir', '/workspace', '--user', '65534:65534',
                   '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'PYTHONPATH=/workspace',
                   image, 'python', '-m', 'unittest', 'discover', '-p', 'test_*.py', '-v']
        started = time.monotonic()
        try:
            result = runner(command, capture_output=True, text=True, timeout=timeout, check=False)
            exit_code = result.returncode
            stdout = result.stdout[-12000:]
            stderr = result.stderr[-12000:]
            # unittest returns zero even when no tests are discovered.
            import re
            discovered = re.search(r'Ran (\\d+) tests? in', stdout + '\\n' + stderr)
            tests_count = int(discovered.group(1)) if discovered else 0
            status = 'passed' if exit_code == 0 and tests_count > 0 else 'failed'
        except subprocess.TimeoutExpired:
            exit_code, stdout, stderr, status, tests_count = None, '', 'Isolated test timeout', 'timeout', 0
        except OSError:
            exit_code, stdout, stderr, status, tests_count = None, '', 'Docker unavailable', 'unavailable', 0
        return {'schema': 'patchwork-isolated-verification-v1', 'status': status,
                'release_sha256': release_digest, 'tests_discovered': tests_count,
                'exit_code': exit_code, 'elapsed_seconds': round(time.monotonic()-started, 2),
                'files_copied': copied, 'replacements_staged': len(candidates),
                'stdout_tail': stdout, 'stderr_tail': stderr,
                'source_repository_modified': False, 'tests_executed_on_host': False,
                'merged': False, 'deployed': False,
                'warning': 'A passing test suite is not proof of security or correctness. '
                           'Docker isolation is not a security boundary for actively malicious code.'}

def main():
    parser = argparse.ArgumentParser(description='Verify reviewed PATCHWORK repairs in Docker')
    parser.add_argument('repository')
    parser.add_argument('release_zip')
    parser.add_argument('--approve-isolated-tests', action='store_true')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = verify(args.repository, args.release_zip, approve=args.approve_isolated_tests)
    destination = Path(args.output).expanduser().absolute()
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({'status': report['status'], 'report': str(destination)}))
    if report['status'] != 'passed':
        raise SystemExit(1)

if __name__ == '__main__':
    main()
