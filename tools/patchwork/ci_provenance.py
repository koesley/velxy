"""PATCHWORK V23: read-only GitHub Actions workflow provenance verification.

Verifies a check run is linked to a completed successful Actions job and
workflow run for the exact immutable PR head commit. Not a signed attestation.
"""
import re
from github_publisher import api

SHA = re.compile(r'^[0-9a-f]{40}$')
REPO = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
WORKFLOW = '.github/workflows/patchwork-repair-pr.yml'
CHECK = 'patchwork-repair-ci'

def verify_ci_provenance(repository, pull_request, *, token, expected_sha,
                         request=api, workflow_path=WORKFLOW):
    if not token or not REPO.fullmatch(repository):
        raise ValueError('Valid repository and token required')
    if not isinstance(pull_request,int) or isinstance(pull_request,bool) or pull_request<1:
        raise ValueError('Invalid pull request number')
    if not isinstance(expected_sha,str) or not SHA.fullmatch(expected_sha):
        raise ValueError('Invalid expected SHA')
    if workflow_path != WORKFLOW:
        raise ValueError('Unrecognized required workflow')
    prefix='/repos/'+repository
    pr=request(token,'GET',prefix+'/pulls/'+str(pull_request))
    head=pr.get('head') or {}
    if (pr.get('state')!='open' or pr.get('draft') is not True
            or head.get('sha')!=expected_sha
            or (head.get('repo') or {}).get('full_name')!=repository):
        raise ValueError('PR must be an open same-repository draft at expected SHA')
    checks=request(token,'GET',prefix+'/commits/'+expected_sha+'/check-runs?per_page=100')
    if checks.get('total_count',0)>100 or not isinstance(checks.get('check_runs'),list):
        raise ValueError('Check run list incomplete')
    matches=[c for c in checks['check_runs'] if c.get('name')==CHECK]
    if len(matches)!=1:
        raise ValueError('Expected exactly one required CI check')
    check=matches[0]
    if (check.get('status')!='completed' or check.get('conclusion')!='success'
            or check.get('head_sha')!=expected_sha
            or (check.get('app') or {}).get('slug')!='github-actions'):
        raise ValueError('Required check has not passed for expected commit')
    check_id=check.get('id')
    if not isinstance(check_id,int) or isinstance(check_id,bool) or check_id<1:
        raise ValueError('Missing check run identity')
    runs=request(token,'GET',prefix+'/actions/runs?head_sha='+expected_sha+'&per_page=100')
    if runs.get('total_count',0)>100 or not isinstance(runs.get('workflow_runs'),list):
        raise ValueError('Workflow run list incomplete')
    valid=[]
    for run in runs['workflow_runs']:
        if (run.get('head_sha')!=expected_sha or run.get('path')!=workflow_path
                or run.get('event')!='pull_request' or run.get('status')!='completed'
                or run.get('conclusion')!='success'):
            continue
        run_id=run.get('id')
        if not isinstance(run_id,int) or isinstance(run_id,bool) or run_id<1:
            continue
        jobs=request(token,'GET',prefix+'/actions/runs/'+str(run_id)+'/jobs?per_page=100')
        if jobs.get('total_count',0)>100 or not isinstance(jobs.get('jobs'),list):
            raise ValueError('Workflow job list incomplete')
        for job in jobs['jobs']:
            if (job.get('check_run_url','').endswith('/check-runs/'+str(check_id))
                    and job.get('name')==CHECK and job.get('status')=='completed'
                    and job.get('conclusion')=='success' and job.get('head_sha')==expected_sha):
                valid.append((run_id,job.get('id')))
    if len(valid)!=1:
        raise ValueError('No unique successful workflow/job provenance for required check')
    return {'schema':'patchwork-github-actions-provenance-v1',
            'status':'verified','repository':repository,'pull_request':pull_request,
            'head_sha':expected_sha,'workflow_path':workflow_path,
            'workflow_run_id':valid[0][0],'job_id':valid[0][1],
            'github_writes_performed':False,'merged':False,'deployed':False,
            'warning':'GitHub API provenance, not signed attestation or enforced branch protection.'}
