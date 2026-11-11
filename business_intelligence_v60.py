"""V60 deterministic business analysis and approval-first task generation.

No external requests or claims of actual revenue. All figures are manual inputs.
"""
import html
from collections import Counter
import business_os_v59 as leads
import business_agents_v59 as agents

def analyze(c,uid,wid):
    data=leads.overview(c,uid,wid)
    workforce=agents.overview(c,uid,wid)
    rows=data["leads"]
    status=Counter(x["status"] for x in rows)
    total=sum(x["value"] for x in rows)
    open_rows=[x for x in rows if x["status"] in ("new","contacted")]
    suggestions=[]
    if status["new"]:
        suggestions.append({"code":"new_leads","agent":"sales","title":"Review new leads",
                            "evidence":str(status["new"])+" manually entered new leads",
                            "goal":"Review new leads and prepare personalized follow-up drafts for approval."})
    if status["contacted"]:
        suggestions.append({"code":"contacted_leads","agent":"sales","title":"Revisit contacted leads",
                            "evidence":str(status["contacted"])+" contacted leads",
                            "goal":"Review contacted leads and identify which need a follow-up."})
    if status["lost"]:
        suggestions.append({"code":"lost_leads","agent":"marketing","title":"Investigate lost leads",
                            "evidence":str(status["lost"])+" leads marked lost",
                            "goal":"Summarize common reasons for lost leads using verified notes."})
    faq_count=sum(k["kind"]=="faq" for k in workforce["knowledge"])
    if not faq_count:
        suggestions.append({"code":"faq","agent":"support","title":"Create an approved FAQ",
                            "evidence":"No FAQ entries in this workspace",
                            "goal":"Draft answers to frequent customer questions for owner review."})
    return {"lead_count":len(rows),"total_potential":round(total,2),
            "open_potential":round(sum(x["value"] for x in open_rows),2),
            "status_counts":dict(status),"pending_reviews":workforce["counts"]["awaiting_review"]+data["metrics"]["pending_approvals"],
            "agent_jobs":workforce["counts"]["jobs"],"suggestions":suggestions,
            "limitations":["Values are self-reported potential, not revenue or verified profit.",
                           "Suggestions are deterministic rules, not model-generated intelligence.",
                           "No outbound communication or automatic task execution occurs."]}

def enqueue(c,uid,wid,code):
    report=analyze(c,uid,wid)
    suggestion=next((s for s in report["suggestions"] if s["code"]==code),None)
    if not suggestion:raise ValueError("Suggestion not available")
    return agents.create_job(c,uid,wid,suggestion["agent"],suggestion["goal"]+" Evidence: "+suggestion["evidence"])

def render(c,uid,wid,csrf):
    d=analyze(c,uid,wid);role=agents.core.access(c,uid,wid)
    h=lambda v:html.escape(str(v),quote=True)
    out=['<section class="panel"><h1>VELXTRIA V60 · Business Intelligence</h1><p>Operational insights from your manually entered leads and curated business knowledge.</p></section>']
    out.append('<section class="panel"><h2>Command Center</h2><p>Leads: '+h(d["lead_count"])+' · Potential pipeline: '+h(d["open_potential"])+' · Awaiting approval: '+h(d["pending_reviews"])+' · Agent tasks: '+h(d["agent_jobs"])+'</p></section>')
    for s in d["suggestions"]:
        out.append('<section class="panel"><h2>'+h(s["title"])+'</h2><p>'+h(s["evidence"])+'</p><p>'+h(s["goal"])+'</p>')
        if role in ("owner","editor"):
            out.append('<form method="post" action="/business-intelligence-v60"><input type="hidden" name="csrf" value="'+h(csrf)+'"><input type="hidden" name="workspace" value="'+h(wid)+'"><input type="hidden" name="code" value="'+h(s["code"])+'"><button>Create agent task</button></form>')
        out.append('</section>')
    out.append('<section class="panel"><p><a href="/business-os-v59?w='+h(wid)+'">Revenue Recovery</a> · <a href="/business-agents-v59?w='+h(wid)+'">Agent Workforce</a></p><small>Recommendations are rule-based. No automatic sending or financial transactions.</small></section>')
    return ''.join(out)
