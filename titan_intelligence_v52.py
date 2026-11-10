"""V52 Titan Intelligence: deterministic, auditable business analyst; no LLM or external calls."""
import html, json
from urllib.parse import urlencode
import ascendancy_v51 as asc
import singularity_v50 as singularity

SEVERITIES=('critical','attention','opportunity','information')

def report(c,uid,wid=''):
    base=asc.report(c,uid,wid)
    if not base['workspace_id']:
        return {'workspace_id':None,'findings':[],'briefing':[],'summary':{},'limitations':['Create a workspace to begin']}
    source=singularity.report(c,uid,base['workspace_id'])
    s=source['summary']; findings=[]
    def add(code,severity,title,observation,action,evidence,stage):
        findings.append({'code':code,'severity':severity,'title':title,'observation':observation,'recommended_action':action,'evidence':evidence,'stage':stage,'requires_human_review':True})
    overdue=int(s.get('overdue_milestones',0))
    if overdue:
        add('overdue','critical','Overdue delivery milestones',f'{overdue} overdue milestone(s) appear in the sampled delivery records.','Review due dates and unblock the affected milestones.',{'metric':'overdue_milestones','value':overdue,'source':'singularity_v50.summary'},'deliver')
    approvals=int(s.get('awaiting_owner_approval',0))
    if approvals:
        add('approvals','attention','Experiments awaiting owner approval',f'{approvals} proposed experiment(s) await an owner decision.','Review the proposal evidence and approve or reject individually.',{'metric':'awaiting_owner_approval','value':approvals,'source':'singularity_v50.summary'},'approve')
    drafts=int(s.get('draft_proposals',0))
    if drafts:
        add('drafts','opportunity','Unreviewed strategy drafts',f'{drafts} strategy draft(s) remain unsubmitted.','Review their hypotheses and supporting evidence before submitting.',{'metric':'draft_proposals','value':drafts,'source':'singularity_v50.summary'},'propose')
    missing=[j for j in source['journeys'] if j['stage']=='delivery' and j['plan_count']==0]
    if missing:
        add('no_plans','attention','Approved work without delivery plans',f'{len(missing)} approved experiment(s) have no delivery plan in this report.','Create milestones and assign estimated effort before starting.',{'metric':'experiment_ids','value':[j['experiment_id'] for j in missing[:25]],'source':'singularity_v50.journeys'},'deliver')
    blocked=sum(int(j.get('blocked_milestones',0)) for j in source['journeys'])
    if blocked:
        add('blocked','attention','Dependency-blocked work',f'{blocked} milestone(s) are blocked by dependencies in sampled plans.','Complete prerequisites before scheduling dependent work.',{'metric':'blocked_milestones','value':blocked,'source':'singularity_v50.journeys'},'deliver')
    measurement=[j for j in source['journeys'] if j['stage']=='measurement']
    if measurement:
        add('measurement','attention','Outcome evidence still needed',f'{len(measurement)} experiment(s) are ready for follow-up measurement.','Record follow-up measurements and review outcomes before finalizing.',{'metric':'experiment_ids','value':[j['experiment_id'] for j in measurement[:25]],'source':'singularity_v50.journeys'},'measure')
    unmeasured=[j for j in source['journeys'] if j['stage']=='complete' and (j['baseline'] is None or j['followup'] is None)]
    if unmeasured:
        add('missing_evidence','attention','Completed experiments with incomplete comparisons',f'{len(unmeasured)} completed experiment(s) lack baseline or follow-up values in this report.','Check measurement coverage before drawing outcome conclusions.',{'metric':'experiment_ids','value':[j['experiment_id'] for j in unmeasured[:25]],'source':'singularity_v50.journeys'},'measure')
    if not findings:
        add('review','information','No flagged conditions in sampled records','The defined rules did not detect an exception in the available bounded reports.','Review the underlying records and data coverage before assuming everything is healthy.',{'metric':'sampled_experiments','value':len(source['journeys']),'source':'singularity_v50.journeys'},'discover')
    order={v:i for i,v in enumerate(SEVERITIES)}
    findings.sort(key=lambda f:(order[f['severity']],f['code']))
    briefing=[f['observation'] for f in findings[:5]]
    return {'workspace_id':base['workspace_id'],'workspace_name':base['workspace_name'],'role':base['role'],'summary':s,'findings':findings,'briefing':briefing,'evidence_count':len(source['journeys']),'limitations':source['limitations']+['Rule-based descriptive analysis, not a trained AI model or causal inference','No autonomous actions; all recommendations require human judgment','Bounded snapshots may omit records; no finding is proof of absence of risk']}

def render(c,uid,csrf,wid=''):
    r=report(c,uid,wid);e=lambda x:html.escape(str(x),quote=True)
    if not r['workspace_id']:return '<section class="panel"><h1>Titan Intelligence V52</h1><p>Create a workspace to begin.</p><a href="/empire">Workspaces</a></section>'
    q=e(urlencode({'w':r['workspace_id']}))
    out=['<section class="panel titan-hero"><p class="eyebrow">VELXTRIA V52 · PROJECT TITAN INTELLIGENCE</p><h1>Your evidence-first business analyst</h1><p>Explainable findings and suggested next steps. Every recommendation traces to a named internal metric.</p><p>Workspace: <strong>'+e(r['workspace_name'])+'</strong> · '+e(r['role'])+'</p><a href="/titan-intelligence.json?'+q+'">Download audit-ready JSON</a></section><section class="panel"><h2>Executive briefing</h2><ul>']
    out.extend('<li>'+e(x)+'</li>' for x in r['briefing'])
    out.append('</ul></section><section class="panel"><h2>Findings and recommended actions</h2><div class="titan-findings">')
    for f in r['findings']:
        href={'approve':'/autonomous-core','propose':'/evolution-engine','deliver':'/hyperion','measure':'/omniscience','discover':'/infinity-engine'}[f['stage']]
        out.append('<article class="titan-finding"><span class="titan-severity">'+e(f['severity'].upper())+'</span><h3>'+e(f['title'])+'</h3><p>'+e(f['observation'])+'</p><p><strong>Suggested review:</strong> '+e(f['recommended_action'])+'</p><small>Evidence: '+e(f['evidence']['source'])+' · '+e(f['evidence']['metric'])+' = '+e(json.dumps(f['evidence']['value']))+'</small><p><a href="'+href+'?'+q+'">Review in workspace →</a></p></article>')
    out.append('</div></section><section class="panel"><h2>What this analysis cannot establish</h2><ul>')
    out.extend('<li>'+e(x)+'</li>' for x in r['limitations'])
    out.append('</ul></section>')
    return ''.join(out)

CSS='''\n.titan-hero{background:linear-gradient(120deg,#241c43,#263553);border:1px solid #8c71ba}.titan-findings{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:14px}.titan-finding{border:1px solid #67527f;padding:16px;border-radius:14px;background:#241c33}.titan-finding small{overflow-wrap:anywhere;color:#c9b6df}.titan-severity{color:#e0b4ff;font-size:12px;letter-spacing:.07em}\n'''
