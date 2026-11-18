"""Human-readable campaign decision support; descriptive, never causal or automated."""
import html
import urllib.parse
from decimal import Decimal
import business_os_v59 as bos
import campaign_experiments_v37 as campaigns

MIN_LEADS=30
MIN_CONVERSIONS=5

def evaluate(c,uid,wid):
    bos.core.access(c,uid,wid)
    rows=campaigns.analyze(c,uid,wid)
    output=[]
    for row in rows:
        leads=row["leads"]
        conversions=row["conversions"]
        spend=row["spend_cents"]
        if leads==0:
            decision="Collect data"
            reason="No recorded leads; performance cannot be evaluated."
        elif row["status"]!="completed":
            decision="Continue measurement"
            reason="Experiment is not marked completed; results may change."
        elif leads<MIN_LEADS or conversions<MIN_CONVERSIONS:
            decision="Insufficient evidence"
            reason="Fewer than 30 leads or five conversions. Gather more observations before comparing."
        elif spend==0:
            decision="Check cost data"
            reason="No recorded spending. Cost efficiency cannot be compared reliably."
        else:
            decision="Ready for human review"
            reason="Minimum descriptive data thresholds met. Compare cost per conversion and conversion share; this is not statistical proof."
        output.append({**row,"decision":decision,"reason":reason,
                       "cost_per_conversion_cents":round(spend/conversions) if conversions else None,
                       "meets_data_threshold":leads>=MIN_LEADS and conversions>=MIN_CONVERSIONS and spend>0 and row["status"]=="completed"})
    eligible=[r for r in output if r["meets_data_threshold"]]
    # Rankings are descriptive; never interpret as proof one campaign causes better outcomes.
    eligible.sort(key=lambda r:(r["cost_per_conversion_cents"],-r["conversion_pct"],r["name"]))
    for i,r in enumerate(eligible):
        r["descriptive_rank"]=i+1
    return output

def render(c,uid,wid):
    bos.core.access(c,uid,wid)
    rows=evaluate(c,uid,wid)
    e=lambda x:html.escape(str(x),quote=True)
    money=lambda cents:"$"+format(Decimal(cents)/100,",.2f")
    w=urllib.parse.quote(wid,safe="")
    out=['<section class="panel"><h1>Experiment Decision Engine</h1>',
         '<p>Review manually entered campaign performance before considering new investment. '
         'A completed campaign needs at least 30 recorded leads, five conversions, and nonzero recorded spend '
         'to qualify for descriptive cost-per-conversion ranking. These are screening thresholds, '
         'NOT statistical significance, verified conversions, causal lift, or ROI. '
         'Different audiences, conversion definitions, dates, and incomplete costs can invalidate comparisons. '
         'No campaign or budget is changed automatically.</p>',
         '<p><a href="/campaign-experiments?w='+w+'">Manage campaign experiments</a></p></section>']
    if not rows:
        return ''.join(out)+'<section class="panel"><p>No campaigns recorded yet.</p></section>'
    ranked=sorted(rows,key=lambda r:(not r["meets_data_threshold"],
                r["cost_per_conversion_cents"] if r["cost_per_conversion_cents"] is not None else 10**20,
                r["name"]))
    for row in ranked:
        out.append('<section class="panel"><h2>'+e(row["name"])+'</h2>'
                   '<p>'+e(row["source"])+' · '+e(row["status"])+' · '+e(row["decision"])+'</p>'
                   '<p>'+e(row["reason"])+'</p>'
                   '<p>Leads: '+str(row["leads"])+' · Conversions: '+str(row["conversions"])+
                   ' · Conversion share: '+(str(row["conversion_pct"])+"%" if row["conversion_pct"] is not None else "N/A")+'</p>'
                   '<p>Recorded spend: '+money(row["spend_cents"])+
                   ' · Cost per recorded conversion: '+
                   (money(row["cost_per_conversion_cents"]) if row["cost_per_conversion_cents"] is not None else "N/A")+'</p>')
        if row.get("descriptive_rank"):
            out.append('<p>Descriptive cost-efficiency rank among eligible campaigns: #'+str(row["descriptive_rank"])+'</p>')
        out.append('</section>')
    return ''.join(out)
