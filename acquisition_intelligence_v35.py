"""Manual channel acquisition cost ledger and descriptive efficiency comparisons."""
import html
import secrets
import time
from datetime import datetime, timezone
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
    if not 1<=len(source)<=100 or len(note)>300 or any(ord(ch)<32 or ord(ch)==127 for ch in source+note):
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


def expense_history(c,uid,wid,limit=20,now=None):
    """Read-only, tenant-scoped spend ledger and six UTC calendar-month totals.

    Month buckets use expense entry creation timestamps, not campaign service dates.
    Amounts are recorded costs, never verified payment or marketing ROI.
    """
    bos.core.access(c,uid,wid)
    setup(c)
    if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=100:
        raise ValueError("History limit must be between 1 and 100.")
    current=int(time.time() if now is None else now)
    current_month=datetime.fromtimestamp(current,timezone.utc)
    month_index=current_month.year*12+current_month.month-1
    first_index=month_index-5
    start_year,start_month=divmod(first_index,12)
    start=int(datetime(start_year,start_month+1,1,tzinfo=timezone.utc).timestamp())
    recent=c.execute(
        "SELECT id,source,amount_cents,note,created FROM vx_acquisition_cost35 "
        "WHERE workspace_id=? ORDER BY created DESC,id DESC LIMIT ?",
        (wid,limit)).fetchall()
    monthly=c.execute(
        "SELECT created,amount_cents FROM vx_acquisition_cost35 "
        "WHERE workspace_id=? AND created>=? AND created<=?",
        (wid,start,current)).fetchall()
    totals={i:0 for i in range(first_index,month_index+1)}
    for created,cents in monthly:
        try:
            dt=datetime.fromtimestamp(int(created),timezone.utc)
            index=dt.year*12+dt.month-1
            amount=int(cents)
            if index in totals and amount>=0:
                totals[index]+=amount
        except (ValueError,TypeError,OverflowError):
            continue
    months=[]
    for index,total in sorted(totals.items()):
        year,month=divmod(index,12)
        months.append({"month":f"{year:04d}-{month+1:02d}","cost_cents":total})
    return {"recent":[{"id":id_,"source":source,"amount_cents":cents,
                       "note":note,"created":created} for id_,source,cents,note,created in recent],
            "months":months,"display_limit":limit}

def render(c,uid,wid,csrf):
    bos.core.access(c,uid,wid)
    bos.init(c)
    setup(c)
    rows=analyze(c,uid,wid)
    history=expense_history(c,uid,wid)
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
    out.append('<section class="panel"><h2>Recorded spending by month (UTC)</h2>'
               '<p>Last six UTC calendar months, based on when expenses were entered, not '
               'when advertising occurred. These totals cannot be matched to lead conversion '
               'periods without dated lead attribution.</p><ul>')
    for month in history["months"]:
        out.append('<li>'+e(month["month"])+': '+money(month["cost_cents"])+'</li>')
    out.append('</ul></section>')
    out.append('<section class="panel"><h2>Recent acquisition expense entries</h2>'
               '<p>Latest 20 entries across this workspace; a read-only audit view. '
               'Amounts are manually entered, not independently verified.</p>')
    if history["recent"]:
        out.append('<ul>')
        for entry in history["recent"]:
            try:
                when=datetime.fromtimestamp(int(entry["created"]),timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            except (ValueError,TypeError,OverflowError):
                when="Date unavailable"
            out.append('<li>'+e(when)+' · '+e(entry["source"])+' · '+
                       money(entry["amount_cents"])+
                       (' · '+e(entry["note"]) if entry["note"] else '')+'</li>')
        out.append('</ul>')
    else:
        out.append('<p>No expenses have been recorded.</p>')
    out.append('</section>')
    if not rows:out.append('<section class="panel"><p>Add leads with sources to begin comparing acquisition channels.</p></section>')
    return ''.join(out)
