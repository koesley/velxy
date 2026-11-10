"""V54 Aegis: explainable experiment-level evidence dossiers; read-only and scoped."""
import csv, html, io, json
from urllib.parse import urlencode
import singularity_v50 as singularity
import titan_intelligence_v52 as titan
import sentinel_v53 as sentinel

SEVERITY={'critical':0,'attention':1,'review':2,'ready_for_review':3}

def assess(j):
    """Conservative checks: missing evidence is never interpreted as success."""
    issues=[]
    def flag(code, severity, reason, action):
        issues.append({'code':code,'severity':severity,'reason':reason,'action':action})
    stage=j.get('stage')
    if j.get('baseline') is None:
        flag('baseline_missing','attention','No baseline measurement in the sampled experiment','Record or verify the starting measurement')
    if stage in ('measurement','complete') and j.get('followup') is None:
        flag('followup_missing','attention','No follow-up measurement in the sampled experiment','Record or verify the follow-up measurement')
    if stage=='delivery' and not j.get('plan_count'):
        flag('plan_missing','attention','Approved work has no delivery plan in this snapshot','Create a delivery plan')
    if int(j.get('overdue_milestones') or 0)>0:
        flag('overdue','critical','At least one milestone is overdue','Review milestone due dates')
    if int(j.get('blocked_milestones') or 0)>0:
        flag('blocked','attention','Dependencies are blocking milestones','Resolve prerequisite milestones')
    if stage=='complete' and j.get('direction_matched') is None:
        flag('outcome_unverified','review','The desired outcome is not verified in this snapshot','Review measurement quality and experiment direction')
    issues.sort(key=lambda x:(SEVERITY[x['severity']],x['code']))
    return {'experiment_id':j['experiment_id'],'title':j.get('title',''),'goal':j.get('goal',''),'stage':stage,'status':j.get('experiment_status'),'issues':issues,'readiness':'review_required' if issues else 'ready_for_review','issue_count':len(issues),'evidence':{'baseline':j.get('baseline'),'followup':j.get('followup'),'delta':j.get('delta'),'direction_matched':j.get('direction_matched'),'plans':j.get('plan_count',0),'milestones':j.get('milestones',0),'completed_milestones':j.get('completed_milestones',0),'overdue_milestones':j.get('overdue_milestones',0),'blocked_milestones':j.get('blocked_milestones',0),'actual_hours':j.get('actual_hours',0)},'next_action':j.get('next_action','Review underlying records')}

def report(c,uid,wid=''):
    # Sentinel delegates to Titan and Singularity, both of which enforce workspace authorization.
    audit=sentinel.report(c,uid,wid)
    if not audit['workspace_id']:
        return {'workspace_id':None,'dossiers':[],'summary':{},'limitations':['Create a workspace first.']}
    source=singularity.report(c,uid,audit['workspace_id'])
    dossiers=[assess(j) for j in source['journeys']]
    dossiers.sort(key=lambda x:(0 if any(i['severity']=='critical' for i in x['issues']) else 1, -x['issue_count'],str(x['title']),x['experiment_id']))
    return {'workspace_id':audit['workspace_id'],'workspace_name':audit['workspace_name'],'role':audit['role'],'summary':{'sampled_experiments':len(dossiers),'requiring_review':sum(bool(d['issues']) for d in dossiers),'critical_experiments':sum(any(i['severity']=='critical' for i in d['issues']) for d in dossiers),'issue_occurrences':sum(d['issue_count'] for d in dossiers),'sentinel_flagged_rules':audit['summary']['flagged']},'dossiers':dossiers,'limitations':list(source.get('limitations',[]))+['All findings are based on bounded samples; missing records can change the result.','Ready for review means no defined rule flagged the sampled evidence, not certified success.','No customer data is modified. Human approval is required for actions.']}

def csv_export(r):
    f=io.StringIO(newline='');w=csv.writer(f)
    w.writerow(['experiment_id','title','goal','stage','readiness','issue_count','issue_codes','baseline','followup','overdue_milestones','blocked_milestones','actual_hours'])
    def safe(v):
        s='' if v is None else str(v)
        return "'"+s if s.lstrip().startswith(('=','+','-','@','\t','\r')) else s
    for d in r['dossiers']:
        ev=d['evidence'];w.writerow([safe(d['experiment_id']),safe(d['title']),safe(d['goal']),safe(d['stage']),safe(d['readiness']),d['issue_count'],safe('|'.join(i['code'] for i in d['issues'])),safe(ev['baseline']),safe(ev['followup']),ev['overdue_milestones'],ev['blocked_milestones'],safe(ev['actual_hours'])])
    return '\ufeff'+f.getvalue()

def render(c,uid,csrf,wid=''):
    r=report(c,uid,wid);e=lambda v:html.escape(str(v),quote=True)
    if not r['workspace_id']:return '<section class="panel"><h1>Aegis V54</h1><p>Create a workspace first.</p></section>'
    q=e(urlencode({'w':r['workspace_id']}))
    out=['<section class="panel aegis-hero"><p class="eyebrow">VELXTRIA V54 · PROJECT AEGIS</p><h1>Experiment evidence dossiers</h1><p>Workspace: '+e(r['workspace_name'])+'</p><p>Review gaps before making outcome claims. No automatic actions.</p><p><a href="/aegis-v54.json?'+q+'">Export JSON</a> · <a href="/aegis-v54.csv?'+q+'">Export CSV</a></p></section><section class="panel"><h2>Coverage summary</h2><div class="aegis-grid">']
    for k,v in r['summary'].items():out.append('<article class="aegis-card"><strong>'+e(v)+'</strong><p>'+e(k.replace('_',' ').title())+'</p></article>')
    out.append('</div></section><section class="panel"><h2>Evidence dossiers</h2>')
    for d in r['dossiers']:
        out.append('<article class="aegis-dossier"><h3>'+e(d['title'])+'</h3><p>'+e(d['stage'])+' · '+e(d['readiness'])+' · '+e(d['issue_count'])+' issue(s)</p><p>Goal: '+e(d['goal'])+'</p><ul>')
        for i in d['issues']:out.append('<li><strong>'+e(i['severity'])+': '+e(i['code'])+'</strong> — '+e(i['reason'])+'. '+e(i['action'])+'.</li>')
        out.append('</ul><p>Baseline: '+e(d['evidence']['baseline'])+' · Follow-up: '+e(d['evidence']['followup'])+' · Logged hours: '+e(d['evidence']['actual_hours'])+'</p><p>Next: '+e(d['next_action'])+'</p></article>')
    if not r['dossiers']:out.append('<p>No experiments in the sampled records. This is not proof of complete coverage.</p>')
    out.append('</section><section class="panel"><h2>Limitations</h2><ul>')
    out.extend('<li>'+e(x)+'</li>' for x in r['limitations'])
    return ''.join(out)+'</ul></section>'

CSS='''\n.aegis-hero{background:linear-gradient(115deg,#241e45,#15424a);border:1px solid #7771b5}.aegis-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}.aegis-card,.aegis-dossier{background:#24243c;border:1px solid #66658c;border-radius:12px;padding:14px}.aegis-dossier{margin:12px 0;overflow-wrap:anywhere}\n'''
