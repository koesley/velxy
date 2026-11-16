"""PATCHWORK V13: real Docker integration smoke test with a trusted fixture.

Runs a deterministic two-file staged repair through the actual isolated
Docker verifier. Only the self-contained fixture is executed in Docker;
no external project code, GitHub writes, or secrets are involved.
"""
import hashlib
import json
import tempfile
from pathlib import Path

from release_gate import prepare_release
from release_policy import analyze
from isolated_verify import verify
from github_publisher import validate_test_evidence

ORIGINAL = '''def answer():
    return 1
'''
REPLACEMENT = '''def answer():
    return 42
'''
TEST = '''import unittest
from app import answer

class AnswerTests(unittest.TestCase):
    def test_answer(self):
        self.assertEqual(answer(), 42)
'''

def run():
    with tempfile.TemporaryDirectory(prefix='patchwork-real-docker-') as temp:
        work = Path(temp)
        repo = work / 'repo'
        repo.mkdir()
        (repo / 'app.py').write_text(ORIGINAL, encoding='utf-8')
        (repo / 'test_app.py').write_text(TEST, encoding='utf-8')
        original_digest = hashlib.sha256((repo / 'app.py').read_bytes()).hexdigest()
        bundle = work / 'review.json'
        bundle.write_text(json.dumps({
            'schema':'patchwork-review-v1', 'file':'app.py',
            'original':ORIGINAL, 'replacement':REPLACEMENT
        }), encoding='utf-8')
        archive = work / 'release.zip'
        prepare_release(repo, [bundle], archive, approve=True)
        policy = analyze(repo, archive)
        if policy['status'] != 'eligible':
            raise AssertionError('Trusted fixture failed policy: ' + str(policy['findings']))
        report = verify(repo, archive, approve=True)
        if report['status'] != 'passed' or report['tests_discovered'] < 1:
            raise AssertionError('Actual Docker verification failed: ' + json.dumps(report))
        report_path = work / 'verification.json'
        report_path.write_text(json.dumps(report), encoding='utf-8')
        validate_test_evidence(archive, report_path)
        if hashlib.sha256((repo / 'app.py').read_bytes()).hexdigest() != original_digest:
            raise AssertionError('Original source changed')
        if (repo / 'app.py').read_text(encoding='utf-8') != ORIGINAL:
            raise AssertionError('Original file contents changed')
        return {
            'schema':'patchwork-real-docker-integration-v1',
            'status':'passed',
            'tests_discovered':report['tests_discovered'],
            'release_sha256':report['release_sha256'],
            'source_unchanged':True,
            'docker_executed':True,
            'github_requests_made':False,
            'merged':False,
            'deployed':False
        }

if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
