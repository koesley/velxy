"""PATCHWORK V7: GitHub-native immutable-commit CI verification gate.

Read-only inspection of a draft PR's current head commit and its GitHub
Checks API results. This is not a merge operation and cannot configure
branch protection. Require repository administrators to enforce this
check through GitHub rulesets before production use.
"""
import argparse
import json
import os
import re
import sys

from github_publisher import api

REQUIRED_CHECKS = ('patchwork-repair-ci',)
SHA_PATTERN = re.compile(r'^[0-9a-f]{40}$')

def inspect_pr(repository, number, *, token, expected_sha=None,
               required_checks=REQUIRED_CHECKS, request=api):
    if not token:
        raise ValueError('GitHub token required')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Invalid repository')
    if not isinstance(number, int) or number < 1:
        raise ValueError('Invalid pull request number')
    if not required_checks or len(set(required_checks)) != len(required_checks):
        raise ValueError('At least one unique required check is needed')
    prefix = '/repos/' + repository
    pr = request(token, 'GET', prefix + '/pulls/' + str(number))
    if pr.get('state') != 'open' or not pr.get('draft', False):
        raise ValueError('Only open draft PRs are supported')
    head = pr.get('head', {})
    sha = head.get('sha')
    if not isinstance(sha, str) or not SHA_PATTERN.fullmatch(sha):
        raise ValueError('Invalid PR head SHA')
    if expected_sha is not None and sha != expected_sha:
        raise ValueError('PR head changed since verification request')
    if head.get('repo', {}).get('full_name') != repository:
        raise ValueError('Forked PR heads are not supported')
    # Query checks for the exact immutable commit, not a branch name.
    checks = request(token, 'GET', prefix + '/commits/' + sha + '/check-runs?per_page=100')
    if checks.get('total_count', 0) > 100:
        raise ValueError('Too many checks to evaluate safely')
    runs = checks.get('check_runs')
    if not isinstance(runs, list):
        raise ValueError('Missing GitHub check runs')
    observed = {}
    for run in runs:
        name = run.get('name')
        if name in required_checks:
            observed.setdefault(name, []).append({
                'status': run.get('status'), 'conclusion': run.get('conclusion'),
                'head_sha': run.get('head_sha'), 'app_slug': (run.get('app') or {}).get('slug')})
    outcomes = {}
    for name in required_checks:
        matches = observed.get(name, [])
        outcomes[name] = ('passed' if len(matches) == 1
                          and matches[0]['status'] == 'completed'
                          and matches[0]['conclusion'] == 'success'
                          and matches[0]['head_sha'] == sha
                          and matches[0]['app_slug'] == 'github-actions'
                          else 'blocked')
    return {'schema': 'patchwork-github-ci-gate-v1', 'repository': repository,
            'pull_request': number, 'head_sha': sha, 'checks': outcomes,
            'status': 'passed' if all(v == 'passed' for v in outcomes.values()) else 'blocked',
            'merged': False, 'deployed': False,
            'warning': 'Read-only status check. GitHub branch rulesets must separately enforce checks and review.'}

def main():
    parser = argparse.ArgumentParser(description='Inspect immutable GitHub PR CI status')
    parser.add_argument('repository')
    parser.add_argument('pull_request', type=int)
    parser.add_argument('--expected-sha', required=True, help='Immutable 40-character PR head commit')
    args = parser.parse_args()
    report = inspect_pr(args.repository, args.pull_request,
                        token=os.getenv('GITHUB_TOKEN'), expected_sha=args.expected_sha)
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'passed' else 1

if __name__ == '__main__':
    sys.exit(main())
