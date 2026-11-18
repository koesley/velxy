"""Campaign Optimization Workbench: documented experiments and approval-controlled decisions."""
import html
import secrets
import time
import urllib.parse
from decimal import Decimal,InvalidOperation
import business_os_v59 as bos
import campaign_experiments_v37 as campaigns

STATES=("proposed","approved","rejected","implemented")
def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS vx_optimization39 (
      id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,base_campaign_id TEXT NOT NULL,
      creator_id INTEGER NOT NULL,reviewer_id INTEGER,revision_name TEXT NOT NULL,
      change_description TEXT NOT NULL,hypothesis TEXT NOT NULL,
      success_metric TEXT NOT NULL,target_value TEXT NOT NULL,
      estimated_budget_cents INTEGER NOT NULL,status TEXT NOT NULL,
      decision_note TEXT NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS vx_optimization39_scope ON vx_optimization39(workspace_id,base_campaign_id)")

def money(value):
    try:
        v=Decimal(str(value))
        if not v.is_finite() or v<0 or v>Decimal("1000000000") or v.as_tuple().exponent < -2:raise ValueError()
        return int(v*100)
    except (ValueError,TypeError,InvalidOperation):raise ValueError("Budget must be a nonnegative monetary amount with at most two decimals.")

def propose(c,uid,wid,campaign_id,name,change,hypothesis,metric,target,budget):
    bos.core.access(c,uid,wid,write=True);setup(c);campaigns.setup(c)
    if not c.execute("SELECT 1 FROM vx_campaign37 WHERE workspace_id=? AND id=?",(wid,campaign_id)).fetchone():
        raise ValueError("Campaign not found in workspace.")
    fields=[str(v).strip() for v in (name,change,hypothesis,metric,target)]
    if any(not v for v in fields) or any(len(v)>500 for v in fields) or len(fields[0])>120:
        raise ValueError("Complete all proposal fields (maximum 500 characters; name 120).")
    identifier=secrets.token_hex(12);now=int(time.time())
    c.execute("INSERT INTO vx_optimization39 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (identifier,wid,campaign_id,uid,None,*fields,money(budget),"proposed","",now,now))
    return identifier

def decide(c,uid,wid,identifier,action,note):
    bos.core.access(c,uid,wid,write=True);setup(c)
    row=c.execute("SELECT creator_id,status FROM vx_optimization39 WHERE workspace_id=? AND id=?",(wid,identifier)).fetchone()
    if not row:raise ValueError("Proposal not found.")
    creator,status=row
    note=str(note).strip()
    if len(note)>500:raise ValueError("Decision note too long.")
    if action in ("approved","rejected"):
        if status!="proposed":raise ValueError("Only proposed revisions can be reviewed.")
        if creator==uid:raise ValueError("A different workspace member must review the proposal.")
        if not note:raise ValueError("Explain the approval decision.")
    elif action=="implemented":
        if status!="approved":raise ValueError("Only approved revisions can be marked implemented.")
        if creator!=uid:raise ValueError("Only the proposal creator can mark implementation.")
        if not note:raise ValueError("Describe what was implemented.")
    else:raise ValueError("Unknown decision.")
    c.execute("UPDATE vx_optimization39 SET status=?,reviewer_id=?,decision_note=?,updated=? WHERE workspace_id=? AND id=?",
              (action,uid,note,int(time.time()),wid,identifier))

def analyze(c,uid,wid):
    bos.core.access(c,uid,wid);setup(c);campaigns.setup(c)
    rows=c.execute("""SELECT p.id,p.creator_id,p.reviewer_id,p.revision_name,p.change_description,
        p.hypothesis,p.success_metric,p.target_value,p.estimated_budget_cents,p.status,
        p.decision_note,c.name,c.spend_cents,c.leads,c.conversions
        FROM vx_optimization39 p JOIN vx_campaign37 c
        ON p.base_campaign_id=c.id AND p.workspace_id=c.workspace_id
        WHERE p.workspace_id=? ORDER BY p.created DESC LIMIT 150""",(wid,)).fetchall()
    return [dict(zip(("id","creator","reviewer","name","change","hypothesis","metric","target",
                      "budget_cents","status","note","campaign","baseline_spend_cents",
                      "baseline_leads","baseline_conversions"),r)) for r in rows]

def render(c,uid,wid,csrf):
    bos.core.access(c,uid,wid);campaigns.setup(c);setup(c)
    e=lambda v:html.escape(str(v),quote=True)
    dollars=lambda n:"$"+format(Decimal(n)/100,",.2f")
    campaign_rows=c.execute("SELECT id,name FROM vx_campaign37 WHERE workspace_id=? ORDER BY created DESC LIMIT 150",(wid,)).fetchall()
    rows=analyze(c,uid,wid)
    out=['<section class="panel"><h1>Campaign Optimization Workbench</h1>',
         '<p>Develop alternative hypotheses, set measurable success criteria, and route changes '
         'through independent review. Proposed budgets are planning figures only. '
         'Marking a proposal implemented records a manual assertion; it does not launch ads, '
         'change campaigns, spend funds, or establish causal improvement.</p></section>']
    if campaign_rows:
        out.append('<section class="panel"><h2>Propose an optimization</h2>'
                   '<form method="post" action="/campaign-optimization">'
                   '<input type="hidden" name="csrf" value="'+e(csrf)+'">'
                   '<input type="hidden" name="workspace" value="'+e(wid)+'">'
                   '<input type="hidden" name="action" value="propose">'
                   '<label>Existing campaign<select name="campaign">'+
                   ''.join('<option value="'+e(cid)+'">'+e(name)+'</option>' for cid,name in campaign_rows)+
                   '</select></label>'
                   '<label>Revision name<input name="name" maxlength="120" required></label>'
                   '<label>What changes?<textarea name="change" maxlength="500" required></textarea></label>'
                   '<label>Why might it work?<textarea name="hypothesis" maxlength="500" required></textarea></label>'
                   '<label>Success metric<input name="metric" maxlength="500" required></label>'
                   '<label>Target value<input name="target" maxlength="500" required></label>'
                   '<label>Proposed budget ($)<input name="budget" required value="0"></label>'
                   '<button>Submit for review</button></form></section>')
    for r in rows:
        out.append('<section class="panel"><h2>'+e(r["name"])+'</h2><p>Base campaign: '+
                   e(r["campaign"])+' · '+e(r["status"])+'</p><p>Change: '+e(r["change"])+
                   '</p><p>Hypothesis: '+e(r["hypothesis"])+'</p><p>Success: '+
                   e(r["metric"])+' — target '+e(r["target"])+'</p>'
                   '<p>Proposed budget: '+dollars(r["budget_cents"])+
                   ' · Base campaign spend: '+dollars(r["baseline_spend_cents"])+
                   ' · Base leads: '+str(r["baseline_leads"])+
                   ' · Base conversions: '+str(r["baseline_conversions"])+'</p>'
                   '<p>Decision record: '+e(r["note"] or "Pending")+'</p>')
        actions=(("approved","rejected") if r["status"]=="proposed" and r["creator"]!=uid
                 else ("implemented",) if r["status"]=="approved" and r["creator"]==uid else ())
        for action in actions:
            out.append('<form method="post" action="/campaign-optimization">'
                       '<input type="hidden" name="csrf" value="'+e(csrf)+'">'
                       '<input type="hidden" name="workspace" value="'+e(wid)+'">'
                       '<input type="hidden" name="action" value="'+action+'">'
                       '<input type="hidden" name="id" value="'+e(r["id"])+'">'
                       '<label>'+action.title()+' rationale<input name="note" maxlength="500" required></label>'
                       '<button>'+action.title()+'</button></form>')
        out.append('</section>')
    if not rows:out.append('<section class="panel"><p>No optimization proposals yet.</p></section>')
    return ''.join(out)
