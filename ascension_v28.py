"""V28 Ascension: accessible, workspace-scoped customer home. Read-only."""
import html
import empire_v19
import foundation_v26
import launchpad_v27

def esc(value): return html.escape(str(value),quote=True)

# Only local, reviewed destinations may be emitted into dashboard links.
SAFE_ROUTES=frozenset(('/genesis-prime','/oracle','/autonomy','/nexus-intelligence','/launchpad','/foundation','/integration'))
def route_url(path,wid):
 if path not in SAFE_ROUTES:raise ValueError('Unsupported dashboard destination')
 from urllib.parse import urlencode
 return esc(path+'?'+urlencode({'w':str(wid)}))

TOOLS=[('Applications','Build and publish business applications','/genesis-prime','01'),('AI Oracle','Ask evidence-based questions about records','/oracle','02'),('Automation','Review rules and approved actions','/autonomy','03'),('Strategy Center','Create goals and evaluate proposals','/nexus-intelligence','04'),('Customer Pilots','Track onboarding and feedback','/launchpad','05'),('Data Protection','Check integrity and create backups','/foundation','06'),('Integration Journey','Follow setup through customer feedback','/integration','07')]

def dashboard(c,uid,wid=''):
 ws=foundation_v26.workspaces(c,uid)
 if not ws:return '<div class="ascension"><section class="asc-hero"><span class="asc-kicker">VELXTRIA / ASCENSION</span><h1>Build your business workspace.</h1><p>Create your first workspace in Empire to unlock the command center.</p><a class="asc-primary" href="/empire">Create workspace →</a></section></div>'
 if not wid:wid=ws[0][0]
 if wid not in {w[0] for w in ws} or not empire_v19.role(c,uid,wid):raise ValueError('Workspace unavailable')
 name=next(w[1] for w in ws if w[0]==wid)
 opts=''.join('<option value="'+esc(w[0])+'"'+(' selected' if w[0]==wid else '')+'>'+esc(w[1])+'</option>' for w in ws)
 counts=foundation_v26.overview(c,uid,wid)
 cards=''.join('<article class="asc-metric"><span>'+esc(label)+'</span><strong>'+esc(value)+'</strong></article>' for label,value in counts.items())
 # Customer-pilot signals are read-only and always scoped to the selected workspace.
 pilot_rows=c.execute(
  "SELECT status, COUNT(*) FROM launchpad_pilots WHERE workspace_id=? GROUP BY status",
  (wid,),
 ).fetchall()
 pilot_counts=dict(pilot_rows)
 feedback_row=c.execute(
  "SELECT COUNT(*), AVG(rating) FROM launchpad_feedback WHERE workspace_id=?",
  (wid,),
 ).fetchone()
 feedback_count=int(feedback_row[0] or 0)
 average_rating=feedback_row[1]
 # Explicit customer-risk signal: low scores require human review, not auto-action.
 low_rating_row=c.execute(
  "SELECT COUNT(*) FROM launchpad_feedback WHERE workspace_id=? AND rating<=2",
  (wid,),
 ).fetchone()
 low_rating_count=int(low_rating_row[0] or 0)
 if low_rating_count:
  pilot_alert=('<div class="asc-pilot-alert" role="status"><div><strong>Customer feedback needs attention</strong><p>'
   +esc(low_rating_count)+' rating(s) of 2/5 or lower were recorded. Review the feedback and follow up with customers before expanding this pilot.</p></div>'
   +'<a class="asc-secondary" href="'+route_url('/launchpad',wid)+'">Review feedback ↗</a></div>')
 else:
  pilot_alert=('<p class="asc-pilot-clear">No ratings of 2/5 or lower have been recorded in this workspace.</p>' if feedback_count else
   '<p class="asc-pilot-clear">Collect pilot feedback to identify customer risks.</p>')
 pilot_metrics=(
  ('Active pilots',pilot_counts.get('active',0)),
  ('Completed pilots',pilot_counts.get('completed',0)),
  ('Feedback received',feedback_count),
  ('Average pilot rating',format(average_rating,'.1f')+' / 5' if average_rating is not None else 'No ratings yet'),
 )
 pilot_cards=''.join(
  '<article class="asc-metric"><span>'+esc(label)+'</span><strong>'+esc(value)+'</strong></article>'
  for label,value in pilot_metrics
 )
 checks=launchpad_v27.evidence(c,wid)
 done=sum(bool(ok) for _,ok,_ in checks)
 # Prioritize the first unmet, evidence-backed milestone; never imply automated execution.
 pending=[(label,url) for label,ok,url in checks if not ok]
 if low_rating_count:
  next_step=('<section class="asc-next" aria-labelledby="asc-next-title"><div><span class="asc-kicker">PRIORITY CUSTOMER RISK</span><h2 id="asc-next-title">Review low-rated customer feedback</h2><p>'
   +esc(low_rating_count)+' rating(s) of 2/5 or lower need a human review. Investigate the feedback before continuing onboarding or expanding the pilot.</p></div>'
   +'<a class="asc-primary" href="'+route_url('/launchpad',wid)+'">Review customer feedback ↗</a></section>')
 elif pending:
  next_label,next_url=pending[0]
  next_step=('<section class="asc-next" aria-labelledby="asc-next-title"><div><span class="asc-kicker">RECOMMENDED NEXT ACTION</span><h2 id="asc-next-title">'+esc(next_label)+'</h2><p>This onboarding requirement has no qualifying saved evidence yet. Open the relevant tool to complete it.</p></div><a class="asc-primary" href="'+route_url(next_url,wid)+'">Continue setup ↗</a></section>')
 else:
  next_step=('<section class="asc-next" aria-labelledby="asc-next-title"><div><span class="asc-kicker">ONBOARDING MILESTONE</span><h2 id="asc-next-title">Workspace checklist complete</h2><p>All three saved-data requirements are met. Review pilot feedback before treating the workspace as customer-ready.</p></div><a class="asc-primary" href="'+route_url('/launchpad',wid)+'">Review customer pilots ↗</a></section>')
 steps=''.join('<li><span aria-hidden="true">'+('✓' if ok else '○')+'</span><div><strong>'+esc(label)+'</strong><a href="'+route_url(url,wid)+'">'+('Review' if ok else 'Get started')+' →</a></div></li>' for label,ok,url in checks)
 tools=''.join('<a class="asc-tool" href="'+route_url(url,wid)+'"><span class="asc-number">'+num+'</span><strong>'+esc(label)+'</strong><small>'+esc(desc)+'</small><span class="asc-arrow" aria-hidden="true">↗</span></a>' for label,desc,url,num in TOOLS)
 return ('<div class="ascension"><section class="asc-hero"><div class="asc-top"><span class="asc-kicker">VELXTRIA / COMMAND OS</span><span class="asc-tag">WORKSPACE INTELLIGENCE</span></div><h1>One workspace.<br><em>Every advantage.</em></h1><p>A focused operating surface for building applications, reviewing intelligence, managing approvals, and tracking readiness. Every metric comes from authorized workspace records.</p><a class="asc-primary" href="'+route_url('/genesis-prime',wid)+'">Open application builder ↗</a></section>'
 '<nav class="asc-quicknav" aria-label="Command center sections"><a href="#asc-overview">Overview</a><a href="#asc-toolkit">Capabilities</a><a href="#asc-onboarding">Readiness</a></nav><section id="asc-overview" class="asc-switch"><div><span class="asc-kicker">ACTIVE WORKSPACE</span><h2>'+esc(name)+'</h2></div><form method="get" action="/ascension"><label for="asc-workspace">Switch workspace</label><select id="asc-workspace" name="w">'+opts+'</select><button type="submit">Switch</button></form></section>'
 '<section aria-label="Workspace metrics" class="asc-metrics">'+cards+'</section><section aria-label="Customer pilot outcomes" class="asc-pilots"><div class="asc-sectionhead"><div><span class="asc-kicker">CUSTOMER VALIDATION</span><h2>Real pilot outcomes</h2></div></div><div class="asc-metrics">'+pilot_cards+'</div>'+pilot_alert+'<p>Counts and ratings come from saved feedback in this workspace only; they are not forecasts or simulated results.</p></section>'+next_step+
 '<section class="asc-columns"><div id="asc-toolkit" class="asc-panel"><div class="asc-sectionhead"><div><span class="asc-kicker">YOUR TOOLKIT</span><h2>Everything in one place</h2></div></div><div class="asc-tools">'+tools+'</div></div>'
 '<aside id="asc-onboarding" class="asc-panel"><span class="asc-kicker">GETTING STARTED</span><h2>Onboarding progress</h2><p>'+str(done)+' of '+str(len(checks))+' requirements completed</p><div class="asc-track" role="progressbar" aria-valuemin="0" aria-valuemax="'+str(len(checks))+'" aria-valuenow="'+str(done)+'" aria-label="Onboarding steps completed"><span style="width:'+str(int(100*done/max(1,len(checks))))+'%"></span></div><ol class="asc-steps">'+steps+'</ol><a class="asc-secondary" href="'+route_url('/launchpad',wid)+'">Open pilot launchpad ↗</a></aside></section>'
 '<section class="asc-footnote">Counts are derived from your authorized workspace records. This dashboard does not run automations, change records, or certify production readiness.</section></div>')

