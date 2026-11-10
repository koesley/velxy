"""V38 Atlas: guided customer launch, release evidence, optional actual browser smoke tests."""
import argparse, html, json, os, secrets, socket, sqlite3, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
import empire_v19, launchpad_v27
from titanium_v36 import save_report, read_reports
ROOT=Path(__file__).resolve().parent

def esc(v):return html.escape(str(v),quote=True)

def report_summary(data_root):
 reports=read_reports(data_root,100)
 kinds=('authenticated_journey','http_smoke','restore_rehearsal','browser_journey')
 result={}
 for kind in kinds:
  matching=[r for r in reports if r.get('kind')==kind]
  r=matching[0] if matching else None
  result[kind]={'available':bool(r),'verified':bool(r and r.get('verified')),'passed':bool(r and r.get('verified') and r.get('result',{}).get('passed')),'timestamp':r.get('timestamp') if r else None}
 return result

def readiness(data_root):
 summary=report_summary(data_root)
 checks=[('Authenticated customer HTTP journey',summary['authenticated_journey']['passed']),('HTTP startup and anonymous access',summary['http_smoke']['passed']),('Database recovery rehearsal',summary['restore_rehearsal']['passed']),('Real browser customer smoke test',summary['browser_journey']['passed'])]
 return {'checks':checks,'passed':sum(v for _,v in checks),'total':len(checks),'production_ready':False,'blockers':['Independent security assessment','Production hosting and operational recovery validation','Payment and customer billing verification','Real customer usability pilot']}

def render(c,uid,wid,data_root):
 ws=c.execute('SELECT w.id,w.name FROM empire_workspaces w JOIN empire_members m ON m.workspace_id=w.id WHERE m.user_id=? ORDER BY w.created DESC',(uid,)).fetchall()
 if not ws:return '<div class="atlas"><section class="atlas-hero"><p class="atlas-kicker">VELXTRIA V38 / ATLAS</p><h1>Welcome to your launch center.</h1><p>Start by creating a business workspace.</p><a class="atlas-action" href="/empire">Create workspace</a></section></div>'
 if not wid:wid=ws[0][0]
 if not empire_v19.role(c,uid,wid):raise ValueError('Workspace unavailable')
 name=next(name for id,name in ws if id==wid)
 options=''.join('<option value="'+esc(id)+'"'+(' selected' if id==wid else '')+'>'+esc(n)+'</option>' for id,n in ws)
 steps=[('Set up your business workspace','/empire',True),('Publish your first application','/genesis-prime',False),('Add real business records','/genesis-prime',False),('Define a measurable goal','/nexus-intelligence',False),('Run a customer pilot','/launchpad',False),('Log pilot issues','/first-contact',False)]
 try:
  evidence=launchpad_v27.evidence(c,wid)
  for i in range(min(3,len(evidence))):steps[i+1]=(steps[i+1][0],steps[i+1][1],bool(evidence[i][1]))
 except (ValueError,KeyError,sqlite3.OperationalError):pass
 try:
  count=c.execute('SELECT COUNT(*) FROM launchpad_pilots WHERE workspace_id=?',(wid,)).fetchone()[0]
  steps[4]=(steps[4][0],steps[4][1],count>0)
 except sqlite3.OperationalError:pass
 try:
  count=c.execute('SELECT COUNT(*) FROM first_contact_issues WHERE workspace_id=?',(wid,)).fetchone()[0]
  steps[5]=(steps[5][0],steps[5][1],count>0)
 except sqlite3.OperationalError:pass
 done=sum(s[2] for s in steps)
 step_html=''.join('<li><span class="atlas-stepmark">'+('✓' if ok else str(i+1))+'</span><div><strong>'+esc(title)+'</strong><small>'+('Complete' if ok else 'Next action')+'</small></div><a href="'+url+'?w='+esc(wid)+'">'+('Review' if ok else 'Open')+' →</a></li>' for i,(title,url,ok) in enumerate(steps))
 status=readiness(data_root)
 tests=''.join('<li><span class="atlas-indicator '+('atlas-pass' if passed else 'atlas-pending')+'">'+('PASS' if passed else 'NOT VERIFIED')+'</span><span>'+esc(label)+'</span></li>' for label,passed in status['checks'])
 blockers=''.join('<li>'+esc(b)+'</li>' for b in status['blockers'])
 return ('<div class="atlas"><section class="atlas-hero"><p class="atlas-kicker">VELXTRIA / PROJECT ATLAS V38</p><h1>From first login to first customer.</h1><p>One guided path through your business tools, with real test evidence and visible launch blockers.</p><a class="atlas-action" href="/ascension?w='+esc(wid)+'">Open command center ↗</a></section>'
 '<section class="atlas-switch"><div><small>ACTIVE BUSINESS</small><h2>'+esc(name)+'</h2></div><form method="get" action="/atlas"><label for="atlas-w">Workspace</label><select id="atlas-w" name="w">'+options+'</select><button>Switch</button></form></section>'
 '<div class="atlas-grid"><section class="atlas-panel"><p class="atlas-kicker">CUSTOMER JOURNEY</p><h2>Get from setup to feedback</h2><div class="atlas-progress" role="progressbar" aria-valuenow="'+str(done)+'" aria-valuemin="0" aria-valuemax="'+str(len(steps))+'" aria-label="Customer journey progress"><span style="width:'+str(round(100*done/len(steps)))+'%"></span></div><p>'+str(done)+' of '+str(len(steps))+' stages completed</p><ol class="atlas-steps">'+step_html+'</ol></section>'
 '<section class="atlas-panel"><p class="atlas-kicker">RELEASE EVIDENCE</p><h2>Know what is verified</h2><ul class="atlas-tests">'+tests+'</ul><h3>Local operator commands</h3><p><code>python apex_v37.py run</code></p><p><code>python titanium_v36.py all</code></p><p><code>python atlas_v38.py browser</code></p><p class="atlas-note">Browser testing requires Playwright and Chromium. Missing dependencies produce a SKIP, not a PASS.</p><h3>Production blockers</h3><ul>'+blockers+'</ul><p class="atlas-note"><strong>Not production-certified.</strong> Checks only describe evidence recorded on this local installation.</p></section></div></div>')

