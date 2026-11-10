"""V55 Omega: scoped, read-only knowledge graph, question router, strategy review and scenario lab.
No LLM, external data, predictive claims, or autonomous changes.
"""
import html
from urllib.parse import urlencode
import aegis_v54 as aegis
import titan_intelligence_v52 as titan
import singularity_v50 as singularity

QUESTIONS={
 'overview':('What needs attention?','Show prioritized evidence-backed business findings.'),
 'delivery':('Why is delivery behind?','Review overdue milestones, blocked dependencies and missing delivery plans.'),
 'evidence':('Can I trust the outcomes?','Review missing baselines, follow-ups and experiment dossiers.'),
 'approvals':('What needs approval?','Review proposed experiments and unreviewed strategy drafts.'),
 'strategy':('What should we do next?','Compare reviewable actions, counterarguments and assumptions.'),
}
STAGE_LINKS={'approve':'/autonomous-core','propose':'/evolution-engine','deliver':'/hyperion','measure':'/omniscience','discover':'/infinity-engine'}

def graph(journeys):
    """Explicit experiment -> goal / delivery / measurement graph; no inferred causal edges."""
    nodes=[];edges=[]
    for j in journeys:
        eid=str(j['experiment_id']); x='experiment:'+eid; g='goal:'+str(j.get('goal',''))
        nodes.append({'id':x,'kind':'experiment','label':j.get('title',''),'stage':j.get('stage','')})
        nodes.append({'id':g,'kind':'goal','label':j.get('goal','')})
        edges.append({'from':x,'to':g,'relation':'targets_goal'})
        if j.get('plan_count',0):
            p='delivery:'+eid
            nodes.append({'id':p,'kind':'delivery_summary','label':str(j['plan_count'])+' plan(s)'})
            edges.append({'from':x,'to':p,'relation':'has_delivery_summary'})
        if j.get('baseline') is not None or j.get('followup') is not None:
            m='measurement:'+eid
            nodes.append({'id':m,'kind':'measurement_summary','label':'Recorded measurements'})
            edges.append({'from':x,'to':m,'relation':'has_measurement_summary'})
    return {'nodes':list({n['id']:n for n in nodes}.values()),'edges':edges,'limitations':['Goal names are summary identifiers, not globally unique goal IDs.','Graph contains sampled relationships, not a complete database export.']}

def scenarios(summary,capacity=20):
    """Illustrative workload scenarios, not completion predictions."""
    try:capacity=float(capacity)
    except (ValueError,TypeError):raise ValueError('Capacity must be a number')
    if not (0<capacity<=1000):raise ValueError('Capacity must be between 0 and 1000 hours per week')
    open_count=max(0,int(summary.get('open_milestones',0)))
    # Without effort estimates, do not invent duration. Expose planning capacity only.
    return {'weekly_capacity_hours':capacity,'open_milestones':open_count,'scenarios':[{'name':name,'capacity_hours_per_week':round(capacity*factor,2),'assumption':assumption,'estimated_completion_weeks':None} for name,factor,assumption in [('constrained',0.7,'30% capacity reserved for interruptions'),('baseline',1.0,'Full stated weekly capacity'),('expanded',1.25,'25% additional hypothetical capacity')]],'limitations':['No completion dates: milestone-level remaining effort is not available in this report.','Capacity changes are hypothetical and do not establish available staffing.']}

def report(c,uid,wid='',question='overview',capacity=20):
    if question not in QUESTIONS:raise ValueError('Unknown question')
    a=aegis.report(c,uid,wid)
    if not a['workspace_id']:
        return {'workspace_id':None,'question':question,'findings':[],'strategies':[],'limitations':['Create a workspace first.']}
    w=a['workspace_id'];t=titan.report(c,uid,w);s=singularity.report(c,uid,w)
    relevant={'overview':None,'delivery':{'overdue','no_plans','blocked'},'evidence':{'missing_evidence','measurement'},'approvals':{'approvals','drafts'},'strategy':None}[question]
    findings=[f for f in t['findings'] if relevant is None or f['code'] in relevant]
    dossier_issues=[{'experiment_id':d['experiment_id'],'title':d['title'],'code':i['code'],'severity':i['severity'],'action':i['action']} for d in a['dossiers'] for i in d['issues']]
    if question=='evidence':
        findings=findings+[{'code':'dossier:'+i['code'],'severity':i['severity'],'title':i['title'],'observation':'Evidence dossier flagged '+i['code'],'recommended_action':i['action'],'evidence':{'source':'aegis_v54.dossiers','metric':'experiment_id','value':i['experiment_id']},'stage':'measure','requires_human_review':True} for i in dossier_issues[:30]]
    strategies=[]
    for f in findings[:12]:
        strategies.append({'finding_code':f['code'],'proposed_action':f['recommended_action'],'counterargument':'The sampled records may omit context; the issue may not be the primary bottleneck.','validation':'Verify source records, costs, dependencies and an appropriate success metric before approving.','source':f['evidence'],'requires_human_approval':True,'review_link':STAGE_LINKS.get(f['stage'],'/singularity-v50')})
    return {'workspace_id':w,'workspace_name':a['workspace_name'],'role':a['role'],'question':question,'question_label':QUESTIONS[question][0],'summary':s['summary'],'findings':findings,'strategies':strategies,'knowledge_graph':graph(s['journeys']),'scenario_lab':scenarios(s['summary'],capacity),'dossier_issues':dossier_issues[:100],'limitations':list(dict.fromkeys(a['limitations']+t['limitations']+['No generative AI model, causal proof, financial projections or autonomous execution.','Answers are deterministic, rule-based, and based on bounded workspace reports.']))}

