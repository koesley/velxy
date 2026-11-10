"""OMNIS opportunity radar: deterministic, evidence-labeled suggestions, never profit promises."""
import html, json, time, secrets
import sovereign_v56 as core
import sovereign_business_graph_v57 as graph

def init(c):
 core.setup(c)
 c.execute("CREATE TABLE IF NOT EXISTS ov57_opportunity_reviews(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,fingerprint TEXT NOT NULL,decision TEXT NOT NULL CHECK(decision IN ('watch','investigate','dismiss')),reason TEXT NOT NULL,reviewed_by INTEGER NOT NULL,reviewed_at INTEGER NOT NULL,UNIQUE(workspace_id,fingerprint))")

def suggestions(c,uid,wid):
 core.access(c,uid,wid);init(c)
 d=graph.overview(c,uid,wid);nodes=d['nodes'];edges=d['edges'];degree={n['id']:0 for n in nodes}
 for e in edges:
  for key in ('source_id','target_id'):
   if e[key] in degree:degree[e[key]]+=1
 out=[]
 for n in nodes:
  if degree[n['id']]==0:
   out.append({'id':'unconnected:'+n['id'],'kind':'visibility_gap','title':'Map dependencies for '+n['name'],'detail':'This entity has no recorded relationships. Review whether important dependencies are missing.','evidence':n['source'],'confidence':'descriptive','priority':2})
  if n['confidence']=='hypothesis':
   out.append({'id':'hypothesis:'+n['id'],'kind':'evidence_gap','title':'Validate '+n['name'],'detail':'This entity is marked as a hypothesis. Gather independent evidence before acting.','evidence':n['source'],'confidence':'unverified','priority':1})
 for n in nodes:
  dependents=sum(e['target_id']==n['id'] and e['relation']=='depends_on' for e in edges)
  if dependents>=2:out.append({'id':'dependency:'+n['id'],'kind':'concentration_risk','title':'Review shared dependency: '+n['name'],'detail':str(dependents)+' recorded entities depend on this item. Consider continuity planning.','evidence':'Recorded business graph relationships','confidence':'descriptive','priority':0})
 out.sort(key=lambda x:(x['priority'],x['id']))
 reviews={r[0]:{'decision':r[1],'reason':r[2],'reviewed_at':r[3]} for r in c.execute('SELECT fingerprint,decision,reason,reviewed_at FROM ov57_opportunity_reviews WHERE workspace_id=?',(wid,))}
 for item in out:item['review']=reviews.get(item['id'])
 return {'workspace_id':wid,'role':d['role'],'suggestions':out[:100],'total':len(out),'limitations':['Heuristics from manually entered data, not AI-generated predictions.','No estimated revenue, guaranteed outcomes, or automatic execution.','Capped at 250 graph nodes and 500 relationships.']}

def review(c,uid,wid,fingerprint,decision,reason):
 core.access(c,uid,wid,write=True);init(c)
 if decision not in ('watch','investigate','dismiss') or not isinstance(reason,str) or not reason.strip() or len(reason)>500:raise ValueError('Invalid review')
 valid={x['id'] for x in suggestions(c,uid,wid)['suggestions']}
 if fingerprint not in valid:raise ValueError('Opportunity not found in this workspace')
 with c:
  c.execute('INSERT INTO ov57_opportunity_reviews VALUES(?,?,?,?,?,?,?) ON CONFLICT(workspace_id,fingerprint) DO UPDATE SET decision=excluded.decision,reason=excluded.reason,reviewed_by=excluded.reviewed_by,reviewed_at=excluded.reviewed_at',(secrets.token_hex(12),wid,fingerprint,decision,reason.strip(),uid,int(time.time())))
  core.audit(c,uid,wid,'omnis_opportunity_reviewed',fingerprint)

def render(c,uid,wid,csrf):
 d=suggestions(c,uid,wid);h=lambda x:html.escape(str(x),quote=True)
 cards=[]
 for x in d['suggestions']:
  rv=x['review'];status=h(rv['decision']) if rv else 'Unreviewed'
  form=''
  if d['role'] in ('owner','editor'):
   form='<form method="post" action="/sovereign-opportunities-v57"><input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'"><input type="hidden" name="fingerprint" value="'+h(x['id'])+'"><label>Review decision<select name="decision"><option>investigate</option><option>watch</option><option>dismiss</option></select></label><label>Reason<input name="reason" required maxlength="500"></label><button name="action" value="review">Save review</button></form>'
  cards.append('<article class="ov-job"><strong>'+h(x['title'])+'</strong><p>'+h(x['detail'])+'</p><small>'+h(x['kind'])+' · '+h(x['confidence'])+' · '+status+'</small><p><small>Evidence: '+h(x['evidence'])+'</small></p>'+form+'</article>')
 return '<section class="ov-hero"><span>PROJECT OMNIS · OPPORTUNITY RADAR</span><h1>Find the gaps worth investigating.</h1><p>Evidence-labeled, deterministic checks across your Living Business Graph. Recommendations are not forecasts or automatic actions.</p><a href="/sovereign-business-graph-v57?w='+h(wid)+'">Open Business Graph</a></section><section class="ov-panel"><h2>'+str(d['total'])+' opportunities identified</h2>'+(''.join(cards) or '<p>Add entities and relationships in Business Graph to start exploring.</p>')+'</section>'
