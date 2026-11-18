"""Sovereign Intelligence Core: owner-scoped, provenance-aware business context.

Read-only aggregation. Sources are CRM and manual workflow records; never inferred
as verified payments, customer intent, or guaranteed business outcomes.
"""
import html
import time
import sales_pipeline
import sovereign_ascension
import ascension_followups
import ascension_recovery
import ascension_workflows
import ascension_next_actions

def esc(v):
    return html.escape(str(v),quote=True)

def context(c,owner,now=None):
    now=int(time.time() if now is None else now)
    sales_pipeline.setup(c)
    sovereign_ascension.setup(c)
    ascension_followups.setup(c)
    ascension_recovery.setup(c)
    ascension_workflows.setup(c)
    leads=c.execute("""SELECT id,business,stage,estimated_value,updated_at
        FROM sales_pipeline_leads WHERE owner_id=? ORDER BY updated_at DESC LIMIT 500""",(owner,)).fetchall()
    actions=c.execute("""SELECT id,lead_id,status,kind,updated_at
        FROM ascension_actions WHERE owner_id=? ORDER BY updated_at DESC LIMIT 500""",(owner,)).fetchall()
    workflows=c.execute("""SELECT id,action_id,status,current_step,updated_at
        FROM ascension_workflows WHERE owner_id=? ORDER BY updated_at DESC LIMIT 500""",(owner,)).fetchall()
    outcomes=c.execute("""SELECT action_id,outcome,amount_cents,created_at
        FROM ascension_recovery_outcomes WHERE owner_id=? ORDER BY created_at DESC LIMIT 500""",(owner,)).fetchall()
    drafts=c.execute("""SELECT action_id,status,updated_at
        FROM ascension_followup_drafts WHERE owner_id=? ORDER BY updated_at DESC LIMIT 500""",(owner,)).fetchall()
    by_lead={}
    for lid,business,stage,value,updated in leads:
        by_lead[lid]=dict(id=lid,business=business,stage=stage,estimated_value=value,
            last_crm_update=updated,source="sales_pipeline_leads",reliability="user_entered",
            actions=[],workflows=[],outcomes=[],drafts=[])
    action_lead={}
    for aid,lid,status,kind,updated in actions:
        if lid in by_lead:
            action_lead[aid]=lid
            by_lead[lid]["actions"].append(dict(id=aid,status=status,kind=kind,
                timestamp=updated,source="ascension_actions",reliability="user_entered"))
    for wid,aid,status,step,updated in workflows:
        if aid in action_lead:
            by_lead[action_lead[aid]]["workflows"].append(dict(id=wid,action_id=aid,
                status=status,step=step,timestamp=updated,source="ascension_workflows",
                reliability="system_recorded"))
    for aid,outcome,cents,created in outcomes:
        if aid in action_lead:
            by_lead[action_lead[aid]]["outcomes"].append(dict(action_id=aid,
                outcome=outcome,reported_cents=cents,timestamp=created,
                source="ascension_recovery_outcomes",reliability="user_reported_unverified"))
    for aid,status,updated in drafts:
        if aid in action_lead:
            by_lead[action_lead[aid]]["drafts"].append(dict(action_id=aid,status=status,
                timestamp=updated,source="ascension_followup_drafts",
                reliability="internal_draft_not_sent"))
    recommendations=ascension_next_actions.recommendations(c,owner,now=now)
    return dict(owner_id=owner,generated_at=now,leads=list(by_lead.values()),
        recommendations=recommendations,
        source_limits="CRM updates may omit external activity; payment outcomes are unverified user reports")

def decisions(c,owner,now=None):
    ctx=context(c,owner,now)
    queue=[]
    for rec in ctx["recommendations"]:
        state=rec["state"]
        if state=="contact_blocked":
            risk="Contact unverified or restricted; outreach prohibited until eligibility changes"
            objective="Resolve contact eligibility without sending a message"
        elif state=="awaiting_outcome":
            risk="Result is missing; do not assume a successful sale"
            objective="Record an accurate outcome for completed work"
        else:
            risk="CRM timestamps may omit external activity; estimated value is not revenue"
            objective="Review the opportunity and determine an appropriate manual next step"
        queue.append(dict(title=rec["business"]+" — "+state.replace("_"," "),
            lead_id=rec["lead_id"],priority=rec["priority"],
            evidence=rec["evidence"],objective=objective,next_step=rec["next_step"],
            target=rec["target"],risk=risk,
            uncertainty="Rule-based CRM signal, not a calibrated success prediction",
            required_permission="Authenticated owner; human confirmation for changes",
            completion="Owner records an approved action or outcome",
            measurement="Review manual workflow and recorded outcome history",
            sources=["sales_pipeline_leads","ascension_actions"],
            financial_impact="Unknown; deal value is an estimate, not collected revenue"))
    return queue

def dashboard(c,owner):
    ctx=context(c,owner)
    items=decisions(c,owner,ctx["generated_at"])
    active=sum(w["status"]=="active" for lead in ctx["leads"] for w in lead["workflows"])
    reported=sum(o["reported_cents"] for lead in ctx["leads"] for o in lead["outcomes"] if o["outcome"]=="payment_reported")
    parts=['<section class="hero"><h1>Sovereign Intelligence Core</h1><p>Unified evidence from your CRM, approved actions, internal workflows and manually reported results. No external actions occur here.</p></section>']
    parts.append('<section class="panel"><h2>Business context</h2><p>'+str(len(ctx["leads"]))+' CRM records · '+str(active)+' active workflows · '+str(len(items))+' prioritized decisions</p><p>$'+format(reported/100,'.2f')+' user-reported payments (unverified; records limited to latest 500 per source)</p><p>'+esc(ctx["source_limits"])+'</p></section>')
    parts.append('<section class="panel"><h2>Evidence-backed decisions</h2>')
    for item in items[:25]:
        parts.append('<article><h3>'+esc(item["title"])+'</h3><p>Priority '+str(item["priority"])+'/100 · '+esc(item["objective"])+'</p><p><strong>Evidence:</strong> '+esc(item["evidence"])+'</p><p><strong>Next step:</strong> '+esc(item["next_step"])+'</p><p><strong>Risk:</strong> '+esc(item["risk"])+'</p><p><strong>Uncertainty:</strong> '+esc(item["uncertainty"])+'</p><p><strong>Sources:</strong> '+esc(", ".join(item["sources"]))+'</p><p><a href="'+item["target"]+'">Review in workspace</a></p></article>')
    if not items:parts.append('<p>No stale opportunities currently qualify. Add or update leads in the CRM.</p>')
    parts.append('</section><section class="panel"><h2>Connected workspaces</h2><p><a href="/sales-pipeline">CRM</a> · <a href="/ascension-workflows">Workflows</a> · <a href="/ascension-recovery">Outcome ledger</a> · <a href="/ascension-briefing">Executive briefing</a></p></section>')
    return ''.join(parts)
