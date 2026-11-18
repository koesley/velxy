"""Versioned manual campaign outcome snapshots after approved optimizations."""
import html
import secrets
import time
import urllib.parse
from decimal import Decimal,InvalidOperation
import business_os_v59 as bos
import campaign_optimization_v39 as optimization

def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS vx_impact40 (
        id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,proposal_id TEXT NOT NULL,
        author_id INTEGER NOT NULL,period_start TEXT NOT NULL,period_end TEXT NOT NULL,
        spend_cents INTEGER NOT NULL,leads INTEGER NOT NULL,conversions INTEGER NOT NULL,
        evidence TEXT NOT NULL,created INTEGER NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS vx_impact40_scope ON vx_impact40(workspace_id,proposal_id)")

def record(c,uid,wid,proposal_id,start,end,spend,leads,conversions,evidence):
    bos.core.access(c,uid,wid,write=True)
    setup(c);optimization.setup(c)
    row=c.execute("SELECT status FROM vx_optimization39 WHERE workspace_id=? AND id=?",(wid,proposal_id)).fetchone()
    if not row or row[0]!="implemented":raise ValueError("Only implemented optimization proposals can receive follow-up results.")
    from datetime import date
    try:
        if date.fromisoformat(start).isoformat()!=start or date.fromisoformat(end).isoformat()!=end or end<start:
            raise ValueError()
    except (ValueError,TypeError):raise ValueError("Enter a valid follow-up date range.")
    try:
        leads=int(leads);conversions=int(conversions)
        if leads<0 or conversions<0 or conversions>leads or leads>1000000000:raise ValueError()
    except (ValueError,TypeError):raise ValueError("Invalid lead/conversion counts.")
    evidence=str(evidence).strip()
    if not 1<=len(evidence)<=500:raise ValueError("Provide an evidence or data-source note (maximum 500 characters).")
    identifier=secrets.token_hex(12)
    c.execute("INSERT INTO vx_impact40 VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (identifier,wid,proposal_id,uid,start,end,optimization.money(spend),leads,conversions,evidence,int(time.time())))
    return identifier

def analyze(c,uid,wid):
    bos.core.access(c,uid,wid);setup(c);optimization.setup(c)
    rows=c.execute("""SELECT p.id,p.revision_name,p.status,p.estimated_budget_cents,
      x.id,x.period_start,x.period_end,x.spend_cents,x.leads,x.conversions,x.evidence,x.created,
      b.name,b.spend_cents,b.leads,b.conversions
      FROM vx_optimization39 p
      JOIN vx_campaign37 b ON b.id=p.base_campaign_id AND b.workspace_id=p.workspace_id
      LEFT JOIN vx_impact40 x ON x.proposal_id=p.id AND x.workspace_id=p.workspace_id
      WHERE p.workspace_id=? AND p.status='implemented'
      ORDER BY p.created DESC,x.created DESC LIMIT 200""",(wid,)).fetchall()
    out=[]
    for r in rows:
        pid,pname,status,budget,sid,start,end,spend,leads,conv,evidence,created,bname,bspend,bleads,bconv=r
        baseline_rate=round(bconv/bleads*100,1) if bleads else None
        follow_rate=round(conv/leads*100,1) if sid and leads else None
        out.append({"proposal_id":pid,"proposal":pname,"campaign":bname,
                    "snapshot_id":sid,"start":start,"end":end,"spend_cents":spend,
                    "leads":leads,"conversions":conv,"evidence":evidence,
                    "baseline_spend_cents":bspend,"baseline_leads":bleads,
                    "baseline_conversions":bconv,"baseline_rate":baseline_rate,
                    "followup_rate":follow_rate,
                    "percentage_point_change":round(follow_rate-baseline_rate,1)
                    if follow_rate is not None and baseline_rate is not None else None})
    return out

def render(c,uid,wid,csrf):
    bos.core.access(c,uid,wid);optimization.setup(c);setup(c)
    e=lambda v:html.escape(str(v),quote=True)
    money=lambda n:"$"+format(Decimal(n)/100,",.2f")
    rows=analyze(c,uid,wid)
    proposals=c.execute("SELECT id,revision_name FROM vx_optimization39 WHERE workspace_id=? AND status='implemented' ORDER BY created DESC",(wid,)).fetchall()
    out=['<section class="panel"><h1>Optimization Impact Ledger</h1>'
         '<p>Record dated follow-up performance after an approved change is manually marked implemented. '
         'Snapshots are append-only and include a source note. Baselines come from the current '
         'campaign totals, not a frozen pre-change measurement, and may cover different time windows. '
         'Any observed difference is descriptive only, NOT causal lift, proof of improvement, '
         'verified sales, or ROI.</p></section>']
    if proposals:
        out.append('<section class="panel"><h2>Record follow-up observation</h2>'
                   '<form method="post" action="/optimization-impact">'
                   '<input type="hidden" name="csrf" value="'+e(csrf)+'">'
                   '<input type="hidden" name="workspace" value="'+e(wid)+'">'
                   '<label>Implemented proposal<select name="proposal">'+
                   ''.join('<option value="'+e(pid)+'">'+e(name)+'</option>' for pid,name in proposals)+
                   '</select></label>'
                   '<label>Period start<input type="date" name="start" required></label>'
                   '<label>Period end<input type="date" name="end" required></label>'
                   '<label>Recorded spend ($)<input name="spend" required></label>'
                   '<label>Leads<input name="leads" type="number" min="0" required></label>'
                   '<label>Conversions<input name="conversions" type="number" min="0" required></label>'
                   '<label>Data source / evidence note<textarea name="evidence" maxlength="500" required></textarea></label>'
                   '<button>Save follow-up snapshot</button></form></section>')
    for r in rows:
        out.append('<section class="panel"><h2>'+e(r["proposal"])+'</h2><p>Base campaign: '+e(r["campaign"])+'</p>')
        if r["snapshot_id"]:
            out.append('<p>Follow-up period: '+e(r["start"])+' to '+e(r["end"])+'</p>'
                       '<p>Follow-up spend: '+money(r["spend_cents"])+
                       ' · Leads: '+str(r["leads"])+' · Conversions: '+str(r["conversions"])+'</p>'
                       '<p>Baseline conversion share (current cumulative record): '+
                       (str(r["baseline_rate"])+"%" if r["baseline_rate"] is not None else "N/A")+
                       ' · Follow-up conversion share: '+
                       (str(r["followup_rate"])+"%" if r["followup_rate"] is not None else "N/A")+'</p>'
                       '<p>Observed percentage-point difference: '+
                       (str(r["percentage_point_change"]) if r["percentage_point_change"] is not None else "N/A")+'</p>'
                       '<p>Evidence note: '+e(r["evidence"])+'</p>')
        else:out.append('<p>Awaiting first follow-up observation.</p>')
        out.append('</section>')
    if not rows:out.append('<section class="panel"><p>No implemented optimization proposals yet.</p></section>')
    return ''.join(out)
