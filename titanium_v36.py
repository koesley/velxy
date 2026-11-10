"""V36 Titanium: local-only operator recovery rehearsal and HTTP smoke test evidence.

Never restores over live data. The web view is strictly read-only.
"""
import argparse
import hashlib
import html
import json
import os
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
import empire_v19

ROOT=Path(__file__).resolve().parent
MAX_REPORT=25000

def esc(value):return html.escape(str(value),quote=True)
def reports_dir(data_root):return Path(data_root).resolve()/'titanium_evidence'
def digest(payload):return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def save_report(data_root,kind,result):
    folder=reports_dir(data_root);folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    report={'schema':1,'id':secrets.token_hex(16),'kind':kind,'timestamp':int(time.time()),'result':result}
    report['sha256']=digest(report)
    target=folder/(report['id']+'.json')
    with target.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2,sort_keys=True)
    try:os.chmod(target,0o600)
    except OSError:pass
    return report

def read_reports(data_root,limit=20):
    folder=reports_dir(data_root)
    if not folder.is_dir():return []
    out=[]
    for p in sorted(folder.glob('*.json'),key=lambda x:x.stat().st_mtime,reverse=True)[:limit]:
        try:
            if p.is_symlink() or p.stat().st_size>MAX_REPORT:continue
            d=json.loads(p.read_text(encoding='utf-8'))
            sha=d.pop('sha256',None);valid=sha==digest(d) and d.get('id')==p.stem
            d['sha256']=sha;d['verified']=valid
            out.append(d)
        except (OSError,ValueError,TypeError):continue
    return out

def _snapshot(c):
    tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    counts={}
    for table in tables:
        safe='"'+table.replace('"','""')+'"'
        counts[table]=c.execute('SELECT COUNT(*) FROM '+safe).fetchone()[0]
    return counts

def recovery_rehearsal(db_path,data_root):
    """Online snapshot + restore to temporary sandbox; live database never replaced."""
    path=Path(db_path).resolve()
    if not path.is_file():raise ValueError('Local SQLite database does not exist')
    with tempfile.TemporaryDirectory(prefix='velxtria-v36-restore-') as tmp:
        backup=Path(tmp)/'consistent.sqlite3'
        restored=Path(tmp)/'restored.sqlite3'
        with sqlite3.connect(f'{path.as_uri()}?mode=ro',uri=True,timeout=10) as src:
            with sqlite3.connect(backup) as dest:src.backup(dest)
        with sqlite3.connect(backup) as src,sqlite3.connect(restored) as dest:src.backup(dest)
        with sqlite3.connect(backup) as c:
            before_integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
            before_fk=len(c.execute('PRAGMA foreign_key_check').fetchall())
            before_counts=_snapshot(c)
        with sqlite3.connect(restored) as c:
            after_integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
            after_fk=len(c.execute('PRAGMA foreign_key_check').fetchall())
            after_counts=_snapshot(c)
        result={'passed':before_integrity=='ok' and after_integrity=='ok' and before_fk==0 and after_fk==0 and before_counts==after_counts,
                'snapshot_integrity':before_integrity,'restored_integrity':after_integrity,
                'snapshot_foreign_key_violations':before_fk,'restored_foreign_key_violations':after_fk,
                'tables_compared':len(before_counts),'records_compared':sum(before_counts.values()),
                'table_counts_equal':before_counts==after_counts,
                'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),
                'restored_sha256':hashlib.sha256(restored.read_bytes()).hexdigest(),
                'note':'Restore rehearsed only in a disposable directory; no live database files were replaced.'}
    return save_report(data_root,'restore_rehearsal',result)

