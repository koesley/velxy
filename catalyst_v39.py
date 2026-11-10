"""V39 Catalyst: operator-controlled pilot preflight and browser customer workflow.

All active checks execute against disposable localhost installations. Reports are local,
checksum-verified evidence, not third-party attestations or production certifications.
"""
import argparse, html, json, os, re, secrets, socket, sqlite3, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
import empire_v19
from titanium_v36 import save_report, read_reports
from atlas_v38 import report_summary
ROOT=Path(__file__).resolve().parent

def esc(x):return html.escape(str(x),quote=True)

def preflight(data_root,max_age_hours=24):
    """Fail closed if evidence is missing, stale, corrupted, skipped, or failed."""
    if not 1<=max_age_hours<=168:raise ValueError('Invalid maximum age')
    required={'authenticated_journey':'Authenticated HTTP customer journey',
              'http_smoke':'HTTP startup and access boundaries',
              'restore_rehearsal':'Database recovery rehearsal',
              'browser_journey':'Chromium customer browser workflow'}
    now=int(time.time());reports=read_reports(data_root,500);checks={}
    for kind,label in required.items():
        latest=next((r for r in reports if r.get('kind')==kind),None)
        reasons=[]
        if not latest:reasons.append('No evidence recorded')
        else:
            if not latest.get('verified'):reasons.append('Evidence checksum invalid')
            if not latest.get('result',{}).get('passed') or latest.get('result',{}).get('skipped'):reasons.append('Test not passed')
            ts=latest.get('timestamp')
            if not isinstance(ts,int) or ts>now+60 or now-ts>max_age_hours*3600:reasons.append('Evidence missing, future-dated, or stale')
        checks[kind]={'label':label,'passed':not reasons,'reasons':reasons,'timestamp':latest.get('timestamp') if latest else None}
    return {'passed':all(c['passed'] for c in checks.values()),'checks':checks,
            'production_ready':False,'blockers':['Independent security assessment','Remote deployment and disaster recovery testing','Billing/payment verification','Real-user pilot usability validation']}

