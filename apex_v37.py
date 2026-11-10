"""V37 Apex: real authenticated HTTP customer journey in an isolated local server.
Operator-only CLI. No production data access, no browser JavaScript automation.
"""
import argparse, http.cookiejar, json, os, re, secrets, socket, sqlite3, subprocess, sys, tempfile, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path
from titanium_v36 import save_report,read_reports,esc
import empire_v19
ROOT=Path(__file__).resolve().parent
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):return None

def run_journey(data_root,timeout=45):
 if not 15<=timeout<=120:raise ValueError('timeout out of range')
 checks={}; failures=[]
 with tempfile.TemporaryDirectory(prefix='velxtria-v37-') as tmp:
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  env=os.environ.copy();env.update({'VELXTRIA_DATA_DIR':tmp,'VELXTRIA_LOCAL_STUDIO':'1','VELXTRIA_DEPLOYMENT_MODE':'local','PORT':str(port),'VELXTRIA_SMTP_HOST':''})
  proc=subprocess.Popen([sys.executable,'portal.py'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  base=f'http://127.0.0.1:{port}'
  jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar),NoRedirect())
  def req(path,form=None):
   data=urllib.parse.urlencode(form).encode() if form is not None else None
   request=urllib.request.Request(base+path,data=data)
   try:
    with opener.open(request,timeout=3) as r:return r.status,dict(r.headers),r.read(250000).decode('utf-8','replace')
   except urllib.error.HTTPError as e:return e.code,dict(e.headers),e.read(250000).decode('utf-8','replace')
  def check(label,condition):
   checks[label]=bool(condition)
   if not condition:failures.append(label)
  try:
   deadline=time.monotonic()+timeout
   while time.monotonic()<deadline:
    if proc.poll() is not None:break
    try:
     if req('/login')[0]==200:break
    except OSError:pass
    time.sleep(.2)
   else:raise RuntimeError('Portal startup timed out')
   if proc.poll() is not None:raise RuntimeError('Portal exited before tests')
   check('anonymous_workspace_blocked',req('/empire')[0] in (302,303,401,403))
   email='apex-'+secrets.token_hex(6)+'@example.invalid';password=secrets.token_urlsafe(24)
   check('register',req('/register',{'email':email,'password':password})[0] in (302,303))
   status,headers,_=req('/login',{'email':email,'password':password})
   check('login',status in (302,303) and any(c.name=='velxtria_session' for c in jar))
   status,_,page=req('/empire');check('authenticated_empire',status==200)
   match=re.search(r'name="csrf" value="([^"]+)"',page)
   if not match:raise RuntimeError('Missing CSRF token in workspace page')
   csrf=match.group(1)
   check('csrf_rejected',req('/empire',{'action':'create','name':'Rejected Workspace','csrf':'invalid'})[0]==403)
   status,_,page=req('/empire',{'action':'create','name':'Apex Pilot Business','csrf':csrf})
   check('create_workspace',status==200 and 'Apex Pilot Business' in page)
   with sqlite3.connect(Path(tmp)/'portal.sqlite3') as c:
    wid=c.execute('SELECT id FROM empire_workspaces WHERE name=?',('Apex Pilot Business',)).fetchone()[0]
   status,_,page=req('/genesis-prime?w='+wid)
   check('genesis_page',status==200)
   status,_,page=req('/genesis-prime',{'csrf':csrf,'action':'create','workspace':wid,'name':'Apex Inventory','template':'inventory'})
   check('create_application',status==200)
   with sqlite3.connect(Path(tmp)/'portal.sqlite3') as c:
    aid=c.execute('SELECT id FROM prime_apps WHERE workspace_id=?',(wid,)).fetchone()[0]
   status,_,page=req('/genesis-prime',{'csrf':csrf,'action':'publish','workspace':wid,'app':aid})
   check('publish_application',status==200)
   status,_,page=req('/genesis-prime',{'csrf':csrf,'action':'record','workspace':wid,'app':aid,'f0':'Widget','f1':'12'})
   check('save_business_record',status==200)
   with sqlite3.connect(Path(tmp)/'portal.sqlite3') as c:
    check('persisted_business_record',c.execute('SELECT COUNT(*) FROM prime_records WHERE workspace_id=? AND app_id=?',(wid,aid)).fetchone()[0]==1)
   for path in ['/oracle','/nexus-intelligence','/launchpad','/integration','/ascension','/sovereign-core','/first-contact','/horizon','/sentinel','/sovereign-gate','/titanium']:
    status,_,_=req(path+'?w='+wid)
    check('authenticated_'+path.strip('/'),status==200)
   status,_,page=req('/empire',{'csrf':csrf,'action':'create','name':'Apex Isolated Business'})
   check('second_workspace',status==200)
   with sqlite3.connect(Path(tmp)/'portal.sqlite3') as c:
    other=c.execute('SELECT id FROM empire_workspaces WHERE name=?',('Apex Isolated Business',)).fetchone()[0]
   status,_,page=req('/genesis-prime?w='+other+'&app='+aid)
   check('cross_workspace_app_denied',status in (400,403,404))
   status,_,page=req('/genesis-prime',{'csrf':csrf,'action':'record','workspace':other,'app':aid,'f0':'Intrusion','f1':'1'})
   check('cross_workspace_write_denied',status in (400,403,404))
   with sqlite3.connect(Path(tmp)/'portal.sqlite3') as c:
    check('no_cross_workspace_record',c.execute('SELECT COUNT(*) FROM prime_records WHERE workspace_id=?',(other,)).fetchone()[0]==0)
  except Exception as exc:failures.append(type(exc).__name__+': '+str(exc)[:180])
  finally:
   proc.terminate()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
 result={'passed':bool(checks) and all(checks.values()) and not failures,'checks':checks,'failed':failures,'count':len(checks),'scope':'Authenticated HTTP journey on disposable localhost server and database. Not browser automation; not a production security audit.'}
 return save_report(data_root,'authenticated_journey',result)

