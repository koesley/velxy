"""V41: Workspace-scoped unified product navigation and discovery hub. Read-only."""
import html
from urllib.parse import urlencode
import empire_v19
import foundation_v26
import launchpad_v27

CATEGORIES = (
 ('Operate', 'Run your business', (('Business workspace','/workspace','Manage everyday business records'),('Applications','/genesis-prime','Build business apps'),('Business operator','/operator','Operational tools'),('Automation','/autonomy','Approval-based workflows'))),
 ('Understand', 'Turn records into decisions', (('Oracle','/oracle','Ask questions backed by data'),('Intelligence','/nexus-intelligence','Goals and recommendations'),('Insights','/sentience','Explore trends'),('Overview','/ascension','Workspace summary'))),
 ('Grow', 'Launch and improve', (('Customer launch','/atlas','Guided onboarding'),('Pilot feedback','/launchpad','Customer pilot tracker'),('Issue tracker','/first-contact','Capture customer problems'),('Improvement plans','/horizon','Track fixes'))),
 ('Trust', 'Verification and operations', (('Foundation','/foundation','Integrity and backup tools'),('Sentinel','/sentinel','Regression evidence'),('Apex','/apex','HTTP customer journey'),('Catalyst','/catalyst','Release preflight'))),
)
CSS = '''
.v41{max-width:1200px;margin:auto;color:#f5f1ff}.v41 *{box-sizing:border-box}.v41-hero{background:radial-gradient(ellipse at 85% 10%,#49317c,transparent 60%),#171222;border:1px solid #4a3868;border-radius:22px;padding:clamp(22px,5vw,52px)}.v41 h1{font-size:clamp(30px,5vw,56px);letter-spacing:-.045em;margin:8px 0}.v41 p,.v41 small{color:#c6bbdc}.v41 a{text-decoration:none;color:inherit}.v41-kicker{color:#b99cff;letter-spacing:.16em;font-size:11px;font-weight:800}.v41-toolbar{display:flex;gap:12px;flex-wrap:wrap;align-items:end;margin:20px 0}.v41-toolbar label{display:flex;flex-direction:column;gap:5px}.v41 input,.v41 select,.v41 button{background:#292139;border:1px solid #69538a;color:white;padding:11px;border-radius:10px}.v41 input{flex:1;min-width:180px}.v41 button{cursor:pointer}.v41-section{margin:24px 0}.v41-section h2{margin:0 0 4px}.v41-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:14px}.v41-card{display:block;padding:18px;background:#1d172b;border:1px solid #48385e;border-radius:14px;min-height:110px}.v41-card:hover,.v41-card:focus-visible{border-color:#b99cff;background:#2a2040}.v41-card strong{display:block;font-size:16px}.v41-card small{display:block;margin-top:10px;line-height:1.5}.v41-progress{height:10px;background:#342a48;border-radius:100px;overflow:hidden;margin:15px 0}.v41-progress span{display:block;height:100%;background:#b99cff}.v41-metrics{display:flex;gap:12px;flex-wrap:wrap}.v41-metric{padding:14px 20px;background:#20192f;border:1px solid #48385e;border-radius:12px}.v41-metric strong{font-size:24px;display:block}.v41-empty{padding:28px;background:#20192f;border-radius:12px}.v41 [hidden]{display:none!important}@media(max-width:760px){.v41-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:500px){.v41-grid{grid-template-columns:1fr}}
'''
def esc(x): return html.escape(str(x),quote=True)
def link(url,wid): return url+'?'+urlencode({'w':wid}) if wid else url
def workspace_options(c,uid,wid):
 workspaces=foundation_v26.workspaces(c,uid)
 if not workspaces:return [],''
 ids={str(w[0]) for w in workspaces}
 wid=str(wid or workspaces[0][0])
 if wid not in ids or not empire_v19.role(c,uid,wid):raise ValueError('Workspace unavailable')
 return workspaces,wid

def render(c,uid,wid=''):
 workspaces,wid=workspace_options(c,uid,wid)
 if not workspaces:
  return '<div class="v41"><section class="v41-hero"><span class="v41-kicker">V41 / NEXUS REFORGED</span><h1>One home for your business.</h1><p>Create your first workspace to unlock the unified platform.</p><a class="v41-card" href="/empire">Create a workspace →</a></section></div>'
 name=next(str(w[1]) for w in workspaces if str(w[0])==wid)
 options=''.join('<option value="'+esc(w[0])+'"'+(' selected' if str(w[0])==wid else '')+'>'+esc(w[1])+'</option>' for w in workspaces)
 checks=launchpad_v27.evidence(c,wid)
 done=sum(bool(ok) for _,ok,_ in checks)
 try: metrics=foundation_v26.overview(c,uid,wid)
 except (KeyError,ValueError):metrics={}
 metric_html=''.join('<div class="v41-metric"><strong>'+esc(v)+'</strong><small>'+esc(k)+'</small></div>' for k,v in list(metrics.items())[:4])
 sections=[]
 for title,description,tools in CATEGORIES:
  cards=''.join('<a class="v41-card" data-search="'+esc((label+' '+detail).lower())+'" href="'+esc(link(url,wid))+'"><strong>'+esc(label)+' ↗</strong><small>'+esc(detail)+'</small></a>' for label,url,detail in tools)
  sections.append('<section class="v41-section"><h2>'+esc(title)+'</h2><p>'+esc(description)+'</p><div class="v41-grid">'+cards+'</div></section>')
 next_step=next(((label,url) for label,ok,url in checks if not ok),None)
 next_html=('<a class="v41-card" href="'+esc(link(next_step[1],wid))+'"><strong>Continue: '+esc(next_step[0])+' ↗</strong><small>Next suggested onboarding step</small></a>' if next_step else '<p>All tracked onboarding requirements are complete.</p>')
 return ('<div class="v41"><section class="v41-hero"><span class="v41-kicker">VELXTRIA / V41 NEXUS REFORGED</span><h1>One platform. One workspace.</h1><p>'+esc(name)+' · Your business tools, organized by what you want to accomplish.</p><div class="v41-metrics">'+metric_html+'</div></section>'
 '<form class="v41-toolbar" action="/nexus-reforged" method="get"><label>Active workspace<select name="w">'+options+'</select></label><button type="submit">Switch workspace</button></form>'
 '<div class="v41-toolbar"><label for="v41search">Find a tool</label><input id="v41search" type="search" placeholder="Search applications, reports, strategy…" autocomplete="off" aria-label="Filter tools"></div>'
 '<section class="v41-section"><h2>Your launch progress</h2><p>'+str(done)+' of '+str(len(checks))+' steps complete</p><div class="v41-progress" role="progressbar" aria-valuemin="0" aria-valuemax="'+str(len(checks))+'" aria-valuenow="'+str(done)+'"><span style="width:'+str(int(100*done/max(1,len(checks))))+'%"></span></div>'+next_html+'</section>'
 +''.join(sections)+'<p><small>Workspace information is read-only. Availability of some tools depends on local mode and user permissions.</small></p></div>'
 '<script>(function(){const i=document.getElementById("v41search");if(!i)return;i.addEventListener("input",function(){const q=i.value.trim().toLowerCase();document.querySelectorAll(".v41-card[data-search]").forEach(function(a){a.hidden=!a.dataset.search.includes(q)});document.querySelectorAll(".v41-section").forEach(function(s){if(s.querySelector(".v41-grid")){s.hidden=!Array.from(s.querySelectorAll(".v41-card[data-search]")).some(function(a){return !a.hidden})}})})})();</script>')
