"""Read-only executive briefing built from tenant-scoped CRM facts."""
import html
import time
import sales_pipeline
import sovereign_ascension
import ascension_recovery
import ascension_followups
import ascension_next_actions
import ascension_command_center

def esc(x):return html.escape(str(x),quote=True)

def briefing(c,owner,now=None):
    now=int(time.time() if now is None else now)
    ascension_command_center.snapshot(c,owner)
    signals=ascension_next_actions.recommendations(c,owner,now=now)
    since=now-7*86400
    new_leads=c.execute("SELECT COUNT(*) FROM sales_pipeline_leads WHERE owner_id=? AND created_at>=? AND created_at<=?",(owner,since,now)).fetchone()[0]
    touched=c.execute("SELECT COUNT(*) FROM sales_pipeline_leads WHERE owner_id=? AND updated_at>=? AND updated_at<=?",(owner,since,now)).fetchone()[0]
    completed=c.execute("SELECT COUNT(*) FROM ascension_actions WHERE owner_id=? AND status='completed' AND updated_at>=? AND updated_at<=?",(owner,since,now)).fetchone()[0]
    outcomes=dict(c.execute("SELECT outcome,COUNT(*) FROM ascension_recovery_outcomes WHERE owner_id=? AND created_at>=? AND created_at<=? GROUP BY outcome",(owner,since,now)).fetchall())
    reported=c.execute("SELECT COALESCE(SUM(amount_cents),0) FROM ascension_recovery_outcomes WHERE owner_id=? AND outcome='payment_reported' AND created_at>=? AND created_at<=?",(owner,since,now)).fetchone()[0]
    return dict(new_leads=new_leads,updated_leads=touched,completed=completed,outcomes=outcomes,
        reported_cents=reported,queue=signals,blocked=sum(x['state']=='contact_blocked' for x in signals),
        awaiting=sum(x['state']=='awaiting_outcome' for x in signals),since=since,until=now)

def dashboard(c,owner):
    s=briefing(c,owner)
    parts=['<section class="hero"><h1>Executive Briefing</h1><p>A factual seven-day operating summary for your business, using VELXTRIA CRM records only. No messages or reports are sent automatically.</p></section>']
    parts.append('<section class="panel"><h2>Last seven days</h2><p>'+str(s['new_leads'])+' new CRM leads · '+str(s['updated_leads'])+' leads updated · '+str(s['completed'])+' actions completed</p><p>'+str(s['outcomes'].get('responded',0))+' recorded responses · '+str(s['outcomes'].get('meeting_booked',0))+' recorded meetings booked · '+str(s['outcomes'].get('no_response',0))+' recorded no-responses</p><p>$'+format(s['reported_cents']/100,'.2f')+' payments reported by users (unverified; not independently attributed or verified).</p></section>')
    parts.append('<section class="panel"><h2>Operational risks</h2><p>'+str(s['blocked'])+' opportunities have contact restrictions or missing verification. '+str(s['awaiting'])+' completed actions still need outcome records.</p><p>CRM timestamps can miss calls and activity outside VELXTRIA. No inferred conversion rates or revenue promises.</p></section>')
    parts.append('<section class="panel"><h2>Top five next actions</h2>')
    for item in s['queue'][:5]:
        parts.append('<article><strong>'+esc(item['business'])+'</strong><p>Priority '+str(item['priority'])+'/100 · '+esc(item['evidence'])+'</p><p>'+esc(item['next_step'])+'</p><a href="'+item['target']+'">Review in workspace</a></article>')
    if not s['queue']:parts.append('<p>No qualifying aging opportunities in the CRM.</p>')
    parts.append('</section><section class="panel"><h2>Continue working</h2><p><a href="/ascension-next-actions">Full action queue</a> · <a href="/ascension-command">Revenue Command Center</a> · <a href="/ascension-recovery">Outcome ledger</a></p></section>')
    return ''.join(parts)