CSS=r"""/* V38 Atlas: isolated accessible responsive styles */
.atlas{max-width:1200px;margin:auto;color:#f6f0ff}.atlas *{box-sizing:border-box}.atlas a{color:#cfbaff}.atlas-hero{padding:clamp(28px,5vw,60px);background:radial-gradient(circle at 90% 0%,#54337e 0%,transparent 55%),linear-gradient(135deg,#181023,#100e18);border:1px solid #4b3b63;border-radius:22px}.atlas-kicker{color:#c6a6ff;font-size:11px;font-weight:800;letter-spacing:.17em}.atlas-hero h1{color:white;font-size:clamp(32px,5vw,62px);line-height:1.1;max-width:700px}.atlas-hero p{max-width:630px;color:#d5c8e6;line-height:1.6}.atlas-action{display:inline-block;background:#bd9cf7;color:#1c0d2b!important;padding:13px 20px;border-radius:10px;text-decoration:none;font-weight:800}.atlas-switch,.atlas-panel{background:#191423;border:1px solid #463954;border-radius:16px;padding:25px}.atlas-switch{display:flex;justify-content:space-between;align-items:center;gap:20px;flex-wrap:wrap;margin:16px 0}.atlas-switch h2{margin:5px 0;color:white}.atlas-switch form{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.atlas-switch select,.atlas-switch button{background:#30263e;color:white;padding:10px;border:1px solid #6c5485;border-radius:8px}.atlas-grid{display:grid;grid-template-columns:1.1fr 1fr;gap:16px}.atlas-panel h2,.atlas-panel h3{color:white}.atlas-panel p{color:#c8bcd7}.atlas-progress{height:10px;background:#392c47;border-radius:20px;overflow:hidden}.atlas-progress span{display:block;height:100%;background:#b999f2}.atlas-steps,.atlas-tests{list-style:none;padding:0}.atlas-steps li{display:flex;align-items:center;gap:13px;padding:16px 0;border-bottom:1px solid #45364f}.atlas-stepmark{border:1px solid #7b6298;width:30px;height:30px;display:grid;place-items:center;border-radius:50%;flex-shrink:0;color:#e2d1ff}.atlas-steps li div{flex:1;min-width:0}.atlas-steps li strong,.atlas-steps li small{display:block}.atlas-steps li small{font-size:11px;color:#b9a8c9;margin-top:4px}.atlas-steps li a{white-space:nowrap;font-size:13px}.atlas-tests li{display:flex;gap:12px;align-items:center;padding:10px 0}.atlas-indicator{font-size:10px;min-width:91px;font-weight:800}.atlas-pass{color:#8be5af}.atlas-pending{color:#f4c67c}.atlas-note{font-size:12px;line-height:1.5}.atlas code{white-space:normal;overflow-wrap:anywhere}@media(max-width:800px){.atlas-grid{grid-template-columns:1fr}.atlas-panel{padding:18px}}
"""

