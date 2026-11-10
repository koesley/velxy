"""V51 Ascendancy: secure, read-only, guided customer workflow and portable action queue."""
import csv, html, io, json
from urllib.parse import urlencode
import infinity_engine_v42 as infinity
import singularity_v50 as singularity
import empire_v19

STAGES=(('discover','Discover','Review current business data','/infinity-engine'),('propose','Propose','Turn evidence into an experiment proposal','/evolution-engine'),('approve','Approve','Review proposed experiments','/autonomous-core'),('deliver','Deliver','Plan milestones and record effort','/hyperion'),('measure','Measure','Review outcomes and delivery performance','/omniscience'),('learn','Learn','Review historical patterns','/neural-network'))
STATUS_FILTERS=('all','high','medium','approval','delivery','measurement','complete')

def report(c,uid,wid='',status='all'):
    if status not in STATUS_FILTERS:raise ValueError('Unsupported filter')
    ws,wid=infinity.scope(c,uid,wid)
    if not wid:return {'workspace_id':None,'workspace_name':None,'role':None,'stages':[],'actions':[],'journeys':[],'summary':{},'filter':status,'limitations':['Create a workspace to begin']}
    source=singularity.report(c,uid,wid)
    name=next((w[1] for w in ws if w[0]==wid),'Workspace')
    role=empire_v19.role(c,uid,wid)
    actions=[]
    for item in source['priorities']:
        stage=('approve' if item['reason'].startswith('Workspace owner') else 'propose' if 'proposal' in item['reason'].lower() else 'deliver' if 'milestone' in item['reason'].lower() or 'delivery plan' in item['reason'].lower() else 'measure')
        if item['experiment_id']:
            match=next((j for j in source['journeys'] if j['experiment_id']==item['experiment_id']),None)
            if match and match['stage']=='approval':stage='approve'
            elif match and match['stage']=='measurement':stage='measure'
            elif match and match['stage']=='delivery':stage='deliver'
        route=next(s[3] for s in STAGES if s[0]==stage)
        actions.append({'title':item['title'],'priority':item['priority'],'reason':item['reason'],'stage':stage,'url':route+'?'+urlencode({'w':wid}),'overdue':item['overdue'],'experiment_id':item['experiment_id']})
    if role!='owner':
        for action in actions:
            if action['stage']=='approve':action['reason']='Owner approval required — contact your workspace owner'
    if status in ('high','medium'):actions=[a for a in actions if a['priority']==status]
    elif status in ('approval','delivery','measurement'):actions=[a for a in actions if a['stage']=={'approval':'approve','delivery':'deliver','measurement':'measure'}[status]]
    elif status=='complete':actions=[]
    stage_counts={s[0]:sum(a['stage']==s[0] for a in actions) for s in STAGES}
    stages=[{'key':key,'name':label,'description':description,'url':route+'?'+urlencode({'w':wid}),'open_actions':stage_counts[key]} for key,label,description,route in STAGES]
    return {'workspace_id':wid,'workspace_name':name,'role':role,'stages':stages,'actions':actions,'journeys':source['journeys'] if status in ('all','complete') else [j for j in source['journeys'] if (status=='approval' and j['stage']=='approval') or (status=='delivery' and j['stage']=='delivery') or (status=='measurement' and j['stage']=='measurement') or (status in ('high','medium') and j['priority']==status)],'summary':source['summary'],'filter':status,'limitations':source['limitations']+['Guided links do not execute work or approve experiments','Action queue reflects bounded underlying module reports']}

def csv_export(c,uid,wid='',status='all'):
    data=report(c,uid,wid,status)
    stream=io.StringIO(newline='')
    writer=csv.writer(stream)
    writer.writerow(('workspace','stage','priority','title','reason','overdue_milestones','experiment_id'))
    for a in data['actions']:
        # Spreadsheet formula injection protection on untrusted customer strings.
        def safe(v):
            s=str(v if v is not None else '')
            return "'"+s if s.lstrip().startswith(('=','+','-','@','\t','\r','\n')) else s
        writer.writerow((safe(data['workspace_name']),safe(a['stage']),safe(a['priority']),safe(a['title']),safe(a['reason']),a['overdue'],safe(a['experiment_id'])))
    return stream.getvalue().encode('utf-8-sig')

