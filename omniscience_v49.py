"""Omniscience V49: scoped, auditable actual effort and descriptive delivery intelligence.
No automated execution, financial advice, or guaranteed completion forecasting.
"""
import datetime
import html
import json
import math
import secrets
import statistics
import time
from urllib.parse import urlencode

import autonomous_core_v43 as core
import quantum_command_v48 as quantum


def setup(c):
    c.execute('''CREATE TABLE IF NOT EXISTS omniscience_effort_v49(
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, step_id TEXT NOT NULL,
        actor_id INTEGER NOT NULL, hours REAL NOT NULL CHECK(hours>0 AND hours<=24),
        work_date TEXT NOT NULL, note TEXT NOT NULL, created INTEGER NOT NULL)''')
    c.execute('CREATE INDEX IF NOT EXISTS omniscience_scope_v49 ON omniscience_effort_v49(workspace_id,step_id,work_date)')


def _valid_hours(value):
    try:
        n = float(value)
        if not math.isfinite(n) or not 0 < n <= 24:
            raise ValueError()
        return round(n, 2)
    except (TypeError, ValueError):
        raise ValueError('Work entry must be greater than zero and at most 24 hours')


def log_effort(c, uid, wid, step_id, hours, work_date, note):
    core._role(c, uid, wid, write=True)
    row = c.execute('''SELECT p.status,s.status FROM hyperion_steps_v47 s
        JOIN hyperion_plans_v47 p ON p.id=s.plan_id AND p.workspace_id=s.workspace_id
        WHERE s.workspace_id=? AND s.id=?''', (wid, step_id)).fetchone()
    if not row or row[0] != 'active' or row[1] == 'cancelled':
        raise ValueError('Only milestones in active plans can receive work logs')
    n = _valid_hours(hours)
    try:
        day = datetime.date.fromisoformat(str(work_date))
        if not datetime.date(2020,1,1) <= day <= datetime.date.today():
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError('Work date must be a valid past or current YYYY-MM-DD date')
    note = core._clean(note, 'Work evidence', 10, 1000)
    entry_id = secrets.token_hex(12)
    c.execute('INSERT INTO omniscience_effort_v49 VALUES(?,?,?,?,?,?,?,?)',
              (entry_id,wid,step_id,uid,n,day.isoformat(),note,int(time.time())))
    return entry_id


def report(c, uid, wid=''):
    base = quantum.report(c,uid,wid)
    wid = base['workspace_id']
    if not wid:
        return {'workspace_id':None,'summary':{},'plans':[],'recommendations':[],'history':[],'limitations':[]}
    logs = c.execute('''SELECT id,step_id,actor_id,hours,work_date,note,created
        FROM omniscience_effort_v49 WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT 5000''',(wid,)).fetchall()
    history = [dict(zip(('id','step_id','actor_id','hours','work_date','note','created'),r)) for r in logs]
    by_step = {}
    for log in history:
        by_step[log['step_id']] = round(by_step.get(log['step_id'],0)+log['hours'],2)
    plans=[]; ratios=[]; completed=[]; overdue=[]; unestimated=[]; over_budget=[]; open_hours=0
    for p in base['plans']:
        steps=[]
        for step in p['steps']:
            s=dict(step)
            s['actual_hours']=by_step.get(s['id'],0)
            estimate=s['estimated_hours']
            s['variance_hours']=round(s['actual_hours']-estimate,2) if estimate is not None else None
            s['remaining_estimate_hours']=max(0,round(estimate-s['actual_hours'],2)) if estimate is not None and s['status'] in ('todo','doing') else 0
            if s['status'] in ('todo','doing') and p['status']=='active':
                if estimate is None:unestimated.append(s)
                else:
                    open_hours+=s['remaining_estimate_hours']
                    if s['actual_hours']>estimate:over_budget.append(s)
                if s['risk']=='overdue':overdue.append(s)
            if s['status']=='done' and estimate is not None and s['actual_hours']>0:
                ratios.append(s['actual_hours']/estimate)
                completed.append(s)
            steps.append(s)
        plans.append({**p,'steps':steps})
    typical_ratio=round(statistics.median(ratios),3) if ratios else None
    # The adjustment is deliberately not used without at least three comparable completed milestones.
    multiplier=max(0.5,min(3.0,typical_ratio)) if len(ratios)>=3 else 1.0
    weekly=base['weekly_capacity_hours']
    adjusted_hours=round(open_hours*multiplier,2)
    recommendations=[]
    if unestimated:recommendations.append({'priority':'high','reason':f'{len(unestimated)} open milestones have no effort estimates','action':'Add estimates in Quantum Command','source':'missing-estimates'})
    if overdue:recommendations.append({'priority':'high','reason':f'{len(overdue)} milestones are past their due date','action':'Review dates and prerequisites in Hyperion','source':'overdue'})
    if over_budget:recommendations.append({'priority':'medium','reason':f'{len(over_budget)} open milestones have logged more hours than estimated','action':'Review scope and revise unfinished milestone estimates','source':'over-estimate'})
    if len(ratios)<3:recommendations.append({'priority':'info','reason':f'Only {len(ratios)} completed milestones have both an estimate and logged work','action':'Collect at least three comparable completed milestones before using historical adjustments','source':'limited-history'})
    elif typical_ratio>1.2:recommendations.append({'priority':'medium','reason':f'Median actual-to-estimated effort ratio is {typical_ratio:.2f} across {len(ratios)} completed milestones','action':'Review estimation assumptions before committing to new dates','source':'historical-overrun'})
    elif typical_ratio<0.8:recommendations.append({'priority':'info','reason':f'Median actual-to-estimated effort ratio is {typical_ratio:.2f} across {len(ratios)} completed milestones','action':'Review whether estimates consistently include unused contingency','source':'historical-underrun'})
    return {'workspace_id':wid,'summary':{
        'active_plans':base['summary']['active_plans'],
        'logged_entries_in_report':len(history),'logged_hours_in_report':round(sum(x['hours'] for x in history),2),
        'completed_milestones_with_comparable_data':len(ratios),
        'median_actual_to_estimate_ratio':typical_ratio,
        'open_remaining_estimated_hours':round(open_hours,2),
        'historically_adjusted_open_hours':adjusted_hours,
        'weekly_capacity_hours':weekly,
        'illustrative_capacity_weeks':math.ceil(adjusted_hours/weekly) if weekly>0 else None,
        'overdue_milestones':len(overdue),'over_estimate_open_milestones':len(over_budget),
        'unestimated_open_milestones':len(unestimated),
        'historical_adjustment_applied':len(ratios)>=3},
        'plans':plans,'recommendations':recommendations,'history':history,
        'limitations':['Hours are manually reported and are not verified by a time tracker',
        'Effort log entries are append-only; correct mistakes by adding explanatory notes outside this tool',
        'Reports show at most the 5000 most recent log entries per workspace',
        'Historical adjustment requires three completed milestones with estimates and actual work; it is capped between 0.5x and 3x',
        'Capacity weeks are illustrative effort/capacity calculations, not completion-date forecasts',
        'No automated execution, causal business outcome claims, or guaranteed profit improvements']}


