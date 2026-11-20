"""Human-reviewed follow-up drafting. No email or other outbound side effects."""
import html
import secrets
import time
import sales_pipeline
import sovereign_ascension

def esc(value):
    return html.escape(str(value),quote=True)

def setup(c):
    sales_pipeline.setup(c)
    sovereign_ascension.setup(c)
    c.execute("""CREATE TABLE IF NOT EXISTS ascension_followup_drafts (
        id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL, action_id TEXT NOT NULL,
        lead_id TEXT NOT NULL, recipient TEXT NOT NULL, subject TEXT NOT NULL,
        body TEXT NOT NULL, status TEXT NOT NULL, created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL, UNIQUE(owner_id,action_id))""")
    c.execute("CREATE INDEX IF NOT EXISTS ascension_draft_owner ON ascension_followup_drafts(owner_id,status,updated_at)")

def draft_readiness(c, owner, draft_id):
    """Check the current action, lead, and recipient before editing a saved draft."""
    row = c.execute("""SELECT d.recipient,d.status,a.status,l.email,l.stage
        FROM ascension_followup_drafts d
        LEFT JOIN ascension_actions a ON a.id=d.action_id AND a.owner_id=d.owner_id
        LEFT JOIN sales_pipeline_leads l ON l.id=d.lead_id AND l.owner_id=d.owner_id
        WHERE d.owner_id=? AND d.id=?""", (owner, draft_id)).fetchone()
    if not row or row[1] != "draft":
        return False, "Draft is no longer editable"
    recipient, _, action_status, current_email, stage = row
    if action_status != "approved":
        return False, "Action is no longer approved"
    if not current_email or current_email.strip().casefold() != recipient.strip().casefold():
        return False, "Lead email has changed"
    if stage in ("won", "lost"):
        return False, "Lead is closed"
    if not sales_pipeline.outreach_eligibility(c, owner, recipient):
        return False, "Contact is suppressed or unverified"
    return True, "Eligible for manual review"


def prepare(c,owner,action_id):
    setup(c)
    row=c.execute("""SELECT a.lead_id,a.kind,l.business,l.email,l.contact,l.stage
        FROM ascension_actions a JOIN sales_pipeline_leads l
        ON l.id=a.lead_id AND l.owner_id=a.owner_id
        WHERE a.owner_id=? AND a.id=? AND a.status='approved'""",(owner,action_id)).fetchone()
    if not row:
        raise ValueError("An approved action for this account is required")
    lead_id,kind,business,email,contact,stage=row
    if stage in ("won", "lost"):\n        raise ValueError("Lead is closed")\n    if not email or not sales_pipeline.outreach_eligibility(c,owner,email):
        raise ValueError("Contact is not verified clear or is suppressed")
    if c.execute("SELECT 1 FROM ascension_followup_drafts WHERE owner_id=? AND action_id=?",(owner,action_id)).fetchone():
        raise ValueError("A draft already exists for this action")
    name=(contact or business).strip()
    subject="Following up with "+business
    if kind=="stalled_deal":
        body=f"Hello {name},\n\nI wanted to check whether you had any questions about our previous conversation. If it is useful, I would be happy to discuss next steps.\n\nBest regards"
    elif kind=="unanswered_reply":
        body=f"Hello {name},\n\nThank you for getting back to us. I wanted to follow up on our conversation. Please let me know what would be most helpful.\n\nBest regards"
    else:
        body=f"Hello {name},\n\nI wanted to check whether our previous discussion is still relevant to your business. No pressure if the timing is not right.\n\nBest regards"
    ident=secrets.token_hex(12)
    now=int(time.time())
    c.execute("INSERT INTO ascension_followup_drafts VALUES (?,?,?,?,?,?,?,?,?,?)",
        (ident,owner,action_id,lead_id,email.strip().lower(),subject,body,"draft",now,now))
    return ident

def revise(c,owner,draft_id,subject,body):
    setup(c)
    subject=subject.strip()
    body=body.strip()
    if not (1<=len(subject)<=180 and 1<=len(body)<=5000):
        raise ValueError("Subject or body length is invalid")
    row=c.execute("SELECT recipient,status FROM ascension_followup_drafts WHERE id=? AND owner_id=?",(draft_id,owner)).fetchone()
    if not row or row[1]!="draft":
        raise ValueError("Editable draft not found")
    ready, reason = draft_readiness(c, owner, draft_id)
    if not ready:
        raise ValueError(reason)
    c.execute("UPDATE ascension_followup_drafts SET subject=?,body=?,updated_at=? WHERE id=? AND owner_id=?",
              (subject,body,int(time.time()),draft_id,owner))

def dashboard(c,owner,csrf):
    setup(c)
    approved=c.execute("""SELECT a.id,l.business,l.email FROM ascension_actions a
        JOIN sales_pipeline_leads l ON l.id=a.lead_id AND l.owner_id=a.owner_id
        WHERE a.owner_id=? AND a.status='approved' AND NOT EXISTS
        (SELECT 1 FROM ascension_followup_drafts d WHERE d.owner_id=a.owner_id AND d.action_id=a.id)
        ORDER BY a.updated_at DESC LIMIT 100""",(owner,)).fetchall()
    drafts=c.execute("""SELECT id,recipient,subject,body FROM ascension_followup_drafts
        WHERE owner_id=? AND status='draft' ORDER BY updated_at DESC LIMIT 100""",(owner,)).fetchall()
    parts=['<section class="hero"><h1>Follow-up Studio</h1><p>Prepare and edit outreach drafts. Nothing is sent from this workspace. Verify the conversation and contact eligibility before using a draft elsewhere.</p></section>','<section class="panel"><h2>Approved actions</h2>']
    for action_id,business,email in approved:
        eligible=bool(email and sales_pipeline.outreach_eligibility(c,owner,email))
        parts.append('<article><strong>'+esc(business)+'</strong><p>Contact eligibility: '+('verified clear' if eligible else 'blocked or unverified')+'</p>')
        if eligible:
            parts.append('<form method="post" action="/ascension-followup-prepare"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="action_id" value="'+esc(action_id)+'"><button type="submit">Prepare draft</button></form>')
        parts.append('</article>')
    if not approved:parts.append('<p>No approved actions awaiting a draft.</p>')
    parts.append('</section><section class="panel"><h2>Editable drafts</h2>')
    for ident,recipient,subject,body in drafts:
        eligible, reason = draft_readiness(c, owner, ident)
        parts.append('<article><p>Recipient: '+esc(recipient)+' — '+esc(reason)+'</p>')
        parts.append('<form method="post" action="/ascension-followup-revise"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="draft_id" value="'+esc(ident)+'"><label>Subject<input name="subject" maxlength="180" value="'+esc(subject)+'" required></label><label>Message<textarea name="body" maxlength="5000" rows="8" required>'+esc(body)+'</textarea></label><button type="submit"'+('' if eligible else ' disabled')+'>Save draft</button></form></article>')
    if not drafts:parts.append('<p>No drafts yet.</p>')
    parts.append('</section>')
    return ''.join(parts)
