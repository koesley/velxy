"""Infinity V18: export offline Docker-based baseline/candidate validation workbench."""
import hashlib, html, io, json, zipfile
import phoenix_v17
CSS='\n.v18{max-width:960px;margin:auto}.v18 .panel{background:#1b142b;border:1px solid #6a5094;border-radius:16px;padding:24px;margin:16px 0}.v18 a{color:#ddc1ff}'
WORKBENCH=r'''#!/usr/bin/env python3
"""Offline release validator. Never deploys or modifies original sources."""
import argparse, ast, datetime, difflib, hashlib, json, pathlib, shutil, subprocess, sys, tempfile, zipfile
ROOT=pathlib.Path(__file__).resolve().parent
HISTORY=ROOT/'infinity_history'
MAX_SIZE=250000

def sha(data):return hashlib.sha256(data).hexdigest()
def original(name):
    if name not in ('app.py','test_app.py'):raise ValueError('Only app.py/test_app.py are allowed')
    return (ROOT/name).read_bytes()
def load_candidate(path):
    path=pathlib.Path(path).resolve()
    if not path.is_file() or path.stat().st_size>MAX_SIZE:raise ValueError('Missing or oversized candidate')
    data=path.read_bytes();ast.parse(data.decode('utf-8'),filename='app.py')
    return data

def docker_test(app_bytes, label):
    """Run tests with no network, no bind mounts, read-only root, and strict resources."""
    with tempfile.TemporaryDirectory(prefix='infinity-') as tmp:
        root=pathlib.Path(tmp)
        for name in ('test_app.py','schema.json','Dockerfile','compose.evolution.yml'):
            shutil.copyfile(ROOT/name,root/name)
        (root/'app.py').write_bytes(app_bytes)
        cmd=['docker','compose','-f','compose.evolution.yml','run','--build','--rm','--no-deps','evolution-tests']
        try:
            run=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=180,check=False)
            return {'label':label,'status':'PASS' if run.returncode==0 else 'FAIL','exit_code':run.returncode,'output':(run.stdout+'\n'+run.stderr)[-12000:]}
        except (OSError,subprocess.TimeoutExpired) as exc:
            return {'label':label,'status':'UNAVAILABLE','output':str(exc)}

def validate(candidate_path):
    candidate=load_candidate(candidate_path);baseline=original('app.py')
    if candidate==baseline:raise ValueError('No code change')
    HISTORY.mkdir(exist_ok=True)
    baseline_result=docker_test(baseline,'baseline')
    candidate_result=docker_test(candidate,'candidate')
    diff=''.join(difflib.unified_diff(baseline.decode().splitlines(True),candidate.decode().splitlines(True),fromfile='original/app.py',tofile='candidate/app.py'))
    verdict='ELIGIBLE_FOR_MANUAL_REVIEW' if baseline_result['status']=='PASS' and candidate_result['status']=='PASS' else 'BLOCKED'
    rid=sha(baseline+candidate)[:20]
    report={'id':rid,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'baseline_sha256':sha(baseline),'candidate_sha256':sha(candidate),'baseline':baseline_result,'candidate':candidate_result,'verdict':verdict,'limitations':['Passing unit tests do not prove security','Approval is not deployment']}
    (HISTORY/(rid+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    (HISTORY/(rid+'.diff')).write_text(diff,encoding='utf-8')
    (HISTORY/(rid+'.candidate')).write_bytes(candidate)
    print('Validation:',rid,verdict,'\nBaseline:',baseline_result['status'],'Candidate:',candidate_result['status'])
    print('Review:',HISTORY/(rid+'.diff'))
    return report

def release(rid,approve):
    if not approve:raise ValueError('Explicit --approve required')
    if len(rid)!=20 or any(c not in '0123456789abcdef' for c in rid):raise ValueError('Invalid release ID')
    report=json.loads((HISTORY/(rid+'.json')).read_text(encoding='utf-8'))
    if report['verdict']!='ELIGIBLE_FOR_MANUAL_REVIEW':raise ValueError('Release blocked by tests')
    if sha(original('app.py'))!=report['baseline_sha256']:raise ValueError('Original source changed; revalidate')
    candidate=(HISTORY/(rid+'.candidate')).read_bytes()
    if sha(candidate)!=report['candidate_sha256']:raise ValueError('Candidate changed; revalidate')
    dest=HISTORY/('release-'+rid+'.zip')
    if dest.exists():raise ValueError('Release already exists; immutable release retained')
    payload={'app.py':candidate,'test_app.py':original('test_app.py'),'schema.json':(ROOT/'schema.json').read_bytes(),'VALIDATION.json':json.dumps(report,indent=2).encode(),'RELEASE_NOTES.md':b'Validated local release candidate. NOT DEPLOYED. Review authentication, security and rollback before any public release.\n'}
    payload['SHA256SUMS.txt']=''.join(sha(b)+'  '+n+'\n' for n,b in sorted(payload.items())).encode()
    with zipfile.ZipFile(dest,'x',zipfile.ZIP_DEFLATED) as z:
        for n,b in payload.items():z.writestr(n,b)
    print('Release candidate created:',dest,'\nNo deployment performed.')

def main():
    p=argparse.ArgumentParser(description='Infinity offline validation and release candidate builder')
    sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('validate');a.add_argument('candidate')
    b=sub.add_parser('release');b.add_argument('id');b.add_argument('--approve',action='store_true')
    args=p.parse_args()
    if args.action=='validate':validate(args.candidate)
    else:release(args.id,args.approve)
if __name__=='__main__':
    try:main()
    except (ValueError,FileNotFoundError,KeyError,SyntaxError) as exc:print('ERROR:',exc,file=sys.stderr);sys.exit(1)
'''
README='''# VELXTRIA INFINITY V18 — Local Validation Workbench

**Requires Docker Desktop.** No generated application is run inside VELXTRIA's portal process.

1. Prepare `candidate_app.py` alongside this exported package. Review the candidate manually. You may use the V17 Phoenix Ollama diagnosis for guidance; AI suggestions are not automatically applied.
2. Run `python infinity_workbench.py validate candidate_app.py`. This runs baseline and candidate tests in separate disposable Docker Compose test containers (network disabled, read-only filesystem, limited CPU/memory/PIDs). No production secrets or live database are mounted.
3. Open `infinity_history/<id>.diff` and `<id>.json`. Only a baseline PASS and candidate PASS makes a candidate eligible for review. Docker unavailable, timeout or failed tests BLOCK release.
4. After reviewing the diff and test output, run `python infinity_workbench.py release <id> --approve`. This creates an immutable, checksummed ZIP in `infinity_history` without changing the original code or deploying it.
5. Recheck application security, authorization, CSRF, secrets, and migration plans before considering public deployment. These generated applications are local-only and unauthenticated.

**Scope:** This version has deterministic validation, regression gating, manual approval and immutable release candidate packaging. It does NOT automatically repair bugs, retry Ollama patches, deploy, or establish a perfect container security boundary. Docker isolation is defense-in-depth, not a guarantee for hostile code.
'''
def package(c,user_id,app_id):
    base=phoenix_v17.package(c,user_id,app_id)
    with zipfile.ZipFile(io.BytesIO(base)) as z:files={n:z.read(n) for n in z.namelist()}
    files.pop('SHA256SUMS.txt',None)
    files.update({'infinity_workbench.py':WORKBENCH.encode(),'INFINITY_GUIDE.md':README.encode(),'INFINITY_STATUS.json':json.dumps({'version':'18.1','mode':'offline Docker validation','automatic_ai_repair':False,'automatic_deployment':False,'release_approval':'explicit'},indent=2).encode()})
    files['SHA256SUMS.txt']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in sorted(files.items())).encode()
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    return out.getvalue()
def render(c,user_id):
    apps=c.execute('SELECT id,title,state FROM v13_apps WHERE user_id=? ORDER BY created DESC LIMIT 100',(user_id,)).fetchall()
    result=['<div class="v18"><div class="panel"><h1>∞ INFINITY V18 — Validation & Release Lab</h1><p>Download an offline workbench to compare original and proposed app versions in restricted Docker tests, review exact diffs, and explicitly approve immutable release candidates.</p><p><strong>Nothing is executed, repaired or deployed inside this portal.</strong> Docker Desktop is required for validation.</p></div>']
    for aid,title,state in apps:
        result.append('<div class="panel"><h3>'+html.escape(title)+'</h3><p>Status: '+html.escape(state)+'</p>')
        if state=='published':result.append('<a href="/infinity/export?app='+html.escape(aid,quote=True)+'">Download Infinity validation workbench (.zip)</a>')
        else:result.append('<p>Publish this app in Singularity X before exporting.</p>')
        result.append('</div>')
    if not apps:result.append('<div class="panel">No apps yet. <a href="/singularity-x">Create an app</a>.</div>')
    return ''.join(result)+'</div>'