def render(c,uid,csrf,wid='',status='all'):
    r=report(c,uid,wid,status)
    e=lambda v:html.escape(str(v),quote=True)
    if not r['workspace_id']:return '<section class="panel"><h1>Ascendancy V51</h1><p>Create a workspace to begin your guided business journey.</p><a href="/empire">Create workspace</a></section>'
    wid=r['workspace_id'];base=urlencode({'w':wid})
    out=['<section class="panel asc-hero"><p class="eyebrow">VELXTRIA V51 · PROJECT ASCENDANCY</p><h1>One workspace. One clear path forward.</h1><p>Move from business evidence to proposals, owner decisions, delivery, and measurable outcomes without losing your place.</p><p><strong>Workspace:</strong> '+e(r['workspace_name'])+' <span class="asc-role">'+e(r['role'])+'</span></p><p><a href="/ascendancy-v51.json?'+e(base)+'">Download JSON</a> · <a href="/ascendancy-v51.csv?'+e(base)+'">Download action CSV</a></p></section>']
    out.append('<section class="panel"><h2>Your six-step business journey</h2><div class="asc-stages">')
    for i,s in enumerate(r['stages'],1):out.append('<a class="asc-stage" href="'+e(s['url'])+'"><span class="asc-number">'+str(i)+'</span><strong>'+e(s['name'])+'</strong><small>'+e(s['description'])+'</small><span class="asc-count">'+str(s['open_actions'])+' open actions</span></a>')
    out.append('</div></section>')
    out.append('<section class="panel"><h2>What needs attention?</h2><p>Suggested next steps based on existing experiment and milestone records. You remain in control of all changes.</p><nav class="asc-filters" aria-label="Filter next actions">')
    for key in STATUS_FILTERS:
        q=urlencode({'w':wid,'filter':key})
        out.append('<a '+('aria-current="page" ' if status==key else '')+'href="/ascendancy-v51?'+e(q)+'">'+e(key.title())+'</a>')
    out.append('</nav><div class="asc-actions">')
    for a in r['actions'][:100]:out.append('<article class="asc-action"><div><span class="asc-priority">'+e(a['priority'].upper())+'</span> <span>'+e(a['stage'].title())+'</span><h3>'+e(a['title'])+'</h3><p>'+e(a['reason'])+'</p></div><a href="'+e(a['url'])+'">Open tool →</a></article>')
    if not r['actions']:out.append('<p>No matching pending actions in the sampled data. Explore the six-step journey above to get started.</p>')
    out.append('</div></section><section class="panel"><h2>Experiment progress</h2><div class="asc-actions">')
    for j in r['journeys'][:100]:
        pct=round(100*j['completed_milestones']/j['milestones']) if j['milestones'] else 0
        out.append('<article class="asc-action"><div><h3>'+e(j['title'])+'</h3><p>'+e(j['stage'].title())+' · '+e(j['goal'])+'</p><progress max="100" value="'+str(pct)+'" aria-label="Milestone completion percentage"></progress><small>'+str(j['completed_milestones'])+' of '+str(j['milestones'])+' milestones complete · '+str(j['overdue_milestones'])+' overdue</small></div><a href="/singularity-v50?'+e(base)+'">Details →</a></article>')
    if not r['journeys']:out.append('<p>No experiments in this view. Start by defining a goal or exploring your business data.</p>')
    out.append('</div></section><section class="panel"><h2>Evidence and limitations</h2><ul>')
    out.extend('<li>'+e(x)+'</li>' for x in r['limitations'])
    out.append('</ul></section>')
    return ''.join(out)

CSS='''\n.asc-hero{background:linear-gradient(135deg,#22183d,#382059 70%,#182337);border:1px solid #7657a7}.asc-stages{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}.asc-stage{display:flex;flex-direction:column;gap:8px;text-decoration:none!important;background:#231b35;border:1px solid #66517e;border-radius:14px;padding:16px;color:#f4eaff!important}.asc-stage:hover,.asc-stage:focus-visible{border-color:#c49cff;background:#342447}.asc-stage small{color:#cfc4de}.asc-number{font-size:22px;color:#d3a9ff;font-weight:800}.asc-count{font-size:12px;color:#d3a9ff}.asc-role{padding:4px 10px;border-radius:12px;background:#46315f}.asc-filters{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}.asc-filters a{border:1px solid #6e5885;border-radius:12px;padding:7px 12px;color:#eadfff}.asc-filters a[aria-current=page]{background:#604487;color:white}.asc-actions{display:grid;gap:10px}.asc-action{display:flex;justify-content:space-between;align-items:center;gap:20px;padding:16px;border:1px solid #594b6d;border-radius:12px}.asc-action h3{margin:8px 0}.asc-action p{margin:5px 0}.asc-action progress{display:block;max-width:320px;width:100%;accent-color:#aa79ff}.asc-priority{font-size:12px;letter-spacing:.05em;color:#e4b7ff}.asc-action a{white-space:nowrap}@media(max-width:600px){.asc-action{display:block}.asc-action a{display:inline-block;margin-top:10px}}\n'''
