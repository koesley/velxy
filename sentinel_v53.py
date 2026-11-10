"""V53 Project Sentinel: read-only data-quality and decision-readiness checks."""
import html, json
from urllib.parse import urlencode
import titan_intelligence_v52 as titan
import singularity_v50 as singularity

RULES=(('baseline','Missing baseline','Record an initial measurement before evaluating outcomes.'),('followup','Missing follow-up','Record a follow-up measurement before claiming an outcome.'),('plan','Missing delivery plan','Create a delivery plan for approved work.'),('overdue','Overdue milestones','Review milestone due dates and dependencies.'),('blocked','Blocked milestones','Resolve prerequisite milestones first.'))

def report(c,uid,wid=''):
    t=titan.report(c,uid,wid)
    if not t['workspace_id']:
        return {'workspace_id':None,'checks':[],'summary':{'checked':0,'flagged':0},'limitations':['Create a workspace first.']}
    s=singularity.report(c,uid,t['workspace_id'])
    journeys=s.get('journeys',[])
    checks=[]
    def add(code,title,ids,action):
        ids=list(dict.fromkeys(ids))
        checks.append({'code':code,'title':title,'affected_count':len(ids),'sample_experiment_ids':ids[:25], 'status':'review' if ids else 'clear_in_sample','action':action,'requires_human_review':True})
    for code,title,action in RULES:
        ids=[]
        for j in journeys:
            eid=j.get('experiment_id')
            if eid is None:continue
            if code=='baseline' and j.get('baseline') is None:ids.append(eid)
            elif code=='followup' and j.get('stage') in ('measurement','complete') and j.get('followup') is None:ids.append(eid)
            elif code=='plan' and j.get('stage')=='delivery' and j.get('plan_count',0)==0:ids.append(eid)
            elif code=='overdue' and int(j.get('overdue_milestones') or 0)>0:ids.append(eid)
            elif code=='blocked' and int(j.get('blocked_milestones') or 0)>0:ids.append(eid)
        add(code,title,ids,action)
    flagged=sum(x['affected_count']>0 for x in checks)
    return {'workspace_id':t['workspace_id'],'workspace_name':t['workspace_name'],'role':t['role'],'checks':checks,'summary':{'checked':len(checks),'flagged':flagged,'sampled_experiments':len(journeys),'review_items':sum(x['affected_count'] for x in checks)},'limitations':list(s.get('limitations',[]))+['Only sampled experiments are checked; clear_in_sample does not mean no risk.','Counts across rules may overlap and are not unique experiment totals.','This is a deterministic audit, not a prediction or trained AI. No data is modified.']}

def render(c,uid,csrf,wid=''):
    r=report(c,uid,wid);e=lambda v:html.escape(str(v),quote=True)
    if not r['workspace_id']:return '<section class="panel"><h1>Sentinel V53</h1><p>Create a workspace first.</p></section>'
    q=e(urlencode({'w':r['workspace_id']}))
    out=['<section class="panel sentinel-hero"><p class="eyebrow">VELXTRIA V53 · PROJECT SENTINEL</p><h1>Evidence integrity command center</h1><p>Workspace: '+e(r['workspace_name'])+'</p><p>'+e(r['summary']['flagged'])+' of '+e(r['summary']['checked'])+' checks flagged for human review · '+e(r['summary']['sampled_experiments'])+' sampled experiments</p><a href="/sentinel-v53.json?'+q+'">Export evidence audit JSON</a></section><section class="panel"><h2>Quality checks</h2><div class="sentinel-grid">']
    for x in r['checks']:
        out.append('<article class="sentinel-check"><strong>'+e(x['title'])+'</strong><p>'+e(x['status'])+' · '+e(x['affected_count'])+' affected experiments</p><p>'+e(x['action'])+'</p><small>Sample experiment IDs: '+e(', '.join(map(str,x['sample_experiment_ids'])) or 'None')+'</small></article>')
    out.append('</div></section><section class="panel"><h2>Coverage and limitations</h2><ul>')
    out.extend('<li>'+e(x)+'</li>' for x in r['limitations'])
    out.append('</ul></section>')
    return ''.join(out)

CSS='''\n.sentinel-hero{background:linear-gradient(115deg,#221b42,#16384a);border:1px solid #6c7caa}.sentinel-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}.sentinel-check{background:#22243b;border:1px solid #5c6488;border-radius:12px;padding:16px}.sentinel-check small{overflow-wrap:anywhere}\n'''
