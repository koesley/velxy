"""V45 Neural Network: conservative, explainable, tenant-scoped experiment analytics.
No machine-learning model is trained, no automated actions, no causal claims.
"""
import html, json, math, statistics
from urllib.parse import urlencode
import infinity_engine_v42, autonomous_core_v43 as core

MAX_EXPERIMENTS=1000

def _rows(c,wid):
 return c.execute("""SELECT e.id,e.title,e.goal_id,e.status,e.success_direction,e.baseline,e.followup,e.baseline_sample,e.followup_sample,e.created,e.completed,g.title FROM core_experiments_v43 e JOIN nexus_goals g ON g.id=e.goal_id AND g.workspace_id=e.workspace_id WHERE e.workspace_id=? ORDER BY e.created DESC,e.id DESC LIMIT ?""",(wid,MAX_EXPERIMENTS)).fetchall()

def _classify(r):
 eid,title,gid,status,direction,baseline,followup,bs,fs,created,completed,goal=r
 result={'id':eid,'title':title,'goal_id':gid,'goal_title':goal,'status':status,'direction':direction,'baseline':baseline,'followup':followup,'baseline_sample':bs,'followup_sample':fs,'created':created,'completed':completed,'delta':None,'relative_change_percent':None,'outcome':'pending','evidence_quality':'not-evaluated'}
 if status!='completed' or followup is None:return result
 if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in (baseline,followup)):
  result.update(outcome='invalid-data',evidence_quality='insufficient');return result
 delta=followup-baseline
 result['delta']=round(delta,6)
 if baseline!=0:result['relative_change_percent']=round(100*delta/abs(baseline),3)
 result['outcome']='improved' if (delta>0 if direction=='increase' else delta<0) else ('unchanged' if delta==0 else 'worsened')
 result['evidence_quality']='limited' if (bs is None or fs is None or bs<5 or fs<5) else 'observational'
 return result

def report(c,uid,wid=''):
 ws,wid=infinity_engine_v42.scope(c,uid,wid)
 if not wid:return {'workspace_id':None,'summary':{},'experiments':[],'goal_patterns':[],'opportunities':[],'limitations':['Create a workspace first']}
 experiments=[_classify(r) for r in _rows(c,wid)]
 completed=[e for e in experiments if e['status']=='completed' and e['outcome'] in ('improved','worsened','unchanged')]
 improved=[e for e in completed if e['outcome']=='improved']
 by_goal={}
 for e in experiments:
  g=by_goal.setdefault(e['goal_id'],{'goal_id':e['goal_id'],'goal_title':e['goal_title'],'total':0,'completed':0,'improved':0,'worsened':0,'unchanged':0,'limited':0,'deltas':[]})
  g['total']+=1
  if e in completed:
   g['completed']+=1;g[e['outcome']]+=1;g['limited']+=int(e['evidence_quality']=='limited');g['deltas'].append(e['delta'])
 patterns=[]
 for g in by_goal.values():
  ds=g.pop('deltas')
  g['median_signed_delta']=round(statistics.median(ds),6) if ds else None
  g['improvement_fraction']=round(g['improved']/g['completed'],3) if g['completed'] else None
  g['interpretation']='Insufficient repeated outcomes' if g['completed']<3 else 'Descriptive history only; not a forecast or causal estimate'
  patterns.append(g)
 patterns.sort(key=lambda g:(-g['completed'],-g['improved'],g['goal_title']))
 opportunities=[]
 for g in patterns:
  if g['completed']>=3 and g['worsened']>=2:
   opportunities.append({'priority':'review','goal_id':g['goal_id'],'title':'Review repeated unfavorable outcomes: '+g['goal_title'],'evidence':str(g['worsened'])+' of '+str(g['completed'])+' completed experiments moved against their stated direction.','next_step':'Audit measurement definitions and interventions before proposing another experiment.'})
  elif g['completed']>=3 and g['improved']>=2:
   opportunities.append({'priority':'investigate','goal_id':g['goal_id'],'title':'Investigate recurring favorable outcomes: '+g['goal_title'],'evidence':str(g['improved'])+' of '+str(g['completed'])+' completed experiments moved in the stated direction.','next_step':'Review comparable conditions and potential confounders; do not assume replication.'})
  elif g['total']>0 and g['completed']==0:
   opportunities.append({'priority':'data-needed','goal_id':g['goal_id'],'title':'Complete measurements: '+g['goal_title'],'evidence':str(g['total'])+' experiments and no completed measurement pairs.','next_step':'Close approved tasks and record a valid follow-up.'})
 opportunities.sort(key=lambda o:({'review':0,'data-needed':1,'investigate':2}[o['priority']],o['title']))
 return {'workspace_id':wid,'summary':{'experiments':len(experiments),'completed':len(completed),'improved':len(improved),'worsened':sum(e['outcome']=='worsened' for e in completed),'unchanged':sum(e['outcome']=='unchanged' for e in completed),'limited_evidence':sum(e['evidence_quality']=='limited' for e in completed),'coverage_limit':len(experiments)==MAX_EXPERIMENTS},'experiments':experiments,'goal_patterns':patterns,'opportunities':opportunities,'limitations':['Observational before/after changes do not establish causation or predict profit','Different metrics have different units: signed deltas must not be aggregated across goals','Low sample counts are marked limited; no statistical significance is claimed','Only the latest 1000 experiments in the selected workspace are analyzed','No AI model is trained, and no external or customer-record actions are executed']}

