"""Sovereign Ascension: evidence-backed opportunity and approval workspace.

No external actions, mail sends, payment changes, or inferred received revenue.
Uses existing sales_pipeline_leads as its source of truth.
"""
import html
import secrets
import time
import sales_pipeline

def esc(value):
    return html.escape(str(value),quote=True)

def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS ascension_actions (
      id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL, lead_id TEXT NOT NULL,
      kind TEXT NOT NULL, status TEXT NOT NULL, note TEXT NOT NULL,
      created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS ascension_actions_owner ON ascension_actions(owner_id,lead_id,status)")
    # Append-only decision evidence. Existing actions are not rewritten on migration.
    c.execute("""CREATE TABLE IF NOT EXISTS ascension_action_events (
      id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL, action_id TEXT NOT NULL,
      lead_id TEXT NOT NULL, kind TEXT NOT NULL, event_type TEXT NOT NULL,
      note TEXT NOT NULL, created_at INTEGER NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS ascension_events_owner ON ascension_action_events(owner_id,created_at)")


def discover(c, owner, at=None):
    """Only report opportunities supported by the owner's existing CRM records."""
    sales_pipeline.setup(c)
    setup(c)
    now=int(time.time() if at is None else at)
    leads=c.execute("""SELECT id,business,email,stage,estimated_value,updated_at
                       FROM sales_pipeline_leads WHERE owner_id=?
                       AND stage NOT IN ('won','lost') ORDER BY updated_at ASC LIMIT 500""",(owner,)).fetchall()
    existing={(row[0],row[1]) for row in c.execute(
        "SELECT lead_id,kind FROM ascension_actions WHERE owner_id=? AND status IN ('approved','completed','dismissed')",(owner,)).fetchall()}
    items=[]
    for lid,business,email,stage,value,updated in leads:
        days=max(0,(now-int(updated))//86400)
        kind=None
        if stage in ('proposal','meeting') and days>=7:
            kind="stalled_deal"
            recommendation="Review the deal and prepare a personalized follow-up for approval."
        elif stage=='replied' and days>=2:
            kind="unanswered_reply"
            recommendation="Review the conversation and decide whether a response is appropriate."
        elif stage in ('new','contacted') and days>=7:
            kind="aging_lead"
            recommendation="Check the lead's relevance and contact eligibility before any follow-up."
        else:
            continue
        if (lid,kind) in existing:
            continue
        status=c.execute("SELECT status FROM outreach_suppression WHERE owner_id=? AND email=?",
                         (owner,(email or '').lower())).fetchone()
        contact_state=status[0] if status else "unverified"
        urgency="high" if days>=14 else "medium"
        score=(30 if urgency=="high" else 15)+(15 if stage in ('proposal','meeting') else 5)+min(days,30)
        items.append(dict(lead_id=lid,business=business,kind=kind,days=days,
                          stage=stage,estimated_value=value,contact_state=contact_state,
                          urgency=urgency,score=score,recommendation=recommendation,
                          evidence=f"CRM stage: {stage}; last CRM update: {days} days ago",
                          assumption="CRM activity timestamps may not reflect activity outside VELXTRIA.",
                          impact="Unknown: estimated deal value is not recovered revenue.",
                          effort="Manual review required"))
    return sorted(items,key=lambda item:(-item['score'],item['business'].lower()))

def _audit(c,owner,action_id,lead_id,kind,event_type,note,at):
    c.execute("""INSERT INTO ascension_action_events
      (id,owner_id,action_id,lead_id,kind,event_type,note,created_at)
      VALUES (?,?,?,?,?,?,?,?)""",
      (secrets.token_hex(12),owner,action_id,lead_id,kind,event_type,note,at))

def action(c, owner, lead_id, kind, decision, note=""):
    """Records internal approval only. Never executes an external action."""
    sales_pipeline.setup(c)
    setup(c)
    if decision not in ('approved','dismissed','completed'):
        raise ValueError("Invalid decision")
    if kind not in ('stalled_deal','unanswered_reply','aging_lead'):
        raise ValueError("Invalid opportunity type")
    lead=c.execute("SELECT id FROM sales_pipeline_leads WHERE owner_id=? AND id=?",(owner,lead_id)).fetchone()
    if not lead:
        raise ValueError("Lead not found")
    note=str(note or "").strip()
    if len(note)>500:
        raise ValueError("Action note exceeds 500 characters")
    if decision=='completed':
        if len(note)<12:
            raise ValueError("Completion requires an outcome note of at least 12 characters")
        existing=c.execute("""SELECT id FROM ascension_actions WHERE owner_id=? AND lead_id=?
          AND kind=? AND status='approved' ORDER BY created_at DESC LIMIT 1""",(owner,lead_id,kind)).fetchone()
        if not existing:
            raise ValueError("An approved action is required before completion")
        updated=c.execute("UPDATE ascension_actions SET status='completed',note=?,updated_at=? WHERE id=? AND owner_id=? AND status='approved'",
                  (note,int(time.time()),existing[0],owner))
        if updated.rowcount!=1:
            raise ValueError("Action was already completed or changed")
        _audit(c,owner,existing[0],lead_id,kind,'completed',note,int(time.time()))
        return existing[0]
    # Decisions must apply to a currently actionable CRM signal, not an
    # arbitrary caller-supplied lead/type pair or an already decided item.
    eligible=any(item['lead_id']==lead_id and item['kind']==kind
                 for item in discover(c,owner))
    if not eligible:
        raise ValueError("Opportunity is no longer eligible for a new decision")
    if decision=='approved':
        # A suppression is never overridden by an internal approval.
        contact=c.execute("SELECT email FROM sales_pipeline_leads WHERE owner_id=? AND id=?",
                          (owner,lead_id)).fetchone()
        state=c.execute("SELECT status FROM outreach_suppression WHERE owner_id=? AND email=?",
                        (owner,(contact[0] or '').strip().lower())).fetchone()
        if state and state[0] in ('do_not_contact','suppress_permanent','suppress_rejected'):
            raise ValueError("Contact suppression blocks approval; review the lead instead")
    ident=secrets.token_hex(12)
    now=int(time.time())
    c.execute("""INSERT INTO ascension_actions VALUES (?,?,?,?,?,?,?,?)""",
              (ident,owner,lead_id,kind,decision,note,now,now))
    _audit(c,owner,ident,lead_id,kind,decision,note,now)
    return ident

def dashboard(c, owner, csrf):
    items=discover(c,owner)
    approvals=c.execute("""SELECT a.id,l.business,a.kind,a.status,a.lead_id
      FROM ascension_actions a JOIN sales_pipeline_leads l
      ON l.id=a.lead_id AND l.owner_id=a.owner_id
      WHERE a.owner_id=? AND a.status='approved' ORDER BY a.updated_at DESC LIMIT 100""",(owner,)).fetchall()
    counts=dict(c.execute("SELECT status,COUNT(*) FROM ascension_actions WHERE owner_id=? GROUP BY status",(owner,)).fetchall())
    parts=['<section class="hero"><h1>Sovereign Ascension</h1><p>Evidence-backed CRM opportunities and human-approved action tracking. No messages are sent automatically.</p></section>']
    parts.append('<section class="panel"><h2>Business pulse</h2><p>'+str(len(items))+' actionable CRM signals · '+str(counts.get('approved',0))+' approved tasks · '+str(counts.get('completed',0))+' completed tasks</p><p>Estimated deal values are not collected revenue. Missing data is shown as unknown.</p></section>')
    parts.append('<section class="panel"><h2>Priority queue</h2>')
    if not items:
        parts.append('<p>No aging CRM opportunities detected. Add leads to Sales Pipeline to begin.</p>')
    for item in items[:50]:
        parts.append('<article><h3>'+esc(item['business'])+' — '+esc(item['kind'].replace('_',' ').title())+'</h3><p>Priority: '+esc(item['urgency'])+' · '+esc(item['evidence'])+'</p><p>'+esc(item['recommendation'])+'</p><p>Contact: '+esc(item['contact_state'])+' · Financial impact: '+esc(item['impact'])+'</p><p>'+esc(item['assumption'])+'</p>')
        for decision in ('approved','dismissed'):
            parts.append('<form method="post" action="/ascension-action"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="lead_id" value="'+esc(item['lead_id'])+'"><input type="hidden" name="kind" value="'+esc(item['kind'])+'"><input type="hidden" name="decision" value="'+decision+'"><button type="submit">'+decision.title()+'</button></form>')
        parts.append('</article>')
    parts.append('</section><section class="panel"><h2>Approved actions</h2>')
    for ident,business,kind,status,lid in approvals:
        parts.append('<article><p>'+esc(business)+' — '+esc(kind.replace('_',' '))+'</p><form method="post" action="/ascension-action"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="lead_id" value="'+esc(lid)+'"><input type="hidden" name="kind" value="'+esc(kind)+'"><input type="hidden" name="decision" value="completed"><label>Outcome note<input name="note" maxlength="500" required></label><button type="submit">Mark completed</button></form></article>')
    if not approvals:
        parts.append('<p>No approved actions pending.</p>')
    parts.append('</section>')
    events=c.execute("""SELECT e.event_type,e.note,e.created_at,l.business
      FROM ascension_action_events e JOIN sales_pipeline_leads l
      ON l.id=e.lead_id AND l.owner_id=e.owner_id
      WHERE e.owner_id=? ORDER BY e.created_at DESC,e.id DESC LIMIT 50""",(owner,)).fetchall()
    parts.append('<section class="panel"><h2>Decision audit trail</h2><p>Recorded approvals, dismissals and completions. This history does not imply messages were sent or payments received.</p>')
    if not events:
        parts.append('<p>No recorded decisions yet.</p>')
    for event_type,event_note,created,business in events:
        parts.append('<article><strong>'+esc(business)+'</strong> · '+esc(event_type.title())+
                     ' · <time>'+esc(created)+'</time><p>'+esc(event_note or 'No note supplied')+'</p></article>')
    parts.append('</section>')
    return ''.join(parts)