CSS=r"""
/* Ascension Command OS: isolated, responsive, accessible visual system */
.ascension{--asc-purple:#b49aff;--asc-ink:#f4f0ff;--asc-muted:#b6aec8;--asc-border:rgba(193,169,255,.17);color:var(--asc-ink);max-width:1240px;margin:0 auto;font-family:inherit}
.ascension *{box-sizing:border-box}.ascension .asc-hero{padding:clamp(28px,5vw,66px);border:1px solid var(--asc-border);border-radius:24px;background:radial-gradient(ellipse at 86% 10%,rgba(116,65,204,.45),transparent 55%),linear-gradient(135deg,#181327,#0d0b17);margin-bottom:18px}
.ascension .asc-top{display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap}.ascension .asc-kicker{color:var(--asc-purple);font-size:11px;letter-spacing:.19em;font-weight:800}.ascension .asc-tag{border:1px solid var(--asc-border);padding:6px 10px;border-radius:100px;color:var(--asc-muted);font-size:10px;letter-spacing:.08em}.ascension h1{font-size:clamp(36px,5.4vw,72px);letter-spacing:-.055em;line-height:1.07;margin:26px 0 20px;color:white}.ascension h1 em{font-style:normal;color:var(--asc-purple)}.ascension p{color:var(--asc-muted);line-height:1.7;max-width:670px}.ascension a{color:inherit;text-decoration:none}.ascension .asc-primary,.ascension .asc-secondary{display:inline-block;padding:12px 19px;border-radius:12px;font-weight:700;margin-top:15px;background:var(--asc-purple);color:#160c27}.ascension .asc-secondary{background:rgba(180,154,255,.12);color:var(--asc-ink);border:1px solid var(--asc-border)}.ascension .asc-primary:hover,.ascension .asc-secondary:hover{filter:brightness(1.13)}.ascension .asc-switch,.ascension .asc-panel,.ascension .asc-metric{border:1px solid var(--asc-border);background:#161321;border-radius:18px}.ascension .asc-switch{padding:20px 25px;display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap}.ascension h2{color:white;font-size:22px;margin:8px 0}.ascension .asc-switch form{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.ascension .asc-switch label{color:var(--asc-muted);font-size:12px}.ascension select,.ascension button{border:1px solid var(--asc-border);border-radius:9px;padding:10px;background:#29223a;color:white}.ascension button{cursor:pointer}.ascension .asc-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:16px 0}.ascension .asc-metric{padding:23px}.ascension .asc-metric span{display:block;color:var(--asc-muted);font-size:12px}.ascension .asc-metric strong{font-size:35px;display:block;margin-top:10px;color:white}.ascension .asc-columns{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(290px,1fr);gap:16px}.ascension .asc-panel{padding:25px}.ascension .asc-tools{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:20px}.ascension .asc-tool{position:relative;display:flex;flex-direction:column;gap:10px;padding:20px;border:1px solid var(--asc-border);border-radius:14px;background:#201a30;min-height:150px;transition:background .15s}.ascension .asc-tool:hover{background:#302544}.ascension .asc-number{font-size:11px;color:var(--asc-purple);font-weight:800}.ascension .asc-tool strong{color:white}.ascension .asc-tool small{font-size:12px;color:var(--asc-muted);line-height:1.45;padding-right:12px}.ascension .asc-arrow{position:absolute;right:16px;top:15px;color:var(--asc-purple)}.ascension .asc-track{height:9px;background:#342b45;border-radius:100px;overflow:hidden}.ascension .asc-track span{height:100%;display:block;background:var(--asc-purple)}.ascension .asc-steps{padding:0;list-style:none;margin:24px 0}.ascension .asc-steps li{display:flex;gap:12px;margin:0 0 18px}.ascension .asc-steps li>span{color:var(--asc-purple)}.ascension .asc-steps strong{display:block;font-size:13px}.ascension .asc-steps a{color:var(--asc-purple);font-size:12px;display:inline-block;margin-top:5px}.ascension .asc-footnote{font-size:12px;color:var(--asc-muted);padding:20px 3px}
@media(max-width:800px){.ascension .asc-columns{grid-template-columns:1fr}.ascension .asc-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:480px){.ascension .asc-tools{grid-template-columns:1fr}.ascension .asc-switch form{width:100%}.ascension .asc-switch select{max-width:100%}.ascension .asc-hero{border-radius:15px}}
"""
CSS+=r"""
 
/* Command OS visual elevation: progressive enhancement without JS dependencies */
.ascension{--asc-purple:#c3b3ff;--asc-muted:#c3bdd3;--asc-border:rgba(190,173,255,.22);position:relative;isolation:isolate}
.ascension:before{content:"";position:absolute;z-index:-1;inset:-24px -12px auto;height:620px;pointer-events:none;background:radial-gradient(ellipse at 60% 0%,rgba(95,67,185,.17),transparent 70%)}
.ascension .asc-hero{position:relative;overflow:hidden;min-height:340px;background:radial-gradient(circle at 85% 25%,rgba(143,98,245,.30),transparent 40%),radial-gradient(circle at 15% 90%,rgba(34,112,164,.18),transparent 45%),linear-gradient(125deg,#161127,#090d19);box-shadow:0 20px 80px rgba(0,0,0,.19)}
.ascension .asc-hero:after{content:"";position:absolute;right:-60px;bottom:-180px;width:430px;height:430px;border:1px solid rgba(198,183,255,.15);border-radius:50%;box-shadow:0 0 0 42px rgba(198,183,255,.025),0 0 0 90px rgba(198,183,255,.025);pointer-events:none}
.ascension .asc-hero>*{position:relative;z-index:1}
.ascension .asc-hero h1{max-width:830px;text-wrap:balance}
.ascension .asc-quicknav{display:flex;gap:6px;flex-wrap:wrap;padding:7px;margin:0 0 16px;background:#14111f;border:1px solid var(--asc-border);border-radius:14px}
.ascension .asc-quicknav a{display:inline-flex;align-items:center;min-height:42px;padding:9px 17px;border-radius:10px;color:var(--asc-muted);font-size:13px;font-weight:700}
.ascension .asc-quicknav a:hover,.ascension .asc-quicknav a:focus-visible{background:#2a2240;color:white}
.ascension .asc-metric{background:linear-gradient(160deg,#211a32,#121522);position:relative;overflow:hidden}
.ascension .asc-metric:before{content:"";position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,#ad91ff,transparent)}
.ascension .asc-metric strong{font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.ascension .asc-tool{background:linear-gradient(145deg,#241d35,#191827);transition:transform .2s ease,border-color .2s ease,background .2s ease}
.ascension .asc-tool:hover{transform:translateY(-3px);border-color:rgba(202,182,255,.6);background:#2c2442}
.ascension .asc-panel{box-shadow:0 12px 36px rgba(0,0,0,.12)}
.ascension :is(a,button,select):focus-visible{outline:3px solid #e0d5ff;outline-offset:3px}
.ascension .asc-steps li{padding:10px 0;border-bottom:1px solid rgba(193,169,255,.09)}
.ascension .asc-steps li:last-child{border-bottom:0}
.ascension .asc-footnote{border-top:1px solid var(--asc-border);margin-top:22px}
@media(max-width:600px){.ascension .asc-hero{min-height:0}.ascension .asc-hero:after{opacity:.4}.ascension .asc-metric{padding:17px}.ascension .asc-metric strong{font-size:clamp(24px,7vw,35px)}.ascension .asc-panel{padding:18px}.ascension .asc-quicknav a{flex:1;justify-content:center;padding:9px}}
@media(prefers-reduced-motion:reduce){.ascension .asc-tool{transition:none}.ascension .asc-tool:hover{transform:none}}
"""

