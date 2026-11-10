"""Sentinel V34: bounded local regression runs and immutable, hashed evidence.

The web page is read-only. Only the operator's CLI may execute test code.
"""
import argparse, hashlib, html, json, os, sqlite3, subprocess, sys, tempfile, time, uuid
from pathlib import Path
import empire_v19

ROOT = Path(__file__).resolve().parent
TEST_FILES = tuple(sorted(p.name for p in ROOT.glob('test_*_v*.py') if p.is_file()))
MAX_OUTPUT = 24000

def esc(value): return html.escape(str(value), quote=True)

def evidence_dir(data_root):
    return Path(data_root).resolve() / 'sentinel_evidence'

def _digest(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def run_suite(data_root, timeout=180):
    """Operator-only: execute fixed, bundled test modules in isolated temporary data dir."""
    if not 10 <= timeout <= 600: raise ValueError('Timeout must be between 10 and 600 seconds')
    if not TEST_FILES: raise RuntimeError('No bundled regression tests found')
    output_dir=evidence_dir(data_root)
    output_dir.mkdir(mode=0o700,parents=True,exist_ok=True)
    started=int(time.time())
    with tempfile.TemporaryDirectory(prefix='velxtria-sentinel-') as sandbox:
        env=os.environ.copy()
        env.update({'VELXTRIA_DATA_DIR':sandbox,'VELXTRIA_LOCAL_STUDIO':'1','VELXTRIA_DEPLOYMENT_MODE':'local'})
        command=[sys.executable,'-m','unittest','-v',*map(lambda x:x[:-3],TEST_FILES)]
        try:
            proc=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=timeout,check=False)
            raw=(proc.stdout+'\n'+proc.stderr)
            status='passed' if proc.returncode==0 else 'failed'
            exit_code=proc.returncode
        except subprocess.TimeoutExpired as exc:
            raw=((exc.stdout or b'').decode(errors='replace') if isinstance(exc.stdout,bytes) else (exc.stdout or ''))+'\nTIMEOUT'
            status='timeout';exit_code=None
    evidence={'schema':1,'run_id':uuid.uuid4().hex,'started':started,'finished':int(time.time()),'status':status,'exit_code':exit_code,'tests':list(TEST_FILES),'output':raw[-MAX_OUTPUT:],'output_truncated':len(raw)>MAX_OUTPUT,'python':sys.version.split()[0]}
    evidence['sha256']=_digest(evidence)
    target=output_dir/(evidence['run_id']+'.json')
    with target.open('x',encoding='utf-8') as f:
        json.dump(evidence,f,indent=2,sort_keys=True)
    try:os.chmod(target,0o600)
    except OSError:pass
    return evidence

def load_reports(data_root,limit=15):
    base=evidence_dir(data_root)
    if not base.is_dir():return []
    reports=[]
    for p in sorted(base.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:limit]:
        try:
            if p.is_symlink() or p.stat().st_size>100000:continue
            data=json.loads(p.read_text(encoding='utf-8'))
            claimed=data.pop('sha256','')
            valid=claimed==_digest(data) and p.stem==data.get('run_id')
            data['sha256']=claimed;data['verified']=valid
            reports.append(data)
        except (OSError,ValueError,TypeError,KeyError):continue
    return reports

def database_health(db_path):
    """Read-only integrity and foreign key inspection, never modifies customer data."""
    path=Path(db_path)
    if not path.is_file():return {'integrity':'missing','foreign_key_violations':None,'size_bytes':0}
    uri='file:'+str(path.resolve()).replace('?','%3F')+'?mode=ro'
    with sqlite3.connect(uri,uri=True,timeout=5) as c:
        integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
        violations=c.execute('PRAGMA foreign_key_check').fetchmany(100)
    return {'integrity':integrity,'foreign_key_violations':len(violations),'size_bytes':path.stat().st_size,'violations_capped':len(violations)==100}

