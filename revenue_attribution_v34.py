"""Descriptive lead-source and activity attribution, not causal ROI or verified revenue."""
import html
import urllib.parse
from collections import defaultdict
import business_os_v59 as bos
import customer_outcomes_v33 as outcomes
import revenue_execution_v29 as execution

def analyze(c,uid,wid):
    bos.core.access(c,uid,wid)
    bos.init(c)
    outcomes.setup(c)
    execution.setup(c)
    leads=c.execute("SELECT id,source,status FROM bos59_leads WHERE workspace_id=?",(wid,)).fetchall()
    source_by_lead={lid:(source.strip() if source and source.strip() else "Unspecified") for lid,source,status in leads}
    stats=defaultdict(lambda:{"leads":0,"won_leads":0,"reported_payments":0,"reported_cents":0,
                               "outcomes":0,"tasks":0,"completed_tasks":0})
    for lid,source,status in leads:
        name=source_by_lead[lid]
        stats[name]["leads"]+=1
        if status=="won":stats[name]["won_leads"]+=1
    for lid,kind,amount in c.execute("SELECT lead_id,kind,amount_cents FROM vx_outcomes33 WHERE workspace_id=?",(wid,)):
        if lid not in source_by_lead:continue
        bucket=stats[source_by_lead[lid]]
        bucket["outcomes"]+=1
        if kind=="payment_reported":
            bucket["reported_payments"]+=1
            bucket["reported_cents"]+=amount
    for lid,status in c.execute("SELECT lead_id,status FROM vx_revenue_tasks29 WHERE workspace_id=?",(wid,)):
        if lid not in source_by_lead:continue
        bucket=stats[source_by_lead[lid]]
        bucket["tasks"]+=1
        if status=="done":bucket["completed_tasks"]+=1
    return [{"source":source,**metrics,
             "won_share_pct":round(metrics["won_leads"]/metrics["leads"]*100,1) if metrics["leads"] else None}
            for source,metrics in sorted(stats.items(),key=lambda kv:(-kv[1]["reported_cents"],-kv[1]["won_leads"],kv[0]))]

def render(c,uid,wid):
    rows=analyze(c,uid,wid)
    e=lambda v:html.escape(str(v),quote=True)
    w=urllib.parse.quote(wid,safe="")
    money=lambda cents:"$"+format(cents/100,",.2f")
    out=['<section class="panel"><h1>Lead Source & Outcome Intelligence</h1>',
         '<p>Compare lead sources using recorded leads, manually marked won leads, '
         'self-reported payment claims, and internal task activity. '
         'Sources are lead-entered labels; multiple payment claims may belong to one lead. '
         'These are descriptive associations, not causal attribution, verified collected '
         'revenue, profit, or return on investment.</p>',
         '<p><a href="/customer-outcomes?w='+w+'">Customer outcomes</a> · '
         '<a href="/revenue-execution?w='+w+'">Execution tasks</a></p></section>']
    if not rows:return ''.join(out)+'<section class="panel"><p>No leads recorded in this workspace yet.</p></section>'
    for row in rows:
        out.append('<section class="panel"><h2>'+e(row["source"])+'</h2>'
                   '<p>Leads: '+str(row["leads"])+' · Won-marked leads: '+str(row["won_leads"])+
                   ' · Won share: '+str(row["won_share_pct"])+'%</p>'
                   '<p>Self-reported payment records: '+str(row["reported_payments"])+
                   ' · Reported amount: '+money(row["reported_cents"])+'</p>'
                   '<p>Recorded outcomes: '+str(row["outcomes"])+
                   ' · Tasks completed: '+str(row["completed_tasks"])+
                   ' / '+str(row["tasks"])+'</p></section>')
    return ''.join(out)
