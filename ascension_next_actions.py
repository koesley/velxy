"""Deterministic, evidence-backed next-best-action recommendations for CRM owners.

Read-only. No outbound messages, financial transfers, or autonomous changes.
"""
import html
import time
import sales_pipeline
import sovereign_ascension
import ascension_followups
import ascension_recovery

def esc(value):
    return html.escape(str(value),quote=True)

def recommendations(c,owner,now=None):
    sales_pipeline.setup(c)
    sovereign_ascension.setup(c)
    ascension_followups.setup(c)
    ascension_recovery.setup(c)
    now=int(time.time() if now is None else now)
    queue=[]
    # Evaluate eligible leads across the workspace, not an arbitrary oldest prefix.
    # The three evidence maps replace per-lead action/draft/outcome lookups.
    leads=c.execute("""SELECT id,business,email,stage,estimated_value,updated_at
        FROM sales_pipeline_leads WHERE owner_id=? AND (
          (stage IN ('proposal','meeting','new','contacted') AND updated_at<=?)
          OR (stage='replied' AND updated_at<=?))
        ORDER BY updated_at ASC,id ASC""",(owner,now-7*86400,now-2*86400)).fetchall()
    if not leads:
        return []
    latest_actions={}
    for aid,lid,kind,status in c.execute("""SELECT id,lead_id,kind,status
        FROM ascension_actions WHERE owner_id=?
        ORDER BY updated_at DESC,created_at DESC,id DESC""",(owner,)).fetchall():
        latest_actions.setdefault((lid,kind),(aid,status))
    draft_actions={row[0] for row in c.execute(
        "SELECT action_id FROM ascension_followup_drafts WHERE owner_id=?",(owner,)).fetchall()}
    outcome_actions={row[0] for row in c.execute(
        "SELECT action_id FROM ascension_recovery_outcomes WHERE owner_id=?",(owner,)).fetchall()}
    # Keep the existing eligibility helper as the final authority. Batch its
    # backing suppression state to avoid per-lead lookups while retaining its
    # email validation and opt-out semantics.
    import outreach_deliverability
    suppression=dict(c.execute(
        "SELECT email,status FROM outreach_suppression WHERE owner_id=?",(owner,)).fetchall())
    for lid,business,email,stage,value,updated_at in leads:
        age=max(0,(now-int(updated_at))//86400)
        if age<2:continue
        if stage in ('proposal','meeting') and age>=7:
            priority=80
            kind='stalled_deal'
            why='Proposal or meeting has not been updated for at least seven days'
        elif stage=='replied' and age>=2:
            priority=75
            kind='unanswered_reply'
            why='Replied lead has not been updated for at least two days'
        elif stage in ('new','contacted') and age>=7:
            priority=55
            kind='aging_lead'
            why='Early-stage lead has not been updated for at least seven days'
        else:continue
        latest=latest_actions.get((lid,kind))
        state='needs_review'
        next_step='Review this opportunity in Sovereign Ascension'
        target='/ascension'
        if latest:
            aid,status=latest
            if status=='dismissed':continue
            if status=='approved':
                if aid in draft_actions:
                    state='draft_ready'
                    next_step='Review the saved draft; do not send without checking recipient eligibility'
                    target='/ascension-followups'
                else:
                    state='approved'
                    next_step='Prepare a manual follow-up draft if contact is verified clear'
                    target='/ascension-followups'
                priority+=10
            elif status=='completed':
                if aid in outcome_actions:continue
                state='awaiting_outcome'
                next_step='Record what happened after the completed action'
                target='/ascension-recovery'
                priority+=20
        normalized=(email or '').strip().lower()
        status=suppression.get(normalized)
        contact=bool(status and outreach_deliverability.eligible_for_new_outreach(
            normalized,{normalized:status}))
        if state in ('approved','draft_ready') and not contact:
            state='contact_blocked'
            next_step='Review contact suppression or verification; do not send outreach'
            target='/sales-pipeline'
        priority=min(100,priority+min(age//7,10))
        queue.append(dict(lead_id=lid,business=business,stage=stage,age_days=age,
            priority=priority,state=state,next_step=next_step,target=target,
            evidence=why,contact_eligible=contact,
            estimated_value=value,assumption='CRM timestamps may omit external activity'))
    return sorted(queue,key=lambda x:(-x['priority'],-x['age_days'],x['business'].lower(),x['lead_id']))[:100]

def dashboard(c,owner):
    items=recommendations(c,owner)
    blocked=sum(x['state']=='contact_blocked' for x in items)
    pending=sum(x['state']=='awaiting_outcome' for x in items)
    parts=['<section class="hero"><h1>Next Best Action Engine</h1><p>Prioritized CRM work based on existing records, not invented AI predictions. All actions require human review. No messages are sent.</p></section>']
    parts.append('<section class="panel"><h2>Execution overview</h2><p>'+str(len(items))+' recommendations · '+str(pending)+' awaiting outcome records · '+str(blocked)+' contact restrictions</p><p>Scores are rule-based ordering aids, not conversion probabilities. Estimated deal values are not received revenue.</p></section>')
    parts.append('<section class="panel"><h2>Priority work queue</h2>')
    for item in items:
        parts.append('<article><h3>'+esc(item['business'])+'</h3><p>Priority score '+str(item['priority'])+'/100 · '+esc(item['state'].replace('_',' '))+' · CRM stage '+esc(item['stage'])+'</p><p>Evidence: '+esc(item['evidence'])+' ('+str(item['age_days'])+' days since CRM update)</p><p>'+esc(item['next_step'])+'</p><p>Contact: '+('verified clear' if item['contact_eligible'] else 'unverified or restricted')+' · Estimated deal value: $'+format(item['estimated_value'],',d')+' (not received)</p><p>'+esc(item['assumption'])+'</p><p><a href="'+item['target']+'">Open relevant workspace</a></p></article>')
    if not items:parts.append('<p>No eligible stale CRM signals. Add or update leads in Sales Pipeline.</p>')
    parts.append('</section>')
    return ''.join(parts)
