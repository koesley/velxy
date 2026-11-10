"""V42 Infinity Engine: deterministic, tenant-isolated decision intelligence."""
import html,json,math,statistics,time
from urllib.parse import urlencode
import empire_v19,nexus_v25

MAX_APPS=50
MAX_RECORDS=500

def scope(c,uid,wid=''):
 ws=c.execute('SELECT w.id,w.name FROM empire_workspaces w JOIN empire_members m ON m.workspace_id=w.id WHERE m.user_id=? ORDER BY w.created DESC LIMIT 100',(uid,)).fetchall()
 if not ws:return [],''
 ids={str(x[0]) for x in ws}
 wid=str(wid or ws[0][0])
 if wid not in ids or not empire_v19.role(c,uid,wid):raise ValueError('Workspace unavailable')
 return ws,wid

def safe_number(value):
 if isinstance(value,bool):return None
 try:
  n=float(value)
  return n if math.isfinite(n) and abs(n)<=1e12 else None
 except (TypeError,ValueError,OverflowError):return None

def app_signals(c,wid):
 apps=c.execute('SELECT id,name,schema_json,status FROM prime_apps WHERE workspace_id=? ORDER BY created DESC LIMIT ?',(wid,MAX_APPS)).fetchall()
 result=[]
 for aid,name,schema,status in apps:
  try:fields=json.loads(schema)
  except (TypeError,ValueError):fields=[]
  numeric=[f.get('name') for f in fields if isinstance(f,dict) and f.get('type')=='number' and isinstance(f.get('name'),str)]
  total=c.execute('SELECT count(*) FROM prime_records WHERE workspace_id=? AND app_id=?',(wid,aid)).fetchone()[0]
  raw=c.execute('SELECT data_json FROM prime_records WHERE workspace_id=? AND app_id=? ORDER BY created DESC,id DESC LIMIT ?',(wid,aid,MAX_RECORDS)).fetchall()
  data=[]
  for (item,) in raw:
   try:
    obj=json.loads(item)
    if isinstance(obj,dict):data.append(obj)
   except (ValueError,TypeError):pass
  metrics={}
  for field in numeric[:30]:
   values=[n for rec in data if (n:=safe_number(rec.get(field))) is not None]
   if not values:continue
   midpoint=len(values)//2
   recent=values[:midpoint];older=values[midpoint:]
   recent_mean=statistics.fmean(recent) if recent else None
   older_mean=statistics.fmean(older) if older else None
   change=(recent_mean-older_mean) if recent_mean is not None and older_mean is not None else None
   metrics[field]={'count':len(values),'average':round(statistics.fmean(values),3),'min':min(values),'max':max(values),'recent_minus_older':round(change,3) if change is not None else None}
  result.append({'id':aid,'name':name,'status':status,'total_records':total,'sampled_records':len(raw),'sample_limited':total>MAX_RECORDS,'numeric':metrics})
 return result

def goal_signals(c,uid,wid):
 goals=c.execute('SELECT id,title,metric,target FROM nexus_goals WHERE workspace_id=? ORDER BY created DESC LIMIT 100',(wid,)).fetchall()
 out=[]
 for gid,title,metric,target in goals:
  m=nexus_v25.measure(c,uid,wid,gid)
  value=m['value'];target=float(target)
  gap=round(target-value,3) if value is not None else None
  # No assumption that higher is better for every metric.
  snapshots=c.execute('SELECT value,created FROM nexus_snapshots WHERE workspace_id=? AND goal_id=? ORDER BY created DESC,id DESC LIMIT 2',(wid,gid)).fetchall()
  delta=round(snapshots[0][0]-snapshots[1][0],3) if len(snapshots)==2 else None
  out.append({'id':gid,'title':title,'metric':metric,'value':value,'target':target,'gap_to_target':gap,'snapshot_delta':delta,'sampled':m['sampled_records'],'limited':m['limited']})
 return out

