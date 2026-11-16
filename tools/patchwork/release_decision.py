"""Read-only PATCHWORK release decision: independently recheck publication and CI.

This is a review-readiness decision, NOT permission to merge or deploy.
All evidence is re-fetched from GitHub; caller-supplied status flags are ignored.
"""
import argparse
import json
import os
import re
from pathlib import Path

from github_publisher import api
from publication_postflight import verify_publication
from ci_provenance import verify_ci_provenance

REPO = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
SHA = re.compile(r'^[a-f0-9]{40}$')

def assess_release(repository, base_branch, archive_path, publication,
                   pull_request, *, token, request=api):
    """Return an auditable fail-closed decision without making GitHub writes."""
    if not token or not REPO.fullmatch(repository):
        raise ValueError('Valid GitHub repository and token required')
    if not isinstance(pull_request, int) or isinstance(pull_request, bool) or pull_request < 1:
        raise ValueError('Valid pull request number required')
    if not isinstance(publication, dict):
        raise ValueError('Publication record required')
    head_sha = publication.get('commit_sha')
    if not isinstance(head_sha, str) or not SHA.fullmatch(head_sha):
        raise ValueError('Valid publication commit SHA required')
    checks = {'publication_integrity': 'blocked', 'github_actions_provenance': 'blocked',
              'final_pr_identity': 'blocked'}
    failures = []
    details = {}
    try:
        verified = verify_publication(repository, base_branch, archive_path,
                                      publication, token=token, request=request)
        if verified.get('status') != 'verified' or verified.get('head_sha') != head_sha:
            raise ValueError('Unexpected publication verification result')
        checks['publication_integrity'] = 'passed'
        details['publication'] = verified
    except Exception as exc:
        failures.append('Publication verification failed: ' + type(exc).__name__ + ': ' + str(exc))
    # Do not skip CI inspection when the archive is wrong; report independent blockers.
    try:
        provenance = verify_ci_provenance(repository, pull_request,
                                          token=token, expected_sha=head_sha,
                                          request=request)
        if provenance.get('status') != 'verified' or provenance.get('head_sha') != head_sha:
            raise ValueError('Unexpected CI provenance result')
        checks['github_actions_provenance'] = 'passed'
        details['ci_provenance'] = provenance
    except Exception as exc:
        failures.append('CI provenance verification failed: ' + type(exc).__name__ + ': ' + str(exc))
    # Re-read the PR after both inspections: fail closed on head changes,
    # non-draft state, mismatched base, or a different URL.
    try:
        pr = request(token, 'GET', '/repos/' + repository + '/pulls/' + str(pull_request))
        head = pr.get('head') or {}
        base = pr.get('base') or {}
        if (pr.get('state') != 'open' or pr.get('draft') is not True
                or head.get('sha') != head_sha
                or head.get('ref') != publication.get('branch')
                or (head.get('repo') or {}).get('full_name') != repository
                or base.get('ref') != base_branch
                or pr.get('html_url') != publication.get('draft_pull_request')):
            raise ValueError('Draft PR changed or does not match approved release')
        checks['final_pr_identity'] = 'passed'
    except Exception as exc:
        failures.append('Final PR identity verification failed: ' + type(exc).__name__ + ': ' + str(exc))
    passed = all(value == 'passed' for value in checks.values())
    return {'schema': 'patchwork-release-decision-v1',
            'status': 'review_ready' if passed else 'blocked',
            'repository': repository, 'base_branch': base_branch,
            'head_sha': head_sha, 'pull_request': pull_request,
            'release_sha256': publication.get('release_sha256'),
            'checks': checks, 'failures': failures,
            'evidence': details, 'github_writes_performed': False,
            'merge_authorized': False, 'deployment_authorized': False,
            'warning': 'Point-in-time review readiness only; human approval and protected branch rules remain mandatory.'}

def main():
    parser = argparse.ArgumentParser(description='Evaluate PATCHWORK draft repair review readiness (read-only)')
    parser.add_argument('repository')
    parser.add_argument('base_branch')
    parser.add_argument('release_zip')
    parser.add_argument('publication_json', help='JSON result from the atomic publisher')
    parser.add_argument('pull_request', type=int)
    args = parser.parse_args()
    record = json.loads(Path(args.publication_json).read_text(encoding='utf-8'))
    report = assess_release(args.repository, args.base_branch, args.release_zip,
                            record, args.pull_request, token=os.getenv('GITHUB_TOKEN'))
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'review_ready' else 1

if __name__ == '__main__':
    raise SystemExit(main())