def render(c,uid,csrf,wid,data_root,db_path):
    ws=c.execute('SELECT w.id,w.name FROM empire_workspaces w JOIN empire_members m ON w.id=m.workspace_id WHERE m.user_id=? ORDER BY w.created DESC',(uid,)).fetchall()
    if not ws:return '<section class="panel"><h1>Sentinel V34</h1><p>Create a workspace in Empire first.</p></section>'
    if not wid:wid=ws[0][0]
    if not empire_v19.role(c,uid,wid):raise ValueError('Workspace unavailable')
    opts=''.join('<option value="'+esc(w[0])+'"'+(' selected' if w[0]==wid else '')+'>'+esc(w[1])+'</option>' for w in ws)
    reports=load_reports(data_root)
    rows=''.join('<tr><td>'+esc(time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(r['started'])))+'</td><td>'+esc(r['status'])+'</td><td>'+('Verified' if r['verified'] else 'INVALID CHECKSUM')+'</td><td>'+esc(len(r['tests']))+' modules</td><td><code>'+esc(r['sha256'][:16])+'…</code></td></tr>' for r in reports)
    try:health=database_health(db_path)
    except (OSError,sqlite3.Error) as e:health={'integrity':'error: '+type(e).__name__,'foreign_key_violations':'unknown','size_bytes':0}
    status='NOT PRODUCTION CERTIFIED'
    return ('<section class="hero"><p class="eyebrow">VELXTRIA V34 · PROJECT SENTINEL</p><h1>Proof before promotion.</h1><p>Machine-generated regression evidence, local database diagnostics and transparent release limitations.</p></section>'
     '<section class="panel"><form method="get" action="/sentinel"><label>Workspace<select name="w">'+opts+'</select></label><button>Switch</button></form></section>'
     '<section class="panel"><h2>Release status: '+status+'</h2><p>SQLite integrity: <strong>'+esc(health['integrity'])+'</strong> · Foreign-key violations: '+esc(health['foreign_key_violations'])+' · Database size: '+esc(health['size_bytes'])+' bytes</p><p>These checks do not replace a security audit, full browser testing, or a verified restore rehearsal.</p></section>'
     '<section class="panel"><h2>Automated regression evidence</h2><p>Run from your local terminal: <code>python sentinel_v34.py run</code>. Tests execute in a separate temporary database directory. This page never executes code.</p><div class="scroll"><table><thead><tr><th>Run</th><th>Result</th><th>Evidence</th><th>Scope</th><th>SHA-256 prefix</th></tr></thead><tbody>'+(rows or '<tr><td colspan="5">No automated test runs recorded yet.</td></tr>')+'</tbody></table></div></section>'
     '<section class="panel"><h2>Release safety</h2><p>Test reports are local operator evidence, not per-workspace security certification. A successful run does not authorize deployment. V33 owner approvals remain separate.</p><p><a href="/evolutionary-core?w='+esc(wid)+'">Release candidates</a> · <a href="/sovereign-core?w='+esc(wid)+'">Readiness checks</a> · <a href="/foundation?w='+esc(wid)+'">Backups</a></p></section>')

def main():
    parser=argparse.ArgumentParser(description='VELXTRIA Sentinel local regression runner')
    parser.add_argument('action',choices=['run','report','health'])
    parser.add_argument('--data-dir',default=os.getenv('VELXTRIA_DATA_DIR',str(ROOT)))
    parser.add_argument('--timeout',type=int,default=180)
    args=parser.parse_args()
    if args.action=='run':
        report=run_suite(args.data_dir,args.timeout)
        print(json.dumps({k:v for k,v in report.items() if k!='output'},indent=2))
        sys.exit(0 if report['status']=='passed' else 1)
    if args.action=='report':
        print(json.dumps([{k:v for k,v in r.items() if k!='output'} for r in load_reports(args.data_dir)],indent=2))
    if args.action=='health':print(json.dumps(database_health(Path(args.data_dir)/'portal.sqlite3'),indent=2))

if __name__=='__main__':main()