def http_smoke(data_root,timeout=30):
    """Boot actual portal in temporary studio; verify public routes and auth boundaries."""
    if not 10<=timeout<=120:raise ValueError('Timeout must be 10-120 seconds')
    with tempfile.TemporaryDirectory(prefix='velxtria-v36-http-') as temp:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        env=os.environ.copy();env.update({'VELXTRIA_DATA_DIR':temp,'VELXTRIA_LOCAL_STUDIO':'1','VELXTRIA_DEPLOYMENT_MODE':'local','PORT':str(port),'VELXTRIA_SMTP_HOST':''})
        process=subprocess.Popen([sys.executable,'portal.py'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        base=f'http://127.0.0.1:{port}'
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,req,fp,code,msg,headers,newurl):return None
        opener=urllib.request.build_opener(NoRedirect())
        def request(path):
            try:
                with opener.open(base+path,timeout=2) as response:return response.status,response.headers.get('Location',''),response.read(100000).decode('utf-8','replace')
            except urllib.error.HTTPError as e:return e.code,e.headers.get('Location',''),e.read(100000).decode('utf-8','replace')
        checks={}
        try:
            until=time.monotonic()+timeout
            while time.monotonic()<until:
                if process.poll() is not None:break
                try:
                    code,_,_=request('/login')
                    if code==200:break
                except (OSError,TimeoutError):pass
                time.sleep(.15)
            if process.poll() is not None:raise RuntimeError('Portal terminated during startup')
            checks['login_page']=request('/login')[0]==200
            checks['registration_page']=request('/register')[0]==200
            checks['stylesheet']=request('/style.css')[0]==200
            for route in ['/titanium','/sovereign-gate','/sentinel','/integration','/first-contact','/horizon']:
                code,loc,_=request(route)
                checks['anonymous_'+route]=code in (302,303,401,403) and (code not in (302,303) or '/login' in loc)
            result={'passed':all(checks.values()),'checks':checks,'count':len(checks),'scope':'Real HTTP smoke test with temporary database; no authenticated browser journey or production security audit.'}
        except Exception as exc:
            result={'passed':False,'checks':checks,'error':type(exc).__name__+': '+str(exc)[:200]}
        finally:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
    return save_report(data_root,'http_smoke',result)

def render(c,uid,wid,data_root):
    ws=c.execute('SELECT w.id,w.name FROM empire_workspaces w JOIN empire_members m ON m.workspace_id=w.id WHERE m.user_id=? ORDER BY w.created DESC',(uid,)).fetchall()
    if not ws:return '<section class="panel"><h1>Titanium V36</h1><p>Create a workspace in Empire first.</p></section>'
    if not wid:wid=ws[0][0]
    if not empire_v19.role(c,uid,wid):raise ValueError('Workspace unavailable')
    opts=''.join('<option value="'+esc(i)+'"'+(' selected' if i==wid else '')+'>'+esc(name)+'</option>' for i,name in ws)
    reports=read_reports(data_root)
    rows=''.join('<tr><td>'+esc(time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(r['timestamp'])))+'</td><td>'+esc(r['kind'])+'</td><td>'+('PASS' if r['result'].get('passed') else 'FAIL')+'</td><td>'+('Verified' if r['verified'] else 'INVALID')+'</td></tr>' for r in reports)
    return ('<section class="hero"><p class="eyebrow">VELXTRIA V36 · PROJECT TITANIUM</p><h1>Test the recovery. Test the actual portal.</h1><p>Local operator-controlled recovery rehearsals and HTTP smoke checks, with checksum-verified evidence.</p></section>'
        '<section class="panel"><form method="get" action="/titanium"><label>Workspace<select name="w">'+opts+'</select></label><button>Switch</button></form></section>'
        '<section class="panel"><h2>Local operator commands</h2><p><code>python titanium_v36.py restore</code> — rehearse SQLite backup and restoration in a disposable directory.</p><p><code>python titanium_v36.py smoke</code> — start a temporary local portal and check HTTP access boundaries.</p><p><code>python titanium_v36.py all</code> — run both checks. No web action executes commands or restores production data.</p></section>'
        '<section class="panel"><h2>Verified evidence history</h2><table><thead><tr><th>Time</th><th>Test</th><th>Outcome</th><th>Checksum</th></tr></thead><tbody>'+(rows or '<tr><td colspan="4">No Titanium evidence recorded.</td></tr>')+'</tbody></table></section>'
        '<section class="panel"><h2>Important limitations</h2><p>Checks are local and operator-controlled. Restored databases are deleted after verification. The HTTP smoke test does not replace browser automation, authenticated multi-step workflows, disaster recovery drills, or an independent security audit.</p><a href="/sovereign-gate?w='+esc(wid)+'">Sovereign Gate</a> · <a href="/sentinel?w='+esc(wid)+'">Sentinel</a></section>')

def main():
    parser=argparse.ArgumentParser(description='VELXTRIA V36 local recovery and HTTP testing')
    parser.add_argument('action',choices=['restore','smoke','all','report'])
    parser.add_argument('--data-dir',default=os.environ.get('VELXTRIA_DATA_DIR',str(ROOT)))
    args=parser.parse_args();root=Path(args.data_dir).resolve()
    if args.action=='report':print(json.dumps(read_reports(root),indent=2));return
    results=[]
    if args.action in ('restore','all'):results.append(recovery_rehearsal(root/'portal.sqlite3',root))
    if args.action in ('smoke','all'):results.append(http_smoke(root))
    for report in results:print(json.dumps(report,indent=2))
    if not all(r['result']['passed'] for r in results):sys.exit(1)
if __name__=='__main__':main()