def render(c,uid,wid=''):
 r=report(c,uid,wid);esc=lambda x:html.escape(str(x),quote=True)
 if not r['workspace_id']:return '<section class="panel"><h1>Neural Network V45</h1><p>Create a workspace to begin.</p></section>'
 q=urlencode({'w':r['workspace_id']});s=r['summary']
 out=['<section class="panel"><h1>✦ NEURAL NETWORK V45</h1><p>Explainable experiment evidence, recurring patterns, and prioritized next reviews. No autonomous execution or profit guarantees.</p><p><a href="/neural-network.json?'+esc(q)+'">Export complete evidence (JSON)</a> · <a href="/synapse?'+esc(q)+'">Synapse tasks</a> · <a href="/autonomous-core?'+esc(q)+'">Experiments</a></p></section>']
 out.append('<section class="panel"><h2>Outcome overview</h2><p>'+ ' · '.join(esc(k.replace('_',' ').title())+': <strong>'+str(v)+'</strong>' for k,v in s.items())+'</p></section>')
 out.append('<section class="panel"><h2>Prioritized reviews</h2>')
 for o in r['opportunities'][:30]:out.append('<article style="padding:12px 0;border-top:1px solid #655777"><h3>'+esc(o['title'])+'</h3><p>'+esc(o['evidence'])+'</p><p>Next step: '+esc(o['next_step'])+'</p></article>')
 if not r['opportunities']:out.append('<p>No pattern meets the current evidence thresholds.</p>')
 out.append('</section><section class="panel"><h2>Goal-by-goal patterns</h2><div class="scroll"><table><thead><tr><th>Goal</th><th>Completed</th><th>Improved</th><th>Worsened</th><th>Median delta</th><th>Evidence</th></tr></thead><tbody>')
 for g in r['goal_patterns']:out.append('<tr><td>'+esc(g['goal_title'])+'</td><td>'+str(g['completed'])+'</td><td>'+str(g['improved'])+'</td><td>'+str(g['worsened'])+'</td><td>'+esc(g['median_signed_delta'])+'</td><td>'+esc(g['interpretation'])+'</td></tr>')
 out.append('</tbody></table></div></section><section class="panel"><h2>Experiment evidence</h2><div class="scroll"><table><thead><tr><th>Experiment</th><th>Status</th><th>Outcome</th><th>Delta</th><th>Quality</th></tr></thead><tbody>')
 for e in r['experiments'][:100]:out.append('<tr><td>'+esc(e['title'])+'</td><td>'+esc(e['status'])+'</td><td>'+esc(e['outcome'])+'</td><td>'+esc(e['delta'])+'</td><td>'+esc(e['evidence_quality'])+'</td></tr>')
 out.append('</tbody></table></div></section><section class="panel"><h2>Interpretation limits</h2><ul>')
 for note in r['limitations']:out.append('<li>'+esc(note)+'</li>')
 out.append('</ul></section>');return ''.join(out)
