"""Manual channel acquisition cost ledger and descriptive efficiency comparisons."""
import html
import secrets
import time
import urllib.parse
from decimal import Decimal, InvalidOperation
import business_os_v59 as bos
import revenue_attribution_v34 as attribution

def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS vx_acquisition_cost35 (
        id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,source TEXT NOT NULL,
        amount_cents INTEGER NOT NULL,note TEXT NOT NULL,created_by INTEGER NOT NULL,
        created INTEGER NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS vx_acquisition_cost35_scope ON vx_acquisition_cost35(workspace_id,source)")

def add(c,uid,wid,source,amount,note):
    bos.core.access(c,uid,wid,write=True)
    bos.init(c)
    setup(c)
    source=str(source).strip()
    note=str(note).strip()
    if not 1<=len(source)<=100 or len(note)>300:
        raise ValueError("Source must be 1–100 characters; note at most 300.")
    if not c.execute("SELECT 1 FROM bos59_leads WHERE workspace_id=? AND source=?",(wid,source)).fetchone():
        raise ValueError("Choose a lead source already used in this workspace.")
    try:
        value=Decimal(str(amount))
        if not value.is_finite() or value<=0 or value>Decimal("1000000000") or value.as_tuple().exponent < -2:
            raise ValueError()
    except (InvalidOperation,ValueError,TypeError):
        raise ValueError("Cost must be positive, up to $1 billion, with at most two decimals.")
    identifier=secrets.token_hex(12)
    c.execute("INSERT INTO vx_acquisition_cost35 VALUES (?,?,?,?,?,?,?)",
              (identifier,wid,source,int(value*100),note,uid,int(time.time())))
    return identifier

def analyze(c,uid,wid):
    bos.core.access(c,uid,wid)
    setup(c)
    sources=attribution.analyze(c,uid,wid)
    costs=dict(c.execute("SELECT source,SUM(amount_cents) FROM vx_acquisition_cost35 WHERE workspace_id=? GROUP BY source",(wid,)).fetchall())
    rows=[]
    for item in sources:
        cost=costs.pop(item["source"],0)
        won=item["won_leads"]
        leads=item["leads"]
        rows.append({**item,"cost_cents":cost,
                     "cost_per_lead_cents":round(cost/leads) if cost and leads else None,
                     "cost_per_won_lead_cents":round(cost/won) if cost and won else None,
                     "reported_payment_to_cost":round(item["reported_cents"]/cost,2) if cost else None})
    # Preserve spend even if its source label is no longer present in current lead data.
    for source,cost in costs.items():
        rows.append({"source":source,"leads":0,"won_leads":0,"reported_cents":0,
                     "cost_cents":cost,"cost_per_lead_cents":None,
                     "cost_per_won_lead_cents":None,"reported_payment_to_cost":None})
    return sorted(rows,key=lambda r:(-r["cost_cents"],r["source"]))


def review_channels(rows, minimum_leads=5):
    """Produce conservative, deterministic data-quality actions, never ROI claims."""
    if not isinstance(minimum_leads,int) or isinstance(minimum_leads,bool) or not 1<=minimum_leads<=100:
        raise ValueError("minimum_leads must be between 1 and 100")
    findings=[]
    for row in rows:
        source=str(row["source"])
        leads=int(row["leads"])
        won=int(row["won_leads"])
        cost=int(row["cost_cents"])
        tasks=int(row.get("tasks",0))
        completed=int(row.get("completed_tasks",0))
        if leads<0 or won<0 or won>leads or cost<0 or tasks<0 or completed<0 or completed>tasks:
            raise ValueError("Invalid acquisition summary")
        flags=[]
        if not leads and cost:
            flags.append("Spend recorded but no leads attributed; check source labels and dates")
        elif leads and not cost:
            flags.append("Leads recorded but no expense entries; cost is unknown")
        if leads and leads<minimum_leads:
            flags.append("Small lead sample; avoid drawing conversion conclusions")
        if leads>=minimum_leads and not won:
            flags.append("No won-marked leads; review follow-up and lead qualification")
        if tasks and completed<tasks:
            flags.append("Internal tasks remain incomplete; review the execution board")
        if not flags:
            flags.append("Review source records periodically; no action automatically taken")
        findings.append({"source":source,"leads":leads,"cost_cents":cost,
                         "flags":flags,"attention":int(bool(cost and not leads))*4+
                         int(bool(leads and not cost))*3+
                         int(bool(leads>=minimum_leads and not won))*2+
                         int(bool(tasks and completed<tasks))})
    return sorted(findings,key=lambda r:(-r["attention"],r["source"].casefold(),r["source"]))

def render_channel_review(rows,wid):
    """HTML for a manual source-quality review; all source names are escaped."""
    e=lambda v:html.escape(str(v),quote=True)
    link="/revenue-execution?w="+urllib.parse.quote(str(wid),safe="")
    out=['<section class="panel"><h2>Acquisition evidence review</h2>',
         '<p>Suggested checks use manually entered lead, task and expense records. '
         'They are not forecasts, verified acquisition costs, or automated budget decisions.</p>',
         '<p><a href="'+e(link)+'">Review internal sales tasks</a></p>']
    for item in review_channels(rows):
        out.append('<article><h3>'+e(item["source"])+'</h3><ul>')
        out.extend('<li>'+e(flag)+'</li>' for flag in item["flags"])
        out.append('</ul></article>')
    if not rows:out.append('<p>No source records available for review.</p>')
    out.append('</section>')
    return ''.join(out)

def render(c,uid,wid,csrf):
    bos.core.access(c,uid,wid)
    bos.init(c)
    setup(c)
    rows=analyze(c,uid,wid)
    e=lambda v:html.escape(str(v),quote=True)
    money=lambda cents:"$"+format(Decimal(cents)/100,",.2f")
    sources=[r["source"] for r in rows if r["leads"]]
    out=['<section class="panel"><h1>Customer Acquisition Intelligence</h1>',
         '<p>Compare manually recorded acquisition costs with existing lead sources. '
         'All-time source-level comparisons only: spending, leads and reported outcomes '
         'may refer to different periods. Reported payments are unverified and '
         'payment-to-cost ratios are NOT profit, ROI or causal marketing attribution. '
         'Missing spend entries mean cost is unknown, not free acquisition.</p></section>']
    if sources:
        out.append('<section class="panel"><h2>Record acquisition expense</h2>'
                   '<form method="post" action="/acquisition-intelligence">'
                   '<input type="hidden" name="csrf" value="'+e(csrf)+'">'
                   '<input type="hidden" name="workspace" value="'+e(wid)+'">'
                   '<label>Source<select name="source" required>'+
                   ''.join('<option value="'+e(source)+'">'+e(source)+'</option>' for source in sources)+
                   '</select></label><label>Expense amount<input name="amount" required></label>'
                   '<label>Expense description<input name="note" maxlength="300"></label>'
                   '<button>Record expense</button></form></section>')
    for row in rows:
        cost=row["cost_cents"]
        out.append('<section class="panel"><h2>'+e(row["source"])+'</h2><p>Leads: '+
                   str(row["leads"])+' · Won-marked: '+str(row["won_leads"])+
                   ' · Recorded acquisition spend: '+(money(cost) if cost else "Not recorded")+'</p>')
        if cost:
            out.append('<p>Cost per recorded lead: '+(money(row["cost_per_lead_cents"]) if row["cost_per_lead_cents"] is not None else "N/A")+
                       ' · Cost per won-marked lead: '+(money(row["cost_per_won_lead_cents"]) if row["cost_per_won_lead_cents"] is not None else "N/A")+'</p>'
                       '<p>Reported payment claims: '+money(row["reported_cents"])+
                       ' · Reported payment-to-cost ratio: '+(str(row["reported_payment_to_cost"])+"×" if row["reported_payment_to_cost"] is not None else "N/A")+'</p>')
        out.append('</section>')
    out.append(render_channel_review(rows,wid))
    if not rows:out.append('<section class="panel"><p>Add leads with sources to begin comparing acquisition channels.</p></section>')
    return ''.join(out)