def render(c,uid,wid,data_root):
 ws=c.execute('SELECT w.id,w.name FROM empire_workspaces w JOIN empire_members m ON m.workspace_id=w.id WHERE m.user_id=? ORDER BY w.created DESC',(uid,)).fetchall()
 if not ws:return '<section class="panel"><h1>Apex V37</h1><p>Create a workspace first.</p></section>'
 if not wid:wid=ws[0][0]
 if not empire_v19.role(c,uid,wid):raise ValueError('Workspace unavailable')
 opts=''.join('<option value="'+esc(i)+'"'+(' selected' if i==wid else '')+'>'+esc(n)+'</option>' for i,n in ws)
 reports=[r for r in read_reports(data_root,50) if r.get('kind')=='authenticated_journey']
 rows=''.join('<tr><td>'+esc(time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(r['timestamp'])))+'</td><td>'+('PASS' if r['result'].get('passed') else 'FAIL')+'</td><td>'+str(r['result'].get('count',0))+'</td><td>'+('Verified' if r['verified'] else 'INVALID')+'</td></tr>' for r in reports)
 return ('<section class="hero"><p class="eyebrow">VELXTRIA V37 · PROJECT APEX</p><h1>Test the complete customer path.</h1><p>Authenticated HTTP checks against an isolated temporary local installation.</p></section>'
 '<section class="panel"><form method="get" action="/apex"><label>Workspace<select name="w">'+opts+'</select></label><button>Switch</button></form></section>'
 '<section class="panel"><h2>Operator command</h2><p><code>python apex_v37.py run</code></p><p>Tests registration, login, CSRF, workspace creation, app publishing, record entry, module pages, and cross-workspace write protections. Tests run in a temporary database. The web page never launches commands.</p></section>'
 '<section class="panel"><h2>Recent authenticated journey reports</h2><table><thead><tr><th>Time</th><th>Result</th><th>Checks</th><th>Checksum</th></tr></thead><tbody>'+(rows or '<tr><td colspan="4">No reports yet</td></tr>')+'</tbody></table></section>'
 '<section class="panel"><h2>Remaining blockers</h2><p>This is real HTTP testing, not browser-driven interaction. JavaScript, responsive usability, external deployment, payments, and independent security assessment remain unverified.</p><a href="/titanium?w='+esc(wid)+'">Titanium recovery</a> · <a href="/sovereign-gate?w='+esc(wid)+'">Release gate</a></section>')

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['run','report']);p.add_argument('--data-dir',default=os.environ.get('VELXTRIA_DATA_DIR',str(ROOT)));args=p.parse_args()
 if args.action=='report':print(json.dumps([r for r in read_reports(args.data_dir) if r.get('kind')=='authenticated_journey'],indent=2));return
 r=run_journey(args.data_dir);print(json.dumps(r,indent=2));sys.exit(0 if r['result']['passed'] else 1)
if __name__=='__main__':main()
