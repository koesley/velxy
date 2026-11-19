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

def discover(c, owner, at=None):
    """Only report opportunities supported by the owner's existing CRM records."""
    sales_pipeline.setup(c)
    setup(c)
    now=int(time.time() if at is None else at)
    leads=c.execute("""SELECT id,business,email,stage,estimated_value,updated_at
                       FROM sales_pipeline_leads WHERE owner_id=?
                       AND stage NOT IN ('won','lost') ORDER BY updated_at ASC, id ASC LIMIT 500""",(owner,)).fetchall()
    existing={(row[0],row[1]) for row in c.execute(
        "SELECT lead_id,kind FROM ascension_actions WHERE owner_id=? AND status IN ('approved','completed','dismissed')",(owner,)).fetchall()}
    # Fetch suppression decisions in one owner-scoped query; avoid per-lead lookups.
    suppression={row[0].strip().lower():row[1] for row in c.execute(
        "SELECT email,status FROM outreach_suppression WHERE owner_id=?",(owner,)).fetchall()}
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
        contact_state=suppression.get((email or '').strip().lower(), "unverified" if email else "missing_email")
        blocked=contact_state in ("do_not_contact","suppress_permanent","suppress_rejected","hold_for_verification")
        urgency="high" if days>=14 else "medium"
        score=(30 if urgency=="high" else 15)+(15 if stage in ('proposal','meeting') else 5)+min(days,30)
        items.append(dict(lead_id=lid,business=business,kind=kind,days=days,
                          stage=stage,estimated_value=value,contact_state=contact_state,
                          urgency=urgency,score=score,recommendation=(
                              "Do not contact this lead. Review suppression and CRM data manually."
                              if blocked else recommendation),contact_blocked=blocked,
                          evidence=f"CRM stage: {stage}; last CRM update: {days} days ago",
                          assumption="CRM activity timestamps may not reflect activity outside VELXTRIA.",
                          impact="Unknown: estimated deal value is not recovered revenue.",
                          effort="Manual review required"))
    return sorted(items,key=lambda item:(-item['score'],item['business'].lower()))

def action(c, owner, lead_id, kind, decision, note=""):
    """Records internal approval only. Never executes an external action."""
    sales_pipeline.setup(c)
    setup(c)
    if not isinstance(note,str) or len(note)>500 or any(ord(ch)<32 and ch not in "\n\t" for ch in note):
        raise ValueError("Outcome note must be at most 500 characters without control characters")
    if decision not in ('approved','dismissed','completed'):
        raise ValueError("Invalid decision")
    if kind not in ('stalled_deal','unanswered_reply','aging_lead'):
        raise ValueError("Invalid opportunity type")
    lead=c.execute("SELECT id FROM sales_pipeline_leads WHERE owner_id=? AND id=?",(owner,lead_id)).fetchone()
    if not lead:
        raise ValueError("Lead not found")
    if decision=='completed':
        existing=c.execute("""SELECT id FROM ascension_actions WHERE owner_id=? AND lead_id=?
          AND kind=? AND status='approved' ORDER BY created_at DESC LIMIT 1""",(owner,lead_id,kind)).fetchone()
        if not existing:
            raise ValueError("An approved action is required before completion")
        c.execute("UPDATE ascension_actions SET status='completed',note=?,updated_at=? WHERE id=? AND owner_id=?",
                  (note[:500],int(time.time()),existing[0],owner))
        return existing[0]
    if decision=="approved":
        prior=c.execute("""SELECT id FROM ascension_actions WHERE owner_id=? AND lead_id=?
          AND kind=? AND status='approved' LIMIT 1""",(owner,lead_id,kind)).fetchone()
        if prior:
            return prior[0]
    ident=secrets.token_hex(12)
    c.execute("""INSERT INTO ascension_actions VALUES (?,?,?,?,?,?,?,?)""",
              (ident,owner,lead_id,kind,decision,note[:500],int(time.time()),int(time.time())))
    return ident

def dashboard(c, owner, csrf):
    items=discover(c,owner)
    approvals=c.execute("""SELECT a.id,l.business,a.kind,a.status,a.lead_id
      FROM ascension_actions a JOIN sales_pipeline_leads l
      ON l.id=a.lead_id AND l.owner_id=a.owner_id
      WHERE a.owner_id=? AND a.status='approved' ORDER BY a.updated_at DESC LIMIT 100""",(owner,)).fetchall()
    counts=dict(c.execute("SELECT status,COUNT(*) FROM ascension_actions WHERE owner_id=? GROUP BY status",(owner,)).fetchall())
    parts=['<section class="hero"><h1>Sovereign Ascension</h1><p>Evidence-backed CRM opportunities and human-approved action tracking. No messages are sent automatically.</p></section>']
    blocked_count=sum(bool(item['contact_blocked']) for item in items)
    parts.append('<section class="panel"><h2>Business pulse</h2><p>'+str(len(items))+' actionable CRM signals · '+str(blocked_count)+' contact-restricted signals · '+str(counts.get('approved',0))+' approved tasks · '+str(counts.get('completed',0))+' completed tasks</p><p>Estimated deal values are not collected revenue. Missing data is shown as unknown. Signals are based on up to 500 oldest open CRM records; only 50 are displayed.</p></section>')
    parts.append('<section class="panel"><h2>Priority queue</h2>')
    if not items:
        parts.append('<p>No aging CRM opportunities detected. Add leads to Sales Pipeline to begin.</p>')
    for item in items[:50]:
        parts.append('<article><h3>'+esc(item['business'])+' — '+esc(item['kind'].replace('_',' ').title())+'</h3><p>Priority: '+esc(item['urgency'])+' · '+esc(item['evidence'])+'</p><p>'+esc(item['recommendation'])+'</p><p>Contact: '+esc(item['contact_state'])+' · Financial impact: '+esc(item['impact'])+'</p><p>'+esc(item['assumption'])+'</p>')
        if item['contact_blocked']:
            parts.append('<p><strong>Contact restricted: do not send outreach.</strong></p>')
        for decision in ('approved','dismissed'):
            parts.append('<form method="post" action="/ascension-action"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="lead_id" value="'+esc(item['lead_id'])+'"><input type="hidden" name="kind" value="'+esc(item['kind'])+'"><input type="hidden" name="decision" value="'+decision+'"><button type="submit">'+decision.title()+'</button></form>')
        parts.append('</article>')
    parts.append('</section><section class="panel"><h2>Approved actions</h2>')
    for ident,business,kind,status,lid in approvals:
        parts.append('<article><p>'+esc(business)+' — '+esc(kind.replace('_',' '))+'</p><form method="post" action="/ascension-action"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="lead_id" value="'+esc(lid)+'"><input type="hidden" name="kind" value="'+esc(kind)+'"><input type="hidden" name="decision" value="completed"><label>Outcome note<input name="note" maxlength="500" required></label><button type="submit">Mark completed</button></form></article>')
    if not approvals:
        parts.append('<p>No approved actions pending.</p>')
    parts.append('</section>')
    return ''.join(parts)
