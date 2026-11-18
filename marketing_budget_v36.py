"""Human-controlled marketing budget scenarios with transparent historical ratios."""
import html
import time
import urllib.parse
from decimal import Decimal,InvalidOperation
import business_os_v59 as bos
import acquisition_intelligence_v35 as acquisition

def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS vx_marketing_budget36 (
      workspace_id TEXT NOT NULL,source TEXT NOT NULL,budget_cents INTEGER NOT NULL,
      updated_by INTEGER NOT NULL,updated_at INTEGER NOT NULL,
      PRIMARY KEY(workspace_id,source))""")

def cents(amount):
    try:
        value=Decimal(str(amount))
        if not value.is_finite() or value<0 or value>Decimal("1000000000") or value.as_tuple().exponent < -2:
            raise ValueError()
        return int(value*100)
    except (ValueError,InvalidOperation,TypeError):
        raise ValueError("Budget must be between $0 and $1 billion, with at most two decimals.")

def set_budget(c,uid,wid,source,amount):
    bos.core.access(c,uid,wid,write=True)
    bos.init(c)
    setup(c)
    source=str(source).strip()
    if not source or len(source)>100:raise ValueError("Invalid channel.")
    if not c.execute("SELECT 1 FROM bos59_leads WHERE workspace_id=? AND source=?",(wid,source)).fetchone():
        raise ValueError("Select an existing lead source in this workspace.")
    value=cents(amount)
    c.execute("""INSERT INTO vx_marketing_budget36 VALUES (?,?,?,?,?)
       ON CONFLICT(workspace_id,source) DO UPDATE SET
       budget_cents=excluded.budget_cents,updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
       (wid,source,value,uid,int(time.time())))

def analyze(c,uid,wid):
    bos.core.access(c,uid,wid)
    setup(c)
    history=acquisition.analyze(c,uid,wid)
    budgets=dict(c.execute("SELECT source,budget_cents FROM vx_marketing_budget36 WHERE workspace_id=?",(wid,)).fetchall())
    result=[]
    for row in history:
        budget=budgets.get(row["source"],0)
        historical_cpl=row["cost_per_lead_cents"]
        # Historical equivalence, not expected future leads. Never estimate from missing spend.
        equivalent=round(budget/historical_cpl,1) if budget and historical_cpl and historical_cpl>0 else None
        result.append({**row,"budget_cents":budget,"historical_lead_equivalent":equivalent})
    return {"channels":result,"total_budget_cents":sum(budgets.values()),
            "modeled_budget_cents":sum(r["budget_cents"] for r in result)}

def render(c,uid,wid,csrf):
    bos.core.access(c,uid,wid)
    bos.init(c)
    setup(c)
    result=analyze(c,uid,wid)
    e=lambda value:html.escape(str(value),quote=True)
    money=lambda value:"$"+format(Decimal(value)/100,",.2f")
    out=['<section class="panel"><h1>Marketing Budget Allocation Studio</h1>',
         '<p>Save proposed channel budgets without spending money or launching campaigns. '
         'Historical cost per lead is based on all recorded leads and acquisition costs, '
         'which may cover different periods. Historical lead equivalents are arithmetic '
         'comparisons, NOT forecasts, guaranteed customers, or ROI. '
         'A missing cost history is unknown, not zero.</p>',
         '<p>Saved allocation total: '+money(result["total_budget_cents"])+'</p></section>']
    if not result["channels"]:
        out.append('<section class="panel"><p>Add leads with acquisition sources to plan a budget.</p></section>')
    for row in result["channels"]:
        out.append('<section class="panel"><h2>'+e(row["source"])+'</h2>'
                   '<p>Recorded leads: '+str(row["leads"])+
                   ' · Historical recorded spend: '+(money(row["cost_cents"]) if row["cost_cents"] else "Unknown")+
                   ' · Historical cost per lead: '+(money(row["cost_per_lead_cents"]) if row["cost_per_lead_cents"] is not None else "N/A")+'</p>'
                   '<p>Saved proposed allocation: '+money(row["budget_cents"])+
                   ' · Historical lead equivalent: '+(str(row["historical_lead_equivalent"]) if row["historical_lead_equivalent"] is not None else "N/A")+'</p>')
        if row["leads"]:
            out.append('<form method="post" action="/marketing-budget">'
                       '<input type="hidden" name="csrf" value="'+e(csrf)+'">'
                       '<input type="hidden" name="workspace" value="'+e(wid)+'">'
                       '<input type="hidden" name="source" value="'+e(row["source"])+'">'
                       '<label>Proposed budget ($)<input name="amount" value="'+e(Decimal(row["budget_cents"])/100)+'" required></label>'
                       '<button>Save allocation</button></form>')
        out.append('</section>')
    return ''.join(out)