def report(c,uid,wid=''):
 ws,wid=scope(c,uid,wid)
 if not wid:return {'workspace_id':None,'workspace_name':None,'apps':[],'goals':[],'opportunities':[],'limitations':['No workspace yet']}
 apps=app_signals(c,wid);goals=goal_signals(c,uid,wid)
 opportunities=[]
 for g in goals:
  if g['value'] is None:
   opportunities.append({'priority':'data-needed','title':g['title'],'evidence':'No valid measurement; verify record collection before deciding','link':'/nexus-intelligence'})
  elif g['gap_to_target']!=0:
   opportunities.append({'priority':'review','title':g['title'],'evidence':f"Current {g['value']}; target {g['target']}; signed target minus current {g['gap_to_target']}. Confirm desired direction before action.",'link':'/nexus-intelligence'})
 for a in apps:
  if a['sample_limited']:
   opportunities.append({'priority':'coverage','title':a['name'],'evidence':f"Only {MAX_RECORDS} of {a['total_records']} records analyzed. Interpret results as a recent sample.",'link':'/sentience'})
  elif a['total_records']==0:
   opportunities.append({'priority':'data-needed','title':a['name'],'evidence':'No business records yet. Add records before drawing conclusions.','link':'/genesis-prime'})
 # These are transparent rules, not AI forecasts or claimed profits.
 opportunities=sorted(opportunities,key=lambda x:({'data-needed':0,'review':1,'coverage':2}[x['priority']],x['title']))[:30]
 name=next(n for w,n in ws if str(w)==wid)
 return {'workspace_id':wid,'workspace_name':name,'apps':apps,'goals':goals,'opportunities':opportunities,'limitations':['Read-only, descriptive signals; no autonomous execution or profit forecasts','Application numeric statistics use up to 500 recent records per app','Signed goal gaps do not imply whether increasing or decreasing a metric is desirable']}

def render(c,uid,wid=''):
 r=report(c,uid,wid);esc=lambda x:html.escape(str(x),quote=True)
 if not r['workspace_id']:return '<section class="panel"><h1>Infinity Engine V42</h1><p>Create a workspace first.</p><a href="/empire">Create workspace</a></section>'
 wid=r['workspace_id'];wq=urlencode({'w':wid})
 h=['<section class="panel"><h1>∞ INFINITY ENGINE V42</h1><p>Business decision intelligence backed by your own workspace records. No AI-generated numbers, automatic actions, or revenue promises.</p><h2>'+esc(r['workspace_name'])+'</h2><p><a href="/infinity-engine.json?'+esc(wq)+'">Export JSON report</a> · <a href="/nexus-intelligence?'+esc(wq)+'">Manage measurable goals</a> · <a href="/nexus-reforged?'+esc(wq)+'">Command Center</a></p></section>']
 h.append('<section class="panel"><h2>Decision queue ('+str(len(r['opportunities']))+')</h2>')
 if not r['opportunities']:h.append('<p>No rule-based flags detected. This does not establish that your business has no risks.</p>')
 for o in r['opportunities']:
  h.append('<article style="border-top:1px solid #655777;padding:12px 0"><strong>'+esc(o['priority'].upper())+' · '+esc(o['title'])+'</strong><p>'+esc(o['evidence'])+'</p><a href="'+esc(o['link']+'?'+wq)+'">Review source →</a></article>')
 h.append('</section><section class="panel"><h2>Measurable goals</h2>')
 for g in r['goals']:
  h.append('<article style="border-top:1px solid #655777;padding:12px 0"><strong>'+esc(g['title'])+'</strong><p>'+esc(g['metric'])+': '+esc(g['value'] if g['value'] is not None else 'No valid data')+' · target '+esc(g['target'])+' · signed gap '+esc(g['gap_to_target'])+' · snapshot change '+esc(g['snapshot_delta'] if g['snapshot_delta'] is not None else 'Not enough snapshots')+'</p></article>')
 if not r['goals']:h.append('<p>No goals defined. Create a goal in Nexus Intelligence to track outcomes.</p>')
 h.append('</section><section class="panel"><h2>Application signals</h2>')
 for a in r['apps']:
  h.append('<article style="border-top:1px solid #655777;padding:12px 0"><h3>'+esc(a['name'])+'</h3><p>'+str(a['total_records'])+' total records · '+str(a['sampled_records'])+' sampled'+(' · SAMPLE LIMITED' if a['sample_limited'] else '')+'</p>')
  for field,m in a['numeric'].items():h.append('<p>'+esc(field)+': mean '+esc(m['average'])+' · range '+esc(m['min'])+' to '+esc(m['max'])+' · recent minus older '+esc(m['recent_minus_older'] if m['recent_minus_older'] is not None else 'insufficient data')+'</p>')
  h.append('</article>')
 h.append('</section><section class="panel"><h2>Interpretation and limits</h2><ul>'+''.join('<li>'+esc(s)+'</li>' for s in r['limitations'])+'</ul></section>')
 return ''.join(h)