def browser_journey(data_root,timeout=75):
    """Chromium-driven signup -> login -> workspace -> app -> publish -> record -> Atlas.

    Browser actions go through real forms and page JavaScript, with no direct DB writes.
    An isolated database is read only to discover generated IDs and validate persistence.
    """
    try:from playwright.sync_api import sync_playwright
    except ImportError:
        return save_report(data_root,'browser_journey',{'passed':False,'skipped':True,'reason':'Playwright not installed','checks':{}})
    checks={};errors=[]
    with tempfile.TemporaryDirectory(prefix='velxtria-v39-browser-') as tmp:
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        env=os.environ.copy();env.update({'VELXTRIA_DATA_DIR':tmp,'VELXTRIA_LOCAL_STUDIO':'1','VELXTRIA_DEPLOYMENT_MODE':'local','PORT':str(port),'VELXTRIA_SMTP_HOST':''})
        proc=subprocess.Popen([sys.executable,'portal.py'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        base=f'http://127.0.0.1:{port}'
        try:
            deadline=time.monotonic()+timeout
            while time.monotonic()<deadline:
                if proc.poll() is not None:raise RuntimeError('Portal exited unexpectedly')
                try:
                    with urllib.request.urlopen(base+'/login',timeout=1) as resp:
                        if resp.status==200:break
                except Exception:time.sleep(.2)
            else:raise RuntimeError('Portal startup timeout')
            with sync_playwright() as p:
                try:browser=p.chromium.launch(headless=True)
                except Exception as exc:
                    return save_report(data_root,'browser_journey',{'passed':False,'skipped':True,'reason':'Chromium unavailable: '+str(exc)[:150],'checks':{}})
                try:
                    page=browser.new_page(viewport={'width':390,'height':844})
                    email='catalyst-'+secrets.token_hex(6)+'@example.invalid';password=secrets.token_urlsafe(24)
                    page.goto(base+'/register');page.locator('input[name="email"]').fill(email);page.locator('input[name="password"]').fill(password)
                    page.locator('form button').first.click();checks['register_browser']=page.url.startswith(base)
                    page.goto(base+'/login');page.locator('input[name="email"]').fill(email);page.locator('input[name="password"]').fill(password)
                    page.locator('form button').first.click()
                    page.goto(base+'/empire');checks['login_browser']=page.url.startswith(base+'/empire') and 'Empire' in page.locator('body').inner_text()
                    csrf=page.locator('input[name="csrf"]').first.get_attribute('value')
                    if not csrf:raise RuntimeError('Missing CSRF input')
                    # Submit through Chromium's fetch in the authenticated page context.
                    # This uses real session cookies and CSRF and exercises the actual HTTP routes.
                    def post(path,values):
                        return page.evaluate("async ({path,values})=>{const body=new URLSearchParams(values);const r=await fetch(path,{method:'POST',body,credentials:'same-origin'});return {status:r.status,text:await r.text()}}",{'path':path,'values':values})
                    result=post('/empire',{'action':'create','name':'Catalyst Pilot','csrf':csrf})
                    checks['workspace_created']=result['status']==200 and 'Catalyst Pilot' in result['text']
                    with sqlite3.connect(Path(tmp)/'portal.sqlite3') as db:
                        wid=db.execute('SELECT id FROM empire_workspaces WHERE name=?',('Catalyst Pilot',)).fetchone()[0]
                    page.goto(base+'/genesis-prime?w='+wid)
                    checks['genesis_browser_page']=page.url.startswith(base+'/genesis-prime')
                    result=post('/genesis-prime',{'csrf':csrf,'action':'create','workspace':wid,'name':'Catalyst Inventory','template':'inventory'})
                    checks['app_created']=result['status']==200
                    with sqlite3.connect(Path(tmp)/'portal.sqlite3') as db:
                        aid=db.execute('SELECT id FROM prime_apps WHERE workspace_id=?',(wid,)).fetchone()[0]
                    result=post('/genesis-prime',{'csrf':csrf,'action':'publish','workspace':wid,'app':aid})
                    checks['app_published']=result['status']==200
                    result=post('/genesis-prime',{'csrf':csrf,'action':'record','workspace':wid,'app':aid,'f0':'Sample Widget','f1':'12'})
                    checks['record_saved']=result['status']==200
                    with sqlite3.connect(Path(tmp)/'portal.sqlite3') as db:
                        checks['record_persisted']=db.execute('SELECT COUNT(*) FROM prime_records WHERE workspace_id=? AND app_id=?',(wid,aid)).fetchone()[0]==1
                    page.goto(base+'/atlas?w='+wid)
                    checks['atlas_authenticated']=page.url.startswith(base+'/atlas') and 'Catalyst Pilot' in page.locator('body').inner_text()
                    checks['mobile_no_horizontal_overflow']=page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 2')
                    page.set_viewport_size({'width':1280,'height':900});page.reload()
                    checks['desktop_atlas']=page.url.startswith(base+'/atlas') and 'Catalyst Pilot' in page.locator('body').inner_text()
                    # A second anonymous browser context must not see workspace details.
                    anon=browser.new_page();anon.goto(base+'/atlas?w='+wid)
                    checks['anonymous_workspace_denied']='Catalyst Pilot' not in anon.locator('body').inner_text()
                    anon.close()
                finally:browser.close()
        except Exception as exc:errors.append(type(exc).__name__+': '+str(exc)[:240])
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
    result={'passed':bool(checks) and all(checks.values()) and not errors,'skipped':False,'checks':checks,'errors':errors,'scope':'Actual Chromium registration, login, authenticated workspace/app/record HTTP actions, responsive views and anonymous boundary, isolated database. Not a production security or accessibility audit.'}
    return save_report(data_root,'browser_journey',result)

def render(c,uid,wid,data_root):
    workspaces=c.execute('SELECT w.id,w.name FROM empire_workspaces w JOIN empire_members m ON m.workspace_id=w.id WHERE m.user_id=? ORDER BY w.created DESC',(uid,)).fetchall()
    if not workspaces:return '<section class="panel"><h1>Catalyst V39</h1><p>Create a business workspace in Empire to begin.</p></section>'
    if not wid:wid=workspaces[0][0]
    if not empire_v19.role(c,uid,wid):raise ValueError('Workspace unavailable')
    name=next(name for key,name in workspaces if key==wid)
    status=preflight(data_root)
    rows=''.join('<tr><td>'+esc(item['label'])+'</td><td>'+('PASS' if item['passed'] else 'BLOCKED')+'</td><td>'+esc('; '.join(item['reasons']) or 'Verified recent evidence')+'</td></tr>' for item in status['checks'].values())
    blockers=''.join('<li>'+esc(x)+'</li>' for x in status['blockers'])
    return ('<section class="hero"><p class="eyebrow">VELXTRIA V39 / PROJECT CATALYST</p><h1>Customer pilot preflight</h1><p>Workspace: '+esc(name)+'</p><p>Release preflight: <strong>'+('LOCAL CHECKS PASSED' if status['passed'] else 'BLOCKED')+'</strong></p></section>'
    '<section class="panel"><h2>Verified evidence matrix (24-hour window)</h2><table><thead><tr><th>Check</th><th>Status</th><th>Explanation</th></tr></thead><tbody>'+rows+'</tbody></table><p>Local checks passing never means production certification.</p></section>'
    '<section class="panel"><h2>Run the complete local pilot checks</h2><p><code>python catalyst_v39.py run</code></p><p>Requires Playwright + Chromium for the real-browser workflow. All tests run against disposable local installations; the web page cannot execute commands.</p></section>'
    '<section class="panel"><h2>Outstanding production blockers</h2><ul>'+blockers+'</ul><a href="/atlas?w='+esc(wid)+'">Atlas launch center</a> · <a href="/sovereign-gate?w='+esc(wid)+'">Release approval</a></section>')

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['run','browser','report']);p.add_argument('--data-dir',default=os.environ.get('VELXTRIA_DATA_DIR',str(ROOT)));args=p.parse_args()
    if args.action=='report':print(json.dumps(preflight(args.data_dir),indent=2));return
    if args.action=='browser':
        r=browser_journey(args.data_dir);print(json.dumps(r,indent=2));sys.exit(0 if r['result']['passed'] else (2 if r['result'].get('skipped') else 1))
    from apex_v37 import run_journey
    from titanium_v36 import http_smoke,recovery_rehearsal
    results={}
    results['authenticated_journey']=run_journey(args.data_dir)['result']['passed']
    results['http_smoke']=http_smoke(args.data_dir)['result']['passed']
    db_path=Path(args.data_dir)/'portal.sqlite3'
    if db_path.is_file():results['restore_rehearsal']=recovery_rehearsal(db_path,args.data_dir)['result']['passed']
    else:
        with tempfile.TemporaryDirectory() as tmp:
            testdb=Path(tmp)/'recovery.sqlite3'
            with sqlite3.connect(testdb) as c:c.execute('CREATE TABLE pilot_recovery(id INTEGER PRIMARY KEY, value TEXT)')
            results['restore_rehearsal']=recovery_rehearsal(testdb,args.data_dir)['result']['passed']
    results['browser_journey']=browser_journey(args.data_dir)['result']['passed']
    print(json.dumps({'results':results,'preflight':preflight(args.data_dir)},indent=2))
    sys.exit(0 if all(results.values()) else 1)
if __name__=='__main__':main()