def render(c,uid,csrf,wid='',question='overview',capacity=20):
    r=report(c,uid,wid,question,capacity);e=lambda v:html.escape(str(v),quote=True)
    if not r['workspace_id']:return '<section class="panel"><h1>Omega V55</h1><p>Create a workspace first.</p></section>'
    w=r['workspace_id'];q=e(urlencode({'w':w,'question':question,'capacity':capacity}))
    out=['<section class="panel omega-hero"><p class="eyebrow">VELXTRIA V55 · PROJECT OMEGA INTELLIGENCE</p><h1>Omega Business Intelligence</h1><p>Traceable answers, strategy counterarguments and transparent scenarios.</p><p>Workspace: '+e(r['workspace_name'])+'</p><a href="/omega-v55.json?'+q+'">Export full evidence report (JSON)</a></section>','<section class="panel"><h2>Ask Omega</h2><div class="omega-grid">']
    for key,(label,desc) in QUESTIONS.items():
        link='/omega-v55?'+e(urlencode({'w':w,'question':key,'capacity':capacity}))
        out.append('<article class="omega-card"><h3><a href="'+link+'">'+e(label)+'</a></h3><p>'+e(desc)+'</p></article>')
    out.append('</div><p>Selected: <strong>'+e(r['question_label'])+'</strong></p></section><section class="panel"><h2>Evidence-linked findings</h2>')
    for f in r['findings'][:30]:
        out.append('<article class="omega-card"><strong>'+e(f['severity'].upper())+' · '+e(f['title'])+'</strong><p>'+e(f['observation'])+'</p><p>Review: '+e(f['recommended_action'])+'</p><small>Source: '+e(f['evidence']['source'])+' · '+e(f['evidence']['metric'])+'</small></article>')
    if not r['findings']:out.append('<p>No matching findings in sampled data. This is not proof of no problems.</p>')
    out.append('</section><section class="panel"><h2>Strategy review and counterarguments</h2>')
    for s in r['strategies']:
        out.append('<article class="omega-card"><h3>'+e(s['proposed_action'])+'</h3><p><strong>Challenge:</strong> '+e(s['counterargument'])+'</p><p><strong>Validate:</strong> '+e(s['validation'])+'</p><a href="'+e(s['review_link'])+'?'+e(urlencode({'w':w}))+'">Review in existing workflow</a></article>')
    out.append('</section><section class="panel"><h2>Capacity scenario laboratory</h2><p>Illustrative capacity only; no fabricated completion forecasts.</p><div class="omega-grid">')
    for s in r['scenario_lab']['scenarios']:
        out.append('<article class="omega-card"><h3>'+e(s['name'].title())+'</h3><strong>'+e(s['capacity_hours_per_week'])+' hours/week</strong><p>'+e(s['assumption'])+'</p></article>')
    out.append('</div><p>Open milestones: '+e(r['scenario_lab']['open_milestones'])+' · Graph nodes: '+e(len(r['knowledge_graph']['nodes']))+' · Graph edges: '+e(len(r['knowledge_graph']['edges']))+'</p></section><section class="panel"><h2>Limitations and verification</h2><ul>')
    out.extend('<li>'+e(v)+'</li>' for v in r['limitations']+r['scenario_lab']['limitations']+r['knowledge_graph']['limitations'])
    return ''.join(out)+'</ul></section>'

CSS='''\n.omega-hero{background:linear-gradient(120deg,#241244,#123d53);border:1px solid #a17ac9}.omega-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}.omega-card{border:1px solid #685888;background:#242139;border-radius:12px;padding:14px;margin:10px 0;overflow-wrap:anywhere}.omega-card small{color:#c7b6e6}\n'''
