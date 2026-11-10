"""V56.12 Sovereign Business Guardian: manual, deterministic, workspace-scoped monitoring.
Only approved connector snapshots are evaluated; no background scheduler or external writes.
"""
import hashlib
import html
import json
import secrets
import time
from urllib.parse import quote
import sovereign_v56 as core

RULES = {
 'revenue_drop': ('Revenue decline', 'high'),
 'expense_surge': ('Expense increase', 'medium'),
 'negative_margin': ('Negative operating margin', 'high'),
 'missing_period': ('Missing recent period', 'medium'),
 'stale_source': ('No recent approved snapshot', 'medium'),
}

def setup(c):
 c.execute('CREATE TABLE IF NOT EXISTS sv56_guardian_runs(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,actor INTEGER NOT NULL,created INTEGER NOT NULL,source_fingerprint TEXT NOT NULL,findings INTEGER NOT NULL)')
 c.execute('CREATE TABLE IF NOT EXISTS sv56_guardian_alerts(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,rule TEXT NOT NULL,subject TEXT NOT NULL,severity TEXT NOT NULL,title TEXT NOT NULL,explanation TEXT NOT NULL,evidence TEXT NOT NULL,status TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL,UNIQUE(workspace_id,rule,subject))')
 c.execute('CREATE INDEX IF NOT EXISTS sv56_guardian_scope ON sv56_guardian_alerts(workspace_id,status,created)')
 c.execute('CREATE TABLE IF NOT EXISTS sv56_guardian_events(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,alert_id TEXT NOT NULL,actor INTEGER NOT NULL,action TEXT NOT NULL,created INTEGER NOT NULL)')

def _event(c,uid,wid,aid,action):
 c.execute('INSERT INTO sv56_guardian_events VALUES(?,?,?,?,?,?)',(secrets.token_hex(12),wid,aid,uid,action,int(time.time())))
 core.audit(c,uid,wid,'guardian_'+action,aid)

def evaluate(c,uid,wid):
 core.access(c,uid,wid,write=True)
 # Aggregate only approved batches. Avoid double counting reuploaded unchanged external IDs.
 rows=c.execute("""SELECT r.source_id,r.external_id,r.period,r.revenue,r.expenses,b.id
 FROM sv56_connector_records r JOIN sv56_connector_batches b ON b.id=r.batch_id AND b.workspace_id=r.workspace_id
 WHERE r.workspace_id=? AND b.status='applied' ORDER BY b.created,b.id""",(wid,)).fetchall()
 latest={}
 for sid,eid,period,revenue,expenses,bid in rows:latest[(sid,eid)]=(period,revenue,expenses,bid)
 grouped={}
 for (sid,eid),(period,revenue,expenses,bid) in latest.items():
  totals=grouped.setdefault(sid,{}).setdefault(period,[0.,0.,set()]);totals[0]+=revenue;totals[1]+=expenses;totals[2].add(bid)
 findings=[]
 def add(rule,sid,subject,explanation,evidence):
  findings.append((rule,sid+':'+subject,RULES[rule][1],RULES[rule][0],explanation,json.dumps(evidence,sort_keys=True)))
 now=time.gmtime();current=now.tm_year*12+now.tm_mon
 for sid,periods in grouped.items():
  dates=sorted(periods)
  for period in dates:
   revenue,expenses,bids=periods[period]
   if expenses>revenue:
    add('negative_margin',sid,period,'Expenses exceed revenue for '+period,{'period':period,'revenue':revenue,'expenses':expenses,'batch_ids':sorted(bids)})
  if len(dates)>=2:
   prev,curr=dates[-2:];pr,pe,pb=periods[prev];cr,ce,cb=periods[curr]
   evidence={'previous_period':prev,'current_period':curr,'previous_revenue':pr,'current_revenue':cr,'previous_expenses':pe,'current_expenses':ce,'batch_ids':sorted(pb|cb)}
   if pr>0 and cr<pr*.8:add('revenue_drop',sid,curr,'Revenue decreased by more than 20% compared with the preceding observed period',evidence)
   if pe>0 and ce>pe*1.25:add('expense_surge',sid,curr,'Expenses increased by more than 25% compared with the preceding observed period',evidence)
   py,pm=map(int,prev.split('-'));cy,cm=map(int,curr.split('-'))
   if (cy*12+cm)-(py*12+pm)>1:add('missing_period',sid,curr,'A gap exists between the two latest observed months',evidence)
  y,m=map(int,dates[-1].split('-'))
  if current-(y*12+m)>2:add('stale_source',sid,'latest','Latest approved data is more than two calendar months old',{'latest_period':dates[-1],'batch_ids':sorted(periods[dates[-1]][2])})
 fingerprint=hashlib.sha256(json.dumps(sorted((k,v[0],v[1],v[2],v[3]) for k,v in latest.items()),default=list).encode()).hexdigest()
 with c:
  run_id=secrets.token_hex(12);c.execute('INSERT INTO sv56_guardian_runs VALUES(?,?,?,?,?,?)',(run_id,wid,uid,int(time.time()),fingerprint,len(findings)))
  for rule,subject,severity,title,explanation,evidence in findings:
   existing=c.execute('SELECT id,status,evidence FROM sv56_guardian_alerts WHERE workspace_id=? AND rule=? AND subject=?',(wid,rule,subject)).fetchone()
   if existing:
    # Preserve acknowledged state for unchanged evidence. Reopen on material change.
    if existing[2]!=evidence:
     c.execute("UPDATE sv56_guardian_alerts SET evidence=?,explanation=?,status='open',updated=? WHERE id=? AND workspace_id=?",(evidence,explanation,int(time.time()),existing[0],wid))
     _event(c,uid,wid,existing[0],'updated')
   else:
    aid=secrets.token_hex(12)
    c.execute('INSERT INTO sv56_guardian_alerts VALUES(?,?,?,?,?,?,?,?,?,?,?)',(aid,wid,rule,subject,severity,title,explanation,evidence,'open',int(time.time()),int(time.time())))
    _event(c,uid,wid,aid,'detected')
  _event(c,uid,wid,run_id,'scan_completed')
 return {'run_id':run_id,'findings':len(findings),'approved_records':len(latest),'fingerprint':fingerprint}

