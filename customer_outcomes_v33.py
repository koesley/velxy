"""Workspace-scoped customer outcome evidence ledger. Manual claims, never verified cash."""
import html
import secrets
import time
import urllib.parse
from decimal import Decimal, InvalidOperation
import business_os_v59 as bos

KINDS=("payment_reported","customer_retained","appointment_booked","deal_won","other")
def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS vx_outcomes33 (
        id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,lead_id TEXT NOT NULL,
        kind TEXT NOT NULL,amount_cents INTEGER NOT NULL,description TEXT NOT NULL,
        evidence_ref TEXT NOT NULL,created_by INTEGER NOT NULL,created INTEGER NOT NULL,
        review_status TEXT NOT NULL,reviewed_by INTEGER,reviewed_at INTEGER)""")
    c.execute("CREATE INDEX IF NOT EXISTS vx_outcomes33_scope ON vx_outcomes33(workspace_id,created)")

def add(c,uid,wid,lead_id,kind,amount,description,evidence):
    bos.core.access(c,uid,wid,write=True)
    bos.init(c)
    setup(c)
    if kind not in KINDS:raise ValueError("Invalid outcome category.")
    description=str(description).strip()
    evidence=str(evidence).strip()
    if not 1<=len(description)<=500 or len(evidence)>500:
        raise ValueError("Description must be 1–500 characters and evidence reference at most 500.")
    try:
        value=Decimal(str(amount))
        if not value.is_finite() or value<0 or value>Decimal("1000000000") or value.as_tuple().exponent < -2:
            raise ValueError()
    except (InvalidOperation,ValueError,TypeError):
        raise ValueError("Amount must be a nonnegative value up to $1 billion with at most 2 decimals.")
    if kind!="payment_reported" and value!=0:
        raise ValueError("Only reported payments can have a monetary amount.")
    if not c.execute("SELECT 1 FROM bos59_leads WHERE workspace_id=? AND id=?",(wid,lead_id)).fetchone():
        raise ValueError("Select a lead belonging to this workspace.")
    identifier=secrets.token_hex(12)
    c.execute("INSERT INTO vx_outcomes33 VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
              (identifier,wid,lead_id,kind,int(value*100),description,evidence,uid,int(time.time()),"unreviewed",None,None))
    return identifier

def review(c,uid,wid,identifier):
    bos.core.access(c,uid,wid,write=True)
    setup(c)
    row=c.execute("SELECT created_by,review_status FROM vx_outcomes33 WHERE workspace_id=? AND id=?",(wid,identifier)).fetchone()
    if not row:raise ValueError("Outcome record not found.")
    if row[0]==uid:raise ValueError("A different authorized member must review this claim.")
    if row[1]!="unreviewed":raise ValueError("This claim has already been reviewed.")
    c.execute("UPDATE vx_outcomes33 SET review_status='internally_reviewed',reviewed_by=?,reviewed_at=? WHERE workspace_id=? AND id=?",
              (uid,int(time.time()),wid,identifier))

def snapshot(c,uid,wid):
    bos.core.access(c,uid,wid)
    setup(c)
    rows=c.execute("SELECT kind,amount_cents,review_status FROM vx_outcomes33 WHERE workspace_id=?",(wid,)).fetchall()
    return {"records":len(rows),
            "reported_payment_cents":sum(amount for kind,amount,status in rows if kind=="payment_reported"),
            "internally_reviewed":sum(status=="internally_reviewed" for kind,amount,status in rows),
            "unreviewed":sum(status=="unreviewed" for kind,amount,status in rows)}

def render(c,uid,wid,csrf):
    bos.core.access(c,uid,wid)
    bos.init(c)
    setup(c)
    e=lambda v:html.escape(str(v),quote=True)
    w=urllib.parse.quote(wid,safe="")
    data=snapshot(c,uid,wid)
    leads=c.execute("SELECT id,name FROM bos59_leads WHERE workspace_id=? ORDER BY updated DESC LIMIT 300",(wid,)).fetchall()
    rows=c.execute("""SELECT o.id,l.name,o.kind,o.amount_cents,o.description,o.evidence_ref,
        o.review_status,o.created_by FROM vx_outcomes33 o JOIN bos59_leads l
        ON l.id=o.lead_id AND l.workspace_id=o.workspace_id
        WHERE o.workspace_id=? ORDER BY o.created DESC LIMIT 100""",(wid,)).fetchall()
    money=lambda cents:"$"+format(Decimal(cents)/100,",.2f")
    out=['<section class="panel"><h1>Customer Outcomes Ledger</h1>',
         '<p>Record customer outcomes and reported payments with optional evidence references. '
         'All amounts are self-reported, NOT bank-verified or confirmed collected revenue. '
         'Internal review is a second-person acknowledgement, NOT financial verification.</p>',
         '<p>Records: '+str(data["records"])+' · Reported payments: '+money(data["reported_payment_cents"])+
         ' · Internally reviewed: '+str(data["internally_reviewed"])+
         ' · Awaiting review: '+str(data["unreviewed"])+'</p></section>']
    if leads:
        out.append('<section class="panel"><h2>Record customer outcome</h2><form method="post" action="/customer-outcomes">'
                   '<input type="hidden" name="csrf" value="'+e(csrf)+'">'
                   '<input type="hidden" name="workspace" value="'+e(wid)+'">'
                   '<input type="hidden" name="action" value="add">'
                   '<label>Lead<select name="lead" required>'+
                   ''.join('<option value="'+e(lid)+'">'+e(name)+'</option>' for lid,name in leads)+'</select></label>'
                   '<label>Outcome<select name="kind">'+''.join('<option value="'+e(k)+'">'+e(k.replace("_"," ").title())+'</option>' for k in KINDS)+'</select></label>'
                   '<label>Reported payment amount (0 for other outcomes)<input name="amount" value="0" required></label>'
                   '<label>Outcome details<textarea name="description" maxlength="500" required></textarea></label>'
                   '<label>Evidence reference (optional)<input name="evidence" maxlength="500"></label>'
                   '<button>Record outcome</button></form></section>')
    for identifier,lead,kind,cents,description,evidence,status,creator in rows:
        out.append('<section class="panel"><h3>'+e(lead)+' — '+e(kind.replace("_"," ").title())+
                   '</h3><p>Reported amount: '+money(cents)+' · '+e(status.replace("_"," "))+
                   '</p><p>'+e(description)+'</p><p>Evidence reference: '+e(evidence or "Not provided")+'</p>')
        if creator!=uid and status=="unreviewed":
            out.append('<form method="post" action="/customer-outcomes">'
                       '<input type="hidden" name="csrf" value="'+e(csrf)+'">'
                       '<input type="hidden" name="workspace" value="'+e(wid)+'">'
                       '<input type="hidden" name="action" value="review">'
                       '<input type="hidden" name="id" value="'+e(identifier)+'">'
                       '<button>Acknowledge internal review</button></form>')
        out.append('</section>')
    return ''.join(out)
