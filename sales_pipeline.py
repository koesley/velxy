"""VELXTRIA manual sales pipeline. Scoped per signed-in user; no automatic outreach."""
import html
import secrets
import time
import outreach_deliverability

STAGES = ("new", "contacted", "replied", "meeting", "proposal", "won", "lost")
def esc(v):
    return html.escape(str(v), quote=True)
def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS sales_pipeline_leads (
        id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL, business TEXT NOT NULL,
        contact TEXT NOT NULL, email TEXT NOT NULL, industry TEXT NOT NULL,
        stage TEXT NOT NULL, estimated_value INTEGER NOT NULL DEFAULT 0,
        notes TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS sales_pipeline_owner ON sales_pipeline_leads(owner_id, updated_at)")
    c.execute("CREATE TABLE IF NOT EXISTS outreach_suppression (owner_id INTEGER NOT NULL,email TEXT NOT NULL,status TEXT NOT NULL,reason TEXT NOT NULL,updated_at INTEGER NOT NULL,PRIMARY KEY(owner_id,email))")
    c.execute("CREATE TABLE IF NOT EXISTS outreach_suppression_events (owner_id INTEGER NOT NULL,email TEXT NOT NULL,status TEXT NOT NULL,reason TEXT NOT NULL,created_at INTEGER NOT NULL)")
def set_suppression(c, owner, email, status, reason=""):
    setup(c)
    email=email.strip().lower()
    if not outreach_deliverability.valid_email(email):
        raise ValueError("Valid email required")
    allowed=("suppress_permanent","suppress_rejected","hold_for_verification","verified_clear","do_not_contact")
    if status not in allowed:
        raise ValueError("Invalid status")
    current=c.execute("SELECT status FROM outreach_suppression WHERE owner_id=? AND email=?",(owner,email)).fetchone()
    if current and current[0]=="do_not_contact" and status!="do_not_contact":
        raise ValueError("Opted-out contact cannot be reactivated")
    if status=="verified_clear" and (not reason.strip() or len(reason.strip())<12):
        raise ValueError("Verification requires evidence of the current public business email source")
    c.execute("""INSERT INTO outreach_suppression(owner_id,email,status,reason,updated_at)
    VALUES (?,?,?,?,?) ON CONFLICT(owner_id,email) DO UPDATE SET
    status=excluded.status,reason=excluded.reason,updated_at=excluded.updated_at""",
    (owner,email,status,reason[:500],int(time.time())))
    c.execute("""INSERT INTO outreach_suppression_events(owner_id,email,status,reason,created_at)
                 VALUES (?,?,?,?,?)""",(owner,email,status,reason[:500],int(time.time())))

def import_bounce_lines(c, owner, raw):
    """Import pasted recipient|bounce-error lines, no automatic clearance.

    Each line must contain an explicit email and its delivery diagnostic.
    Unknown errors are held for review, never marked verified.
    """
    if len(raw)>30000:
        raise ValueError("Import exceeds 30,000 characters")
    entries=[line.strip() for line in raw.splitlines() if line.strip()]
    if len(entries)>150:
        raise ValueError("Maximum 150 bounce entries per import")
    # Validate every line before changing the database.
    parsed=[]
    for line in entries:
        if "|" not in line:
            raise ValueError("Each line must be email | bounce error")
        email, diagnostic=line.split("|",1)
        email=email.strip().lower()
        if not outreach_deliverability.valid_email(email) or not diagnostic.strip():
            raise ValueError("Invalid recipient or missing bounce error")
        status=outreach_deliverability.classify_bounce(diagnostic)
        if status=="needs_manual_review":
            status="hold_for_verification"
        parsed.append((email,status,diagnostic.strip()[:500]))
    # Never weaken existing permanent suppressions or opt-outs on import.
    protected={"do_not_contact","suppress_permanent","suppress_rejected"}
    for email,status,reason in parsed:
        existing=c.execute("SELECT status FROM outreach_suppression WHERE owner_id=? AND email=?",(owner,email)).fetchone()
        if existing and existing[0] in protected:
            continue
        if existing and existing[0]=="verified_clear" and status=="hold_for_verification":
            continue
        set_suppression(c,owner,email,status,reason)
    return len(parsed)

def import_gmail_notices(c, owner, raw):
    """Import pasted Gmail delivery notices with explicit recipient and error.

    Notices must be separated by a line containing exactly ===.
    Does not connect to Gmail or send messages.
    """
    import re
    if len(raw)>60000:
        raise ValueError("Gmail notice import too large")
    notices=[part.strip() for part in re.split(r"(?m)^===$",raw) if part.strip()]
    if len(notices)>100:
        raise ValueError("Maximum 100 notices")
    parsed=[]
    for notice in notices:
        match=re.search(r"(?:message (?:to|wasn't delivered to)|message couldn't be delivered to|delivering your message to)\s+([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})",notice,re.I)
        if not match:
            raise ValueError("Missing recognizable Gmail recipient; use email | error import instead")
        email=match.group(1).lower()
        status=outreach_deliverability.classify_bounce(notice)
        if status=="needs_manual_review":
            status="hold_for_verification"
        parsed.append((email,status,notice[:500]))
    protected={"do_not_contact","suppress_permanent","suppress_rejected"}
    for email,status,reason in parsed:
        existing=c.execute("SELECT status FROM outreach_suppression WHERE owner_id=? AND email=?",(owner,email)).fetchone()
        if existing and existing[0] in protected:
            continue
        set_suppression(c,owner,email,status,reason)
    return len(parsed)

def outreach_eligibility(c, owner, email):
    setup(c)
    email=email.strip().lower()
    row=c.execute("SELECT status FROM outreach_suppression WHERE owner_id=? AND email=?",(owner,email)).fetchone()
    return bool(row and outreach_deliverability.eligible_for_new_outreach(email,{email:row[0]}))

def save(c, owner, data):
    setup(c)
    business = data.get("business","").strip()
    if not 2 <= len(business) <= 120:
        raise ValueError("Business name must be 2–120 characters")
    stage = data.get("stage","new")
    if stage not in STAGES:
        raise ValueError("Invalid stage")
    try:
        value = int(data.get("value","0") or "0")
    except ValueError:
        raise ValueError("Estimated value must be a whole number")
    if not 0 <= value <= 100000000:
        raise ValueError("Estimated value out of range")
    contact=data.get("contact","").strip()[:120]
    email=data.get("email","").strip()[:254]
    industry=data.get("industry","").strip()[:80]
    notes=data.get("notes","").strip()[:1000]
    if email and ("@" not in email or "\n" in email):
        raise ValueError("Invalid email")
    lead_id=data.get("lead_id","").strip()
    if lead_id:
        result=c.execute("""UPDATE sales_pipeline_leads SET business=?,contact=?,email=?,industry=?,stage=?,estimated_value=?,notes=?,updated_at=?
                            WHERE id=? AND owner_id=?""",
                         (business,contact,email,industry,stage,value,notes,int(time.time()),lead_id,owner))
        if result.rowcount != 1:
            raise ValueError("Lead not found")
        return lead_id
    lead_id=secrets.token_hex(12)
    now=int(time.time())
    c.execute("INSERT INTO sales_pipeline_leads VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (lead_id,owner,business,contact,email,industry,stage,value,notes,now,now))
    return lead_id
def lead_quality_review(c, owner):
    """Owner-scoped, read-only data-quality summary; no outreach is initiated."""
    setup(c)
    rows = c.execute("""SELECT id, business, contact, email, industry, stage, estimated_value
        FROM sales_pipeline_leads WHERE owner_id=?""", (owner,)).fetchall()
    missing_contact = 0
    missing_industry = 0
    missing_value = 0
    duplicate_groups = {}
    for lead_id, business, contact, email, industry, stage, value in rows:
        if stage in ("won", "lost"):
            continue
        if not contact.strip() and not email.strip():
            missing_contact += 1
        if not industry.strip():
            missing_industry += 1
        if value == 0:
            missing_value += 1
        # Review candidates only; never merge automatically.
        key = (business.strip().casefold(), email.strip().casefold())
        if key[0] and key[1]:
            duplicate_groups[key] = duplicate_groups.get(key, 0) + 1
    duplicate_extras = sum(n - 1 for n in duplicate_groups.values() if n > 1)
    return {
        "open_leads": sum(r[5] not in ("won", "lost") for r in rows),
        "missing_contact": missing_contact,
        "missing_industry": missing_industry,
        "missing_value": missing_value,
        "potential_duplicates": duplicate_extras,
    }

def lead_quality_html(c, owner):
    d = lead_quality_review(c, owner)
    return ('<section class="panel"><h2>Lead data quality</h2>'
            '<p>Open leads reviewed: ' + str(d["open_leads"]) +
            ' · Missing contact details: ' + str(d["missing_contact"]) +
            ' · Missing industry: ' + str(d["missing_industry"]) +
            ' · Missing estimated value: ' + str(d["missing_value"]) +
            ' · Possible duplicate records: ' + str(d["potential_duplicates"]) + '</p>'
            '<p>Review and correct records using Edit lead below. Duplicates are '
            'suggestions based on matching business and email, not confirmed matches. '
            'No contacts are merged or messaged automatically.</p></section>')

def dashboard(c, owner, csrf):
    setup(c)
    rows=c.execute("""SELECT id,business,contact,email,industry,stage,estimated_value,notes
                      FROM sales_pipeline_leads WHERE owner_id=? ORDER BY updated_at DESC LIMIT 200""",(owner,)).fetchall()
    won=sum(r[6] for r in rows if r[5]=="won")
    potential=sum(r[6] for r in rows if r[5] not in ("won","lost"))
    counts={stage:sum(r[5]==stage for r in rows) for stage in STAGES}
    # Only independently verified mainnet settlement records count as received
    # payments. These are account-level payments, NOT attributed to leads.
    # Do not use the manually selected "won" stage as payment evidence.
    verified_count=0
    verified_cents=0
    try:
        payments=c.execute("""SELECT o.invoice_id FROM btcpay_orders o
            JOIN subscriptions s ON s.user_id=o.user_id
            WHERE o.user_id=? AND o.network='mainnet' AND o.status='settled'
              AND o.settled_at>0 AND o.invoice_id IS NOT NULL
              AND s.verification_source='btcpay_mainnet_verified'
            ORDER BY o.settled_at DESC""",(owner,)).fetchall()
        # Current subscription verification can only attest to its latest
        # source invoice. Older orders may have been settled but should not
        # be represented as individually verified by this join alone.
        source=c.execute("""SELECT source_reference FROM subscriptions
            WHERE user_id=? AND verification_source='btcpay_mainnet_verified'
            AND verified_at>0""",(owner,)).fetchone()
        verified_count=sum(1 for p in payments if source and p[0] == source[0])
        verified_cents=verified_count*4900
    except Exception:
        pass  # No payment schema yet, or inaccessible: show no verified evidence.
    parts=['<section class="hero"><h1>Sales Pipeline</h1><p>Track outreach, conversations, meetings and deals. Values are manual estimates, not verified revenue.</p></section>',
           '<section class="panel"><h2>Pipeline overview</h2><p>'+str(len(rows))+' recent leads · '+str(counts["replied"])+' replied · '+str(counts["meeting"])+' meetings · '+str(counts["won"])+' won</p><p>Estimated open opportunities: $'+str(potential)+' · Self-reported won deals: $'+str(won)+'</p></section>']
    parts.append('<section class="panel"><h2>Payment evidence</h2><p>Currently evidenced mainnet PRO payments: '+str(verified_count)+' · $'+format(verified_cents/100,'.2f')+' USD</p><p>This conservative count includes only the current subscription invoice linked to a settled order. It is not total lifetime revenue, a bank balance, or attribution to any lead. Earlier payments and refunds require separate reconciliation.</p></section>')
    def form(lead=None):
        lead=lead or ("","","","","","new",0,"")
        fields=[("business","Business",lead[1]),("contact","Contact",lead[2]),("email","Email",lead[3]),("industry","Industry",lead[4]),("value","Estimated deal value (USD)",lead[6])]
        p='<form method="post" action="/sales-pipeline"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><input type="hidden" name="lead_id" value="'+esc(lead[0])+'">'
        for key,label,value in fields:
            p+='<label>'+esc(label)+'<input name="'+key+'" maxlength="254" value="'+esc(value)+'"></label>'
        p+='<label>Stage<select name="stage">'+''.join('<option value="'+stage+'"'+(' selected' if stage==lead[5] else '')+'>'+stage.title()+'</option>' for stage in STAGES)+'</select></label>'
        p+='<label>Notes<textarea name="notes" maxlength="1000">'+esc(lead[7])+'</textarea></label><button type="submit">Save lead</button></form>'
        return p
    parts.append(lead_quality_html(c, owner))
    parts.append('<section class="panel"><h2>Add a lead</h2>'+form()+'</section>')
    parts.append('<section class="panel"><h2>Contact delivery safety</h2><p>All addresses are held by default until independently verified. This page never sends email.</p><form method="post" action="/outreach-suppression"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><label>Email<input name="email" required></label><label>Status<select name="status">'+''.join('<option value="'+x+'">'+esc(x.replace('_',' ').title())+'</option>' for x in ("hold_for_verification","suppress_permanent","suppress_rejected","do_not_contact","verified_clear"))+'</select></label><label>Evidence<input name="reason" maxlength="500"></label><button type="submit">Save status</button></form></section>')
    parts.append('<section class="panel"><h2>Import Gmail bounce reports</h2><p>Paste one recipient and its exact error per line, separated by |. Example: info@example.com | 550 5.1.1 User does not exist. No emails are sent.</p><form method="post" action="/outreach-bounce-import"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><textarea name="bounce_lines" rows="7" maxlength="30000" required></textarea><button type="submit">Import bounce statuses</button></form></section>')
    parts.append('<section class="panel"><h2>Paste Gmail delivery notices</h2><p>Paste the full text of each Gmail bounce notice, separated by a line containing ===. No Gmail access or email sending occurs here.</p><form method="post" action="/outreach-gmail-import"><input type="hidden" name="csrf" value="'+esc(csrf)+'"><textarea name="notices" rows="8" maxlength="60000" required></textarea><button type="submit">Review and import failures</button></form></section>')
    summary=dict(c.execute("SELECT status,COUNT(*) FROM outreach_suppression WHERE owner_id=? GROUP BY status",(owner,)).fetchall())
    held=summary.get("hold_for_verification",0)
    blocked=sum(summary.get(x,0) for x in ("suppress_permanent","suppress_rejected","do_not_contact"))
    cleared=summary.get("verified_clear",0)
    parts.append('<section class="panel"><h2>Outreach safety command center</h2><p>'+str(blocked)+' suppressed · '+str(held)+' held for verification · '+str(cleared)+' manually verified</p><p>Verified means contact evidence recorded, not guaranteed inbox delivery. No automatic campaign sender is enabled.</p></section>')
    statuses=c.execute("SELECT email,status FROM outreach_suppression WHERE owner_id=? ORDER BY updated_at DESC LIMIT 100",(owner,)).fetchall()
    parts.append('<section class="panel"><h2>Delivery status register</h2>'+''.join('<p>'+esc(email)+' — '+esc(status)+'</p>' for email,status in statuses)+'</section>')

    for lead in rows:
        parts.append('<section class="panel"><h3>'+esc(lead[1])+'</h3><p>'+esc(lead[5].title())+' · $'+str(lead[6])+' estimated · '+esc(lead[2])+'</p><details><summary>Edit lead</summary>'+form(lead)+'</details></section>')
    return ''.join(parts)
