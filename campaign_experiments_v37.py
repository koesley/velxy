"""Workspace-scoped, manual campaign experiment tracker; no campaign execution."""
import html
import secrets
import time
import urllib.parse
from datetime import date
from decimal import Decimal, InvalidOperation
import business_os_v59 as bos

STATES=("planned","running","completed","paused")

def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS vx_campaign37 (
        id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,owner_id INTEGER NOT NULL,
        name TEXT NOT NULL,source TEXT NOT NULL,hypothesis TEXT NOT NULL,
        start_date TEXT NOT NULL,end_date TEXT NOT NULL,status TEXT NOT NULL,
        spend_cents INTEGER NOT NULL,leads INTEGER NOT NULL,conversions INTEGER NOT NULL,
        notes TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS vx_campaign37_scope ON vx_campaign37(workspace_id,status)")

def amount_cents(value):
    try:
        v=Decimal(str(value))
        if not v.is_finite() or v<0 or v>Decimal("1000000000") or v.as_tuple().exponent < -2:raise ValueError()
        return int(v*100)
    except (ValueError,TypeError,InvalidOperation):
        raise ValueError("Spend must be nonnegative, at most $1 billion, with two decimals or fewer.")

def valid_date(value):
    try:
        if date.fromisoformat(value).isoformat()!=value:raise ValueError()
    except (ValueError,TypeError):raise ValueError("Invalid campaign date.")
    return value

def create(c,uid,wid,name,source,hypothesis,start,end):
    bos.core.access(c,uid,wid,write=True)
    bos.init(c);setup(c)
    name=str(name).strip();source=str(source).strip();hypothesis=str(hypothesis).strip()
    if not 1<=len(name)<=120 or not 1<=len(source)<=100 or not 1<=len(hypothesis)<=500:
        raise ValueError("Campaign name, source, and hypothesis are required.")
    if not c.execute("SELECT 1 FROM bos59_leads WHERE workspace_id=? AND source=?",(wid,source)).fetchone():
        raise ValueError("Choose an existing workspace lead source.")
    valid_date(start);valid_date(end)
    if end<start:raise ValueError("End date must not precede start date.")
    identifier=secrets.token_hex(12);now=int(time.time())
    c.execute("INSERT INTO vx_campaign37 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (identifier,wid,uid,name,source,hypothesis,start,end,"planned",0,0,0,"",now,now))
    return identifier

def update(c,uid,wid,identifier,status,spend,leads,conversions,notes):
    bos.core.access(c,uid,wid,write=True);setup(c)
    row=c.execute("SELECT owner_id FROM vx_campaign37 WHERE workspace_id=? AND id=?",(wid,identifier)).fetchone()
    if not row or row[0]!=uid:raise ValueError("Only the campaign owner may update this experiment.")
    if status not in STATES:raise ValueError("Invalid campaign state.")
    try:
        leads=int(leads);conversions=int(conversions)
        if str(leads)!=str(leads) or leads<0 or conversions<0 or conversions>leads or leads>1000000000:raise ValueError()
    except (TypeError,ValueError):raise ValueError("Leads and conversions must be valid nonnegative counts; conversions cannot exceed leads.")
    notes=str(notes).strip()
    if len(notes)>500:raise ValueError("Notes must be at most 500 characters.")
    c.execute("""UPDATE vx_campaign37 SET status=?,spend_cents=?,leads=?,conversions=?,
        notes=?,updated=? WHERE workspace_id=? AND id=?""",
        (status,amount_cents(spend),leads,conversions,notes,int(time.time()),wid,identifier))

def analyze(c,uid,wid):
    bos.core.access(c,uid,wid);setup(c)
    rows=c.execute("""SELECT id,owner_id,name,source,hypothesis,start_date,end_date,status,
        spend_cents,leads,conversions,notes FROM vx_campaign37 WHERE workspace_id=?
        ORDER BY created DESC LIMIT 150""",(wid,)).fetchall()
    return [{"id":r[0],"owner":r[1],"name":r[2],"source":r[3],"hypothesis":r[4],
             "start":r[5],"end":r[6],"status":r[7],"spend_cents":r[8],
             "leads":r[9],"conversions":r[10],"notes":r[11],
             "cost_per_lead_cents":round(r[8]/r[9]) if r[9] else None,
             "conversion_pct":round(r[10]/r[9]*100,1) if r[9] else None} for r in rows]

def render(c,uid,wid,csrf):
    bos.core.access(c,uid,wid);bos.init(c);setup(c)
    e=lambda v:html.escape(str(v),quote=True)
    money=lambda v:"$"+format(Decimal(v)/100,",.2f")
    sources=[r[0] for r in c.execute("SELECT DISTINCT source FROM bos59_leads WHERE workspace_id=? AND source IS NOT NULL AND TRIM(source)!='' ORDER BY source",(wid,))]
    rows=analyze(c,uid,wid)
    out=['<section class="panel"><h1>Campaign Experiment Lab</h1><p>Plan and manually track individual marketing experiments. '
         'Spend, leads and conversions are manually entered, not verified or automatically linked to customers. '
         'Campaigns are not launched here. Conversion definitions are supplied by the user; '
         'results are descriptive and do not prove causation or ROI.</p></section>']
    if sources:
        out.append('<section class="panel"><h2>Create campaign experiment</h2><form method="post" action="/campaign-experiments">'
                   '<input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'">'
                   '<input type="hidden" name="action" value="create">'
                   '<label>Campaign name<input name="name" maxlength="120" required></label>'
                   '<label>Channel<select name="source">'+''.join('<option value="'+e(x)+'">'+e(x)+'</option>' for x in sources)+'</select></label>'
                   '<label>Hypothesis<textarea name="hypothesis" maxlength="500" required></textarea></label>'
                   '<label>Start date<input type="date" name="start" required></label>'
                   '<label>End date<input type="date" name="end" required></label><button>Create experiment</button></form></section>')
    for r in rows:
        out.append('<section class="panel"><h2>'+e(r["name"])+'</h2><p>'+e(r["source"])+' · '+e(r["status"])+
                   ' · '+e(r["start"])+' to '+e(r["end"])+'</p><p>Hypothesis: '+e(r["hypothesis"])+'</p>'
                   '<p>Recorded spend: '+money(r["spend_cents"])+' · Leads: '+str(r["leads"])+
                   ' · Conversions: '+str(r["conversions"])+'</p><p>Cost per recorded lead: '+
                   (money(r["cost_per_lead_cents"]) if r["cost_per_lead_cents"] is not None else "N/A")+
                   ' · Recorded conversion share: '+(str(r["conversion_pct"])+"%" if r["conversion_pct"] is not None else "N/A")+
                   '</p><p>Notes: '+e(r["notes"] or "None")+'</p>')
        if r["owner"]==uid:
            out.append('<form method="post" action="/campaign-experiments">'
                       '<input type="hidden" name="csrf" value="'+e(csrf)+'"><input type="hidden" name="workspace" value="'+e(wid)+'">'
                       '<input type="hidden" name="action" value="update"><input type="hidden" name="id" value="'+e(r["id"])+'">'
                       '<label>Status<select name="status">'+''.join('<option value="'+x+'"'+(' selected' if r["status"]==x else '')+'>'+x+'</option>' for x in STATES)+'</select></label>'
                       '<label>Recorded spend ($)<input name="spend" value="'+e(Decimal(r["spend_cents"])/100)+'" required></label>'
                       '<label>Recorded leads<input name="leads" type="number" min="0" value="'+str(r["leads"])+'" required></label>'
                       '<label>Recorded conversions<input name="conversions" type="number" min="0" value="'+str(r["conversions"])+'" required></label>'
                       '<label>Experiment notes<textarea name="notes" maxlength="500">'+e(r["notes"])+'</textarea></label>'
                       '<button>Save experiment results</button></form>')
        out.append('</section>')
    return ''.join(out)