def browser_journey(data_root,timeout=60):
 """Real browser smoke test. Isolated portal; never touches user's data directory."""
 try:
  from playwright.sync_api import sync_playwright
 except ImportError:
  return save_report(data_root,'browser_journey',{'passed':False,'skipped':True,'reason':'Playwright Python package not installed. Install with: python -m pip install playwright && python -m playwright install chromium','checks':{}})
 checks={}; errors=[]
 with tempfile.TemporaryDirectory(prefix='velxtria-v38-browser-') as tmp:
  with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
  env=os.environ.copy();env.update({'VELXTRIA_DATA_DIR':tmp,'VELXTRIA_LOCAL_STUDIO':'1','VELXTRIA_DEPLOYMENT_MODE':'local','PORT':str(port),'VELXTRIA_SMTP_HOST':''})
  proc=subprocess.Popen([sys.executable,'portal.py'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  base='http://127.0.0.1:'+str(port)
  try:
   deadline=time.monotonic()+min(timeout,90)
   while time.monotonic()<deadline:
    if proc.poll() is not None:raise RuntimeError('Portal exited unexpectedly')
    try:
     with urllib.request.urlopen(base+'/login',timeout=2) as r:
      if r.status==200:break
    except Exception:time.sleep(.25)
   else:raise RuntimeError('Portal startup timed out')
   with sync_playwright() as p:
    try:browser=p.chromium.launch(headless=True)
    except Exception as exc:
     return save_report(data_root,'browser_journey',{'passed':False,'skipped':True,'reason':'Chromium unavailable: '+str(exc)[:200],'checks':{}})
    try:
     page=browser.new_page(viewport={'width':390,'height':844})
     page.goto(base+'/login',wait_until='domcontentloaded')
     checks['login_form_visible']=page.locator('input[name="email"]').count()>0
     page.goto(base+'/register',wait_until='domcontentloaded')
     checks['registration_form_visible']=page.locator('input[name="email"]').count()>0
     email='atlas-'+secrets.token_hex(6)+'@example.invalid';password=secrets.token_urlsafe(22)
     page.locator('input[name="email"]').fill(email)
     page.locator('input[name="password"]').fill(password)
     page.locator('form button[type="submit"],form button:not([type])').first.click()
     page.goto(base+'/login',wait_until='domcontentloaded')
     page.locator('input[name="email"]').fill(email)
     page.locator('input[name="password"]').fill(password)
     page.locator('form button[type="submit"],form button:not([type])').first.click()
     page.goto(base+'/empire',wait_until='domcontentloaded')
     checks['authenticated_empire']=page.locator('body').inner_text().find('Empire')>=0 and '/login' not in page.url
     page.goto(base+'/atlas',wait_until='domcontentloaded')
     checks['atlas_onboarding_visible']='launch center' in page.locator('body').inner_text().lower()
     checks['mobile_no_horizontal_overflow']=page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 2')
     page.set_viewport_size({'width':1280,'height':900});page.reload()
     checks['desktop_atlas_visible']='launch center' in page.locator('body').inner_text().lower()
    finally:browser.close()
  except Exception as exc:errors.append(type(exc).__name__+': '+str(exc)[:240])
  finally:
   proc.terminate()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
 result={'passed':bool(checks) and all(checks.values()) and not errors,'skipped':False,'checks':checks,'errors':errors,'scope':'Real Chromium smoke test on isolated localhost portal. Not a complete UX or security audit.'}
 return save_report(data_root,'browser_journey',result)

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['browser','report']);p.add_argument('--data-dir',default=os.environ.get('VELXTRIA_DATA_DIR',str(ROOT)));args=p.parse_args()
 if args.action=='report':print(json.dumps(readiness(args.data_dir),indent=2));return
 result=browser_journey(args.data_dir);print(json.dumps(result,indent=2));sys.exit(0 if result['result'].get('passed') else (2 if result['result'].get('skipped') else 1))
if __name__=='__main__':main()
