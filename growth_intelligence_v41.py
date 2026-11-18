"""Workspace-scoped growth intelligence combining recorded operating signals."""
import html
import urllib.parse
from decimal import Decimal
import business_os_v59 as bos
import acquisition_intelligence_v35 as acquisition
import campaign_experiments_v37 as campaigns
import experiment_decisions_v38 as decisions
import optimization_impact_v40 as impact
import customer_outcomes_v33 as outcomes

def analyze(c,uid,wid):
    bos.core.access(c,uid,wid)
    channel_rows=acquisition.analyze(c,uid,wid)
    campaign_rows=campaigns.analyze(c,uid,wid)
    decision_rows=decisions.evaluate(c,uid,wid)
    impact_rows=impact.analyze(c,uid,wid)
    outcomes_snapshot=outcomes.snapshot(c,uid,wid)
    spend=sum(r["cost_cents"] for r in channel_rows)
    reported=sum(r["reported_cents"] for r in channel_rows)
    leads=sum(r["leads"] for r in channel_rows)
    won=sum(r["won_leads"] for r in channel_rows)
    # Campaign spend is a separate manual ledger and may overlap acquisition spend.
    campaign_spend=sum(r["spend_cents"] for r in campaign_rows)
    completed=sum(r["status"]=="completed" for r in campaign_rows)
    review_ready=sum(r["meets_data_threshold"] for r in decision_rows)
    observed=sum(bool(r["snapshot_id"]) for r in impact_rows)
    pending=sum(not r["snapshot_id"] for r in impact_rows)
    flags=[]
    if not channel_rows:flags.append("No lead sources recorded. Add leads before interpreting acquisition performance.")
    if channel_rows and not spend:flags.append("No acquisition spending recorded; zero entries are not evidence of free acquisition.")
    if channel_rows and any(r["source"]=="Unspecified" for r in channel_rows):
        flags.append("Some leads have unspecified acquisition sources.")
    if campaign_rows and not completed:flags.append("No completed campaign experiments yet.")
    if campaign_rows and not review_ready:flags.append("No completed campaigns meet descriptive screening thresholds.")
    if pending:flags.append(str(pending)+" implemented optimization proposals await a follow-up observation.")
    return {"channels":channel_rows,"campaigns":campaign_rows,"decisions":decision_rows,
            "impacts":impact_rows,"outcomes":outcomes_snapshot,
            "lead_count":leads,"won_lead_count":won,"acquisition_spend_cents":spend,
            "reported_payment_cents":reported,"campaign_spend_cents":campaign_spend,
            "completed_campaigns":completed,"review_ready_campaigns":review_ready,
            "followup_snapshots":observed,"pending_followups":pending,"flags":flags}

def render(c,uid,wid):
    data=analyze(c,uid,wid)
    e=lambda v:html.escape(str(v),quote=True)
    money=lambda n:"$"+format(Decimal(n)/100,",.2f")
    w=urllib.parse.quote(wid,safe="")
    out=['<section class="panel"><h1>Business Growth Intelligence Center</h1>'
         '<p>A consolidated view of manually recorded acquisition, marketing experiments, '
         'customer outcomes and post-change observations. Financial claims are unverified. '
         'Separate expense ledgers may overlap and must NOT be summed as total spend. '
         'Observed campaign changes do not establish causation, verified profit, or ROI.</p></section>',
         '<section class="panel"><h2>Growth overview</h2>'
         '<p>Recorded leads: '+str(data["lead_count"])+' · Won-marked leads: '+str(data["won_lead_count"])+'</p>'
         '<p>Acquisition expense ledger: '+money(data["acquisition_spend_cents"])+
         ' · Campaign experiment spend ledger (potential overlap): '+money(data["campaign_spend_cents"])+'</p>'
         '<p>Source-associated self-reported payments: '+money(data["reported_payment_cents"])+
         ' · Completed experiments: '+str(data["completed_campaigns"])+
         ' · Eligible for descriptive review: '+str(data["review_ready_campaigns"])+'</p>'
         '<p>Recorded optimization follow-up snapshots: '+str(data["followup_snapshots"])+
         ' · Implemented proposals awaiting observations: '+str(data["pending_followups"])+'</p></section>']
    if data["flags"]:
        out.append('<section class="panel"><h2>Data gaps & next actions</h2><ul>'+
                   ''.join('<li>'+e(flag)+'</li>' for flag in data["flags"])+'</ul></section>')
    out.append('<section class="panel"><h2>Acquisition channels</h2>')
    if not data["channels"]:out.append('<p>No recorded acquisition channels.</p>')
    for r in data["channels"][:15]:
        out.append('<p><strong>'+e(r["source"])+'</strong> — '+str(r["leads"])+
                   ' leads, '+str(r["won_leads"])+' won-marked, '+money(r["cost_cents"])+
                   ' recorded spend, '+money(r["reported_cents"])+' reported payments</p>')
    out.append('<p><a href="/acquisition-intelligence?w='+w+'">Manage acquisition costs</a></p></section>')
    out.append('<section class="panel"><h2>Experiment decision queue</h2>')
    for r in data["decisions"][:12]:
        out.append('<p><strong>'+e(r["name"])+'</strong> — '+e(r["decision"])+
                   ': '+e(r["reason"])+'</p>')
    if not data["decisions"]:out.append('<p>No campaign experiments yet.</p>')
    out.append('<p><a href="/experiment-decisions?w='+w+'">Review all experiment decisions</a></p></section>')
    out.append('<section class="panel"><h2>Optimization follow-up</h2>')
    for r in data["impacts"][:12]:
        label=("Observed difference: "+str(r["percentage_point_change"])+" percentage points"
               if r["percentage_point_change"] is not None else "No comparable percentage yet")
        out.append('<p><strong>'+e(r["proposal"])+'</strong> — '+
                   (e(label) if r["snapshot_id"] else "Awaiting follow-up observation")+'</p>')
    if not data["impacts"]:out.append('<p>No implemented optimization proposals yet.</p>')
    out.append('<p><a href="/optimization-impact?w='+w+'">Record follow-up evidence</a></p></section>')
    return ''.join(out)