def update_status(c,uid,wid,aid,status):
 core.access(c,uid,wid,write=True)
 if status not in ('open','acknowledged','resolved'):raise ValueError('Invalid alert status')
 with c:
  n=c.execute('UPDATE sv56_guardian_alerts SET status=?,updated=? WHERE id=? AND workspace_id=?',(status,int(time.time()),aid,wid)).rowcount
  if n!=1:raise ValueError('Alert not found in workspace')
  _event(c,uid,wid,aid,'status_'+status)

def history(c,uid,wid):
 core.access(c,uid,wid)
 alerts=[dict(id=i,rule=r,subject=sub,severity=sev,title=t,explanation=ex,evidence=json.loads(ev),status=st,created=ts) for i,r,sub,sev,t,ex,ev,st,ts in c.execute('SELECT id,rule,subject,severity,title,explanation,evidence,status,created FROM sv56_guardian_alerts WHERE workspace_id=? ORDER BY CASE severity WHEN "high" THEN 0 WHEN "medium" THEN 1 ELSE 2 END,updated DESC LIMIT 200',(wid,))]
 runs=[dict(id=i,created=ts,findings=n,source_fingerprint=f) for i,ts,n,f in c.execute('SELECT id,created,findings,source_fingerprint FROM sv56_guardian_runs WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 50',(wid,))]
 events=[dict(alert_id=a,action=act,created=ts) for a,act,ts in c.execute('SELECT alert_id,action,created FROM sv56_guardian_events WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 100',(wid,))]
 return {'alerts':alerts,'runs':runs,'events':events,'rules':RULES,'limitations':['Checks run only when manually requested.','Uses approved connector CSV snapshots, not live accounting data.','Alerts are indicators, not proof of fraud or causation.','No automatic execution or external notifications.']}

def render(c,uid,csrf,wid):
 data=history(c,uid,wid);e=lambda x:html.escape(str(x),quote=True)
 counts={s:sum(a['status']==s for a in data['alerts']) for s in ('open','acknowledged','resolved')}
 cards=''.join('<article class="guardian-alert"><div class="guardian-alert-top"><span class="guardian-pill '+e(a['severity'])+'">'+e(a['severity']).upper()+'</span><span class="guardian-pill muted">'+e(a['status'])+'</span></div><h3>'+e(a['title'])+'</h3><p>'+e(a['explanation'])+'</p><small>Source: '+e(a['subject'])+'</small><details><summary>View supporting evidence</summary><pre>'+e(json.dumps(a['evidence'],indent=2))+'</pre></details><form method="post" action="/sovereign-guardian-v56"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="alert_id" value="'+e(a['id'])+'"><input type="hidden" name="action" value="status"><select name="status"><option value="open">Open</option><option value="acknowledged">Acknowledged</option><option value="resolved">Resolved</option></select><button>Update status</button></form></article>' for a in data['alerts']) or '<div class="guardian-empty">No alerts yet. Run a scan after approving connector snapshots.</div>'
 return '<div class="guardian"><section class="guardian-hero"><span class="guardian-kicker">✦ VELXTRIA · SOVEREIGN INTELLIGENCE</span><h1>Business Guardian<span class="guardian-dot">.</span></h1><p>Watch what matters. Review evidence. Stay in control.</p><div class="guardian-hero-actions"><form method="post" action="/sovereign-guardian-v56"><input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'"><input type="hidden" name="action" value="scan"><button>✦ Run health scan</button></form><a class="guardian-secondary" href="/sovereign-guardian-v56.json?w='+quote(wid,safe='')+'">Export JSON ↗</a></div></section><div class="guardian-metrics"><article><small>OPEN ALERTS</small><strong>'+str(counts['open'])+'</strong><span>Need review</span></article><article><small>ACKNOWLEDGED</small><strong>'+str(counts['acknowledged'])+'</strong><span>Under consideration</span></article><article><small>RESOLVED</small><strong>'+str(counts['resolved'])+'</strong><span>Marked complete</span></article><article><small>HEALTH SCANS</small><strong>'+str(len(data['runs']))+'</strong><span>Latest 50 runs</span></article></div><section class="guardian-section"><div class="guardian-heading"><div><span class="guardian-kicker">MONITORING CENTER</span><h2>Signals &amp; alerts</h2></div><span class="guardian-caption">Evidence-backed · Workspace isolated</span></div><div class="guardian-grid">'+cards+'</div></section><section class="guardian-section"><div class="guardian-heading"><div><span class="guardian-kicker">TRANSPARENCY</span><h2>Monitoring boundaries</h2></div></div><p>Manual scans use only approved connector snapshots. No scheduled monitoring, live integrations, automated remediation, or financial guarantees. Resolve alerts only after checking the underlying business records.</p></section></div>'
