"""Revenue Command Center: owner-scoped, evidence-labeled sales funnel analytics.

All sales amounts are user-entered estimates. No external actions.
"""
import html
import time
import sales_pipeline
import sovereign_ascension
import ascension_recovery
import ascension_followups

def esc(x):
    return html.escape(str(x), quote=True)

def snapshot(c, owner, now=None):
    sales_pipeline.setup(c)
    sovereign_ascension.setup(c)
    ascension_recovery.setup(c)
    ascension_followups.setup(c)
    now = int(time.time()) if now is None else int(now)
    stages = dict(c.execute("SELECT stage,COUNT(*) FROM sales_pipeline_leads WHERE owner_id=? GROUP BY stage", (owner,)).fetchall())
    actions = dict(c.execute("SELECT status,COUNT(*) FROM ascension_actions WHERE owner_id=? GROUP BY status", (owner,)).fetchall())
    outcomes = dict(c.execute("SELECT outcome,COUNT(*) FROM ascension_recovery_outcomes WHERE owner_id=? GROUP BY outcome", (owner,)).fetchall())
    drafts = c.execute("SELECT COUNT(*) FROM ascension_followup_drafts WHERE owner_id=? AND status='draft'", (owner,)).fetchone()[0]
    reported = c.execute("SELECT COALESCE(SUM(amount_cents),0) FROM ascension_recovery_outcomes WHERE owner_id=? AND outcome='payment_reported'", (owner,)).fetchone()[0]
    eligible = c.execute("""SELECT COUNT(*) FROM ascension_followup_drafts d
        JOIN outreach_suppression s ON s.owner_id=d.owner_id AND s.email=d.recipient
        WHERE d.owner_id=? AND d.status='draft' AND s.status='verified_clear'""", (owner,)).fetchone()[0]
    pending = c.execute("""SELECT COUNT(*) FROM ascension_actions a WHERE a.owner_id=? AND a.status='completed'
        AND NOT EXISTS(SELECT 1 FROM ascension_recovery_outcomes o WHERE o.owner_id=a.owner_id AND o.action_id=a.id)""", (owner,)).fetchone()[0]
    # Aggregate in SQL, not a capped display list. No cross-account joins.
    values = dict(c.execute("""SELECT stage,COALESCE(SUM(estimated_value),0)
        FROM sales_pipeline_leads WHERE owner_id=? GROUP BY stage""", (owner,)).fetchall())
    old_open = c.execute("""SELECT COUNT(*) FROM sales_pipeline_leads
        WHERE owner_id=? AND stage NOT IN ('won','lost') AND updated_at<?""",
        (owner, now-14*86400)).fetchone()[0]
    suppressed = c.execute("""SELECT COUNT(*) FROM sales_pipeline_leads l
        JOIN outreach_suppression s ON s.owner_id=l.owner_id AND s.email=LOWER(l.email)
        WHERE l.owner_id=? AND l.stage NOT IN ('won','lost')
          AND s.status IN ('do_not_contact','suppress_permanent','suppress_rejected')""",
        (owner,)).fetchone()[0]
    return dict(stages=stages, actions=actions, outcomes=outcomes, drafts=drafts,
                eligible_drafts=eligible, awaiting_outcome=pending, reported_cents=reported,
                stage_values=values, stale_open=old_open, blocked_open=suppressed)

def dashboard(c, owner):
    s = snapshot(c, owner)
    stages=s['stages']; actions=s['actions']; outcomes=s['outcomes']
    leads=sum(stages.values())
    open_stages=('new','contacted','replied','meeting','proposal')
    open_count=sum(stages.get(x,0) for x in open_stages)
    open_value=sum(s['stage_values'].get(x,0) for x in open_stages)
    won_value=s['stage_values'].get('won',0)
    parts=['<section class="hero"><h1>Revenue Command Center</h1><p>See how CRM leads progress through review, manual follow-up and reported outcomes. All figures are scoped to your account.</p></section>']
    parts.append('<section class="panel"><h2>Sales pipeline</h2><p>'+str(leads)+' total leads · '+str(stages.get('proposal',0))+' proposals · '+str(stages.get('meeting',0))+' meetings · '+str(stages.get('won',0))+' marked won</p><p>Won is a CRM stage, not evidence of received payment.</p></section>')
    parts.append('<section class="panel"><h2>Opportunity health</h2><p>'+str(open_count)+' open leads · $'+str(open_value)+' estimated open value · $'+str(won_value)+' self-reported won value</p><p>'+str(s['stale_open'])+' open leads unchanged for 14+ days · '+str(s['blocked_open'])+' open leads with blocked contact addresses</p><p>Aging measures last CRM update, not last customer contact. Blocked addresses must not be contacted. Deal values are estimates, not verified revenue.</p><p><a href="/sales-pipeline">Review pipeline and contact restrictions</a></p></section>')
    parts.append('<section class="panel"><h2>Follow-up execution</h2><p>'+str(actions.get('approved',0))+' approved tasks · '+str(actions.get('completed',0))+' completed tasks · '+str(s['drafts'])+' saved drafts · '+str(s['eligible_drafts'])+' drafts with currently verified-clear recipients</p><p>'+str(s['awaiting_outcome'])+' completed tasks need an outcome recorded.</p><p>Drafts are never automatically sent. Verification is required before use.</p></section>')
    parts.append('<section class="panel"><h2>Recorded results</h2><p>'+str(outcomes.get('responded',0))+' responses · '+str(outcomes.get('meeting_booked',0))+' meetings booked · '+str(outcomes.get('deal_won_unverified',0))+' unverified deal wins · '+str(outcomes.get('no_response',0))+' no responses</p><p>$'+format(s['reported_cents']/100,'.2f')+' user-reported payments (unverified)</p><p>Reported outcomes are user-entered, not independently verified. These totals do not establish incremental revenue or attribution.</p></section>')
    parts.append('<section class="panel"><h2>Next actions</h2><p><a href="/ascension">Review opportunities</a> · <a href="/ascension-followups">Prepare follow-up drafts</a> · <a href="/ascension-recovery">Record completed outcomes</a> · <a href="/sales-pipeline">Update CRM leads</a></p></section>')
    return ''.join(parts)
