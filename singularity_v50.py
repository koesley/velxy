"""V50 Singularity: scoped, read-only cross-module workflow and evidence diagnostics."""
import html,json
from urllib.parse import urlencode
import infinity_engine_v42 as infinity
import evolution_engine_v46 as evolution
import autonomous_core_v43 as core
import hyperion_v47 as hyperion
import omniscience_v49 as omni

STAGES=('proposals','approval','delivery','measurement')
def report(c,uid,wid=''):
    _,wid=infinity.scope(c,uid,wid)
    if not wid:return {'workspace_id':None,'summary':{},'journeys':[],'priorities':[],'limitations':[]}
    proposals=evolution.report(c,uid,wid)['proposals']
    experiments=core.report(c,uid,wid)['experiments']
    delivery=omni.report(c,uid,wid)
    plans=delivery['plans']
    by_experiment={e['id']:e for e in experiments}
    plans_by_experiment={}
    for p in plans:plans_by_experiment.setdefault(p['experiment_id'],[]).append(p)
    linked={p['experiment_id'] for p in proposals if p['experiment_id']}
    journeys=[];priorities=[]
    for e in experiments:
        related=plans_by_experiment.get(e['id'],[])
        steps=[s for p in related for s in p['steps']]
        done=sum(s['status']=='done' for s in steps)
        outstanding=sum(s['status'] in ('todo','doing') for s in steps)
        overdue=sum(s['risk']=='overdue' for s in steps if s['status']!='done')
        blocked=sum(bool(s.get('depends_on')) and next((x['status'] for x in steps if x['id']==s['depends_on']),None)!='done' for s in steps if s['status'] in ('todo','doing'))
        if e['status']=='proposed':stage='approval';next_action='Workspace owner reviews the proposed experiment';priority='high'
        elif e['status']=='approved' and not related:stage='delivery';next_action='Create a delivery plan with milestones';priority='medium'
        elif e['status']=='approved' and outstanding:stage='delivery';next_action='Resolve outstanding milestones and capture evidence';priority='high' if overdue else 'medium'
        elif e['status']=='approved':stage='measurement';next_action='Record follow-up measurements and finalize the experiment';priority='medium'
        elif e['status']=='completed':stage='complete';next_action='Review descriptive outcome evidence';priority='info'
        else:stage='closed';next_action='No action required';priority='info'
        j={'experiment_id':e['id'],'title':e['title'],'goal':e['goal_title'],'experiment_status':e['status'],'source_proposal':e['id'] in linked,'stage':stage,'next_action':next_action,'priority':priority,'plan_count':len(related),'milestones':len(steps),'completed_milestones':done,'open_milestones':outstanding,'overdue_milestones':overdue,'blocked_milestones':blocked,'actual_hours':round(sum(s['actual_hours'] for s in steps),2),'baseline':e['baseline'],'followup':e['followup'],'delta':e['delta'],'direction_matched':e['direction_matched']}
        journeys.append(j)
        if stage not in ('complete','closed'):priorities.append({'experiment_id':e['id'],'title':e['title'],'priority':priority,'reason':next_action,'overdue':overdue})
    for p in proposals:
        if p['status']=='draft':priorities.append({'experiment_id':None,'title':p['title'],'priority':'medium','reason':'Review or dismiss generated proposal','overdue':0})
    rank={'high':0,'medium':1,'info':2}
    priorities.sort(key=lambda p:(rank[p['priority']],-p['overdue'],p['title']))
    return {'workspace_id':wid,'summary':{'draft_proposals':sum(p['status']=='draft' for p in proposals),'awaiting_owner_approval':sum(e['status']=='proposed' for e in experiments),'approved_experiments':sum(e['status']=='approved' for e in experiments),'completed_experiments':sum(e['status']=='completed' for e in experiments),'delivery_plans':len(plans),'open_milestones':sum(j['open_milestones'] for j in journeys),'overdue_milestones':sum(j['overdue_milestones'] for j in journeys),'logged_hours_in_report':delivery['summary']['logged_hours_in_report']},'journeys':journeys,'priorities':priorities[:100],'limitations':['Read-only cross-module snapshot; no automated execution','Experiments and plans are sampled by existing bounded module reports','No causal inference or guaranteed revenue impact','No background jobs, notifications, or independent security certification']}

def render(c,uid,csrf,wid=''):
    r=report(c,uid,wid);e=lambda x:html.escape(str(x),quote=True)
    if not r['workspace_id']:return '<section class="panel"><h1>Singularity V50</h1><p>Create a workspace to begin.</p><a href="/empire">Workspaces</a></section>'
    q=e(urlencode({'w':r['workspace_id']}))
    links=[('/infinity-engine','Analyze'),('/evolution-engine','Propose'),('/autonomous-core','Approve'),('/hyperion','Deliver'),('/omniscience','Measure'),('/neural-network','Learn')]
    out=['<section class="panel"><p class="eyebrow">VELXTRIA V50 · PROJECT SINGULARITY</p><h1>One connected business improvement journey</h1><p>Evidence → proposal → human approval → execution planning → measured outcome.</p><p><a href="/singularity-v50.json?'+q+'">Export full journey report</a></p><div class="grid">']
    for label,val in r['summary'].items():out.append('<article><h3>'+e(label.replace('_',' ').title())+'</h3><strong>'+e(val)+'</strong></article>')
    out.append('</div></section><section class="panel"><h2>Connected workflow</h2><div class="grid">')
    for href,label in links:out.append('<article><h3>'+e(label)+'</h3><a href="'+href+'?'+q+'">Open '+e(label)+' tool</a></article>')
    out.append('</div></section><section class="panel"><h2>Next actions</h2>')
    for p in r['priorities'][:25]:out.append('<article><strong>'+e(p['priority'].upper())+' · '+e(p['title'])+'</strong><p>'+e(p['reason'])+'</p></article>')
    if not r['priorities']:out.append('<p>No pending actions in the sampled records.</p>')
    out.append('</section><section class="panel"><h2>End-to-end experiment journeys</h2>')
    for j in r['journeys']:
        out.append('<article style="border-top:1px solid #655777;padding:12px 0"><h3>'+e(j['title'])+'</h3><p>'+e(j['goal'])+' · '+e(j['stage'].upper())+' · '+e(j['experiment_status'])+'</p><p>Milestones: '+e(j['completed_milestones'])+'/'+e(j['milestones'])+' complete · '+e(j['overdue_milestones'])+' overdue · '+e(j['actual_hours'])+' logged hours</p><p>'+e(j['next_action'])+'</p></article>')
    if not r['journeys']:out.append('<p>No experiments yet. Start with an analysis or proposal.</p>')
    out.append('</section><section class="panel"><h2>Evidence limitations</h2><ul>')
    out.extend('<li>'+e(v)+'</li>' for v in r['limitations'])
    out.append('</ul></section>');return ''.join(out)
