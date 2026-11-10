"""V23 Sentience: tenant-scoped, deterministic insights and owner-approved draft actions."""
import html,json,secrets,time,math
import empire_v19,genesis_prime_v20 as prime,autonomy_v22

def setup(c):
 c.execute('CREATE TABLE IF NOT EXISTS sentience_recommendations(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,app_id TEXT NOT NULL,field TEXT NOT NULL,threshold REAL NOT NULL,reason TEXT NOT NULL,status TEXT NOT NULL,rule_id TEXT,created_by INTEGER NOT NULL,created INTEGER NOT NULL)')
 c.execute('CREATE INDEX IF NOT EXISTS sentience_rec_workspace ON sentience_recommendations(workspace_id,created)')

def overview(c,uid,wid):
 prime.permission(c,uid,wid)
 apps=c.execute('SELECT id,name,schema_json,status FROM prime_apps WHERE workspace_id=? ORDER BY created DESC LIMIT 50',(wid,)).fetchall()
 result=[]
 for aid,name,schema,status in apps:
  fields=json.loads(schema); rows=c.execute('SELECT data_json FROM prime_records WHERE workspace_id=? AND app_id=? ORDER BY created DESC LIMIT 500',(wid,aid)).fetchall()
  data=[json.loads(r[0]) for r in rows]
  numbers={}
  for f in fields:
   if f['type']!='number':continue
   values=[]
   for rec in data:
    try:
     v=float(rec.get(f['name'],''))
     if math.isfinite(v):values.append(v)
    except (ValueError,TypeError):pass
   if values:numbers[f['name']]={'count':len(values),'min':min(values),'max':max(values),'average':round(sum(values)/len(values),2)}
  result.append({'id':aid,'name':name,'status':status,'record_count_sampled':len(data),'sample_limit':500,'numeric_fields':numbers})
 return result

def recommend(c,uid,wid,aid,field,threshold):
 if empire_v19.role(c,uid,wid) not in ('owner','editor'):raise ValueError('Editing permission required')
 row=prime.app(c,uid,wid,aid)
 if row[3]!='published':raise ValueError('Publish application first')
 if field not in {f['name'] for f in json.loads(row[2]) if f['type']=='number'}:raise ValueError('Select a numeric field')
 try:t=float(threshold)
 except (ValueError,TypeError):raise ValueError('Invalid threshold')
 if not math.isfinite(t) or abs(t)>1e9:raise ValueError('Invalid threshold')
 rid=secrets.token_hex(12)
 reason='Proposed review task when '+field+' is below '+str(t)+'. No action is taken until an owner approves the resulting workflow.'
 c.execute('INSERT INTO sentience_recommendations VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,wid,aid,field,t,reason,'proposed',None,uid,int(time.time())))
 return rid

def decide(c,uid,wid,rid,approve):
 if empire_v19.role(c,uid,wid)!='owner':raise ValueError('Only owners can review recommendations')
 r=c.execute('SELECT app_id,field,threshold,status FROM sentience_recommendations WHERE id=? AND workspace_id=?',(rid,wid)).fetchone()
 if not r or r[3]!='proposed':raise ValueError('Recommendation unavailable or already reviewed')
 rule_id=None
 if approve:rule_id=autonomy_v22.create(c,uid,wid,r[0],'Sentience review: '+r[1],r[1],str(r[2]))
 c.execute('UPDATE sentience_recommendations SET status=?,rule_id=? WHERE id=? AND workspace_id=?',('draft_created' if approve else 'rejected',rule_id,rid,wid))
 return rule_id

def render(c,uid,csrf,wid='',message=''):
 esc=lambda x:html.escape(str(x),quote=True)
 ws=c.execute('SELECT w.id,w.name,m.role FROM empire_workspaces w JOIN empire_members m ON w.id=m.workspace_id WHERE m.user_id=? ORDER BY w.created DESC',(uid,)).fetchall()
 if not wid and ws:wid=ws[0][0]
 if wid:prime.permission(c,uid,wid)
 h=['<section class="panel"><h1>◈ SENTIENCE V23 — Business Intelligence</h1><p>Evidence-based summaries from your workspace only. Numeric statistics are calculated in Python, not invented by an AI. Recommendations require owner review and separate Autonomy activation.</p><p>Workspace: '+''.join('<a style="margin-right:12px" href="/sentience?w='+esc(w)+'">'+esc(n)+'</a>' for w,n,_ in ws)+'</p></section>']
 if message:h.append('<section class="panel">'+esc(message)+'</section>')
 if not wid:return ''.join(h)
 role=prime.permission(c,uid,wid)
 for a in overview(c,uid,wid):
  h.append('<section class="panel"><h2>'+esc(a['name'])+'</h2><p>Status: '+esc(a['status'])+' · Records sampled: '+str(a['record_count_sampled'])+' (maximum 500 most recent)</p>')
  for field,stats in a['numeric_fields'].items():
   h.append('<p><strong>'+esc(field)+'</strong>: min '+esc(stats['min'])+' · max '+esc(stats['max'])+' · average '+esc(stats['average'])+' · valid values '+esc(stats['count'])+'</p>')
   if role in ('owner','editor') and a['status']=='published':
    h.append('<form method="post" action="/sentience"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="action" value="recommend"><input type="hidden" name="app" value="'+esc(a['id'])+'"><input type="hidden" name="field" value="'+esc(field)+'"><label>Propose review task when '+esc(field)+' falls below<input name="threshold" type="number" step="any" required></label><button>Propose workflow</button></form>')
  h.append('</section>')
 h.append('<section class="panel"><h2>Recommendations & decisions</h2>')
 for rid,reason,status,rule_id in c.execute('SELECT id,reason,status,rule_id FROM sentience_recommendations WHERE workspace_id=? ORDER BY created DESC LIMIT 100',(wid,)).fetchall():
  h.append('<div style="border-top:1px solid #655777;padding:12px"><p>'+esc(reason)+'</p><p>Status: '+esc(status)+'</p>')
  if rule_id:h.append('<p>Draft workflow created. <a href="/autonomy?w='+esc(wid)+'">Review and activate in Autonomy</a>.</p>')
  if role=='owner' and status=='proposed':
   for action,label in [('approve','Create draft workflow'),('reject','Reject')]:
    h.append('<form method="post" action="/sentience"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'"><input type="hidden" name="rec" value="'+esc(rid)+'"><input type="hidden" name="action" value="'+action+'"><button>'+label+'</button></form>')
  h.append('</div>')
 return ''.join(h)+'</section>'