CSS+=r"""
/* Evidence-based next action: real workspace checklist state, no simulated analytics. */
.ascension .asc-next{display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap;padding:24px 28px;margin:0 0 16px;border:1px solid rgba(158,221,232,.27);border-radius:18px;background:linear-gradient(110deg,#14232e,#1d1932 75%)}
.ascension .asc-next h2{font-size:clamp(20px,2.4vw,28px);margin:8px 0}
.ascension .asc-next p{font-size:13px;margin:0;max-width:610px}
.ascension .asc-next .asc-primary{margin:0;white-space:normal;text-align:center}
@media(max-width:600px){.ascension .asc-next{padding:20px}.ascension .asc-next .asc-primary{width:100%}}
"""

CSS+=r"""
.ascension .asc-pilots{margin:20px 0 16px;padding:20px 22px;border:1px solid var(--asc-border);border-radius:18px;background:#131323}
.ascension .asc-pilots .asc-sectionhead{margin-bottom:14px}
.ascension .asc-pilots .asc-metrics{margin-bottom:8px}
.ascension .asc-pilots p{font-size:12px;margin:12px 0 0}
"""

CSS+=r"""
.ascension .asc-pilot-alert{border:1px solid rgba(255,190,116,.45);background:rgba(150,83,30,.13);border-radius:14px;padding:14px 18px;display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap}
.ascension .asc-pilot-alert strong{color:#ffcf97}.ascension .asc-pilot-alert p{margin:6px 0 0;color:var(--asc-ink)}
.ascension .asc-pilot-alert .asc-secondary{margin:0;white-space:nowrap}
.ascension .asc-pilot-clear{margin:12px 0;color:var(--asc-muted)}
"""