def render(c,uid,csrf,wid=''):
    r=report(c,uid,wid)
    esc=lambda v:html.escape(str(v),quote=True)
    if not r['workspace_id']:
        return '<section class="panel"><h1>Omniscience V49</h1><p>Create a workspace first.</p></section>'
    wid=r['workspace_id'];role=core._role(c,uid,wid)
    q=urlencode({'w':wid})
    hidden='<input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="workspace" value="'+esc(wid)+'">'
    s=r['summary']
    out=['<section class="panel"><h1>✦ OMNISCIENCE V49 — Delivery Intelligence</h1><p>Real logged effort, historical estimation accuracy and evidence-based management review.</p><p><a href="/omniscience.json?'+esc(q)+'">Download JSON evidence</a> · <a href="/quantum-command?'+esc(q)+'">Capacity planning</a> · <a href="/hyperion?'+esc(q)+'">Delivery plans</a></p><div class="grid">']
    for title,key in [('Actual hours logged','logged_hours_in_report'),('Open estimated hours','open_remaining_estimated_hours'),('Historical ratio','median_actual_to_estimate_ratio'),('Illustrative capacity weeks','illustrative_capacity_weeks')]:
        out.append('<article><h3>'+esc(title)+'</h3><strong>'+esc(s[key] if s[key] is not None else 'Insufficient data')+'</strong></article>')
    out.append('</div></section><section class="panel"><h2>Management review</h2>')
    for rec in r['recommendations']:
        out.append('<article><strong>'+esc(rec['priority'].upper())+'</strong> — '+esc(rec['reason'])+'<p>'+esc(rec['action'])+'</p></article>')
    if not r['recommendations']:out.append('<p>No priority flags in the current sample.</p>')
    out.append('</section>')
    for p in r['plans']:
        out.append('<section class="panel"><h2>'+esc(p['title'])+'</h2><p>'+esc(p['status'])+'</p>')
        for st in p['steps']:
            out.append('<article style="border-top:1px solid #655777;padding:12px 0"><strong>'+esc(st['title'])+'</strong> · '+esc(st['status'])+'<p>Estimated '+esc(st['estimated_hours'] if st['estimated_hours'] is not None else 'Not set')+' h · Actual '+esc(st['actual_hours'])+' h · Variance '+esc(st['variance_hours'] if st['variance_hours'] is not None else 'Unknown')+' h</p>')
            if role in ('owner','editor') and p['status']=='active' and st['status']!='cancelled':
                out.append('<form method="post" action="/omniscience">'+hidden+'<input type="hidden" name="action" value="log"><input type="hidden" name="step" value="'+esc(st['id'])+'"><label>Hours worked<input type="number" name="hours" min="0.01" max="24" step="0.01" required></label><label>Work date<input type="date" name="date" max="'+datetime.date.today().isoformat()+'" required></label><label>Evidence of work<textarea name="note" minlength="10" maxlength="1000" required></textarea></label><button>Record actual effort</button></form>')
            out.append('</article>')
        out.append('</section>')
    out.append('<section class="panel"><h2>Latest work entries</h2>')
    for entry in r['history'][:30]:
        out.append('<article><strong>'+esc(entry['work_date'])+' · '+esc(entry['hours'])+' h</strong><p>'+esc(entry['note'])+'</p></article>')
    out.append('</section><section class="panel"><h2>Limitations</h2><ul>'+''.join('<li>'+esc(x)+'</li>' for x in r['limitations'])+'</ul></section>')
    return ''.join(out)
