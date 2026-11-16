"""Workspace-scoped Mission Control for existing VELXTRIA Business OS.

Read-only aggregation. No AI inference, external execution, or cross-workspace joins.
"""
import html
import urllib.parse
import business_os_v59 as sales
import business_agents_v59 as workforce
import sovereign_v56 as core

def snapshot(c, uid, wid):
    core.access(c, uid, wid)
    leads = sales.overview(c, uid, wid)
    agents = workforce.overview(c, uid, wid)
    jobs = agents["jobs"]
    pipeline = leads["metrics"]
    pending = [j for j in jobs if j["status"] == "in_review"]
    blocked = [j for j in jobs if j["status"] == "rejected"]
    active = [j for j in jobs if j["status"] in ("queued", "approved")]
    return {
        "workspace": wid,
        "role": agents["role"],
        "pipeline": pipeline,
        "workforce": {
            "total_visible": len(jobs),
            "pending_review": len(pending),
            "queued_or_approved": len(active),
            "rejected": len(blocked),
            "completed": sum(j["status"] == "completed" for j in jobs),
        },
        "attention": [
            {"type": "agent_review", "id": j["id"], "agent": j["agent"],
             "summary": j["goal"], "status": j["status"]}
            for j in pending[:10]
        ],
        "limitations": [
            "Read-only view of existing workspace records; no agents run automatically.",
            "Pipeline values are entered by users, not verified revenue.",
            "Counts reflect the existing 200-job and 300-lead overview limits.",
            "No external actions, messaging, or autonomous decisions occur.",
        ],
    }

def render(c, uid, wid, csrf):
    d = snapshot(c, uid, wid)
    h = lambda v: html.escape(str(v), quote=True)
    q = "?w=" + urllib.parse.quote(wid, safe="")
    metrics = [
        ("Open pipeline (reported)", "$" + format(d["pipeline"]["open_pipeline"], ",.2f")),
        ("Won (reported)", "$" + format(d["pipeline"]["won_reported"], ",.2f")),
        ("Agent reviews", d["workforce"]["pending_review"]),
        ("Sales approvals", d["pipeline"]["pending_approvals"]),
        ("Active agent tasks", d["workforce"]["queued_or_approved"]),
        ("Completed (manual)", d["workforce"]["completed"]),
    ]
    cards = "".join('<article class="ov-card"><strong>' + h(label) +
                    '</strong><span>' + h(value) + '</span></article>'
                    for label, value in metrics)
    items = "".join('<li><strong>' + h(item["agent"]) + '</strong> · ' +
                    h(item["summary"]) + ' <small>Awaiting owner review</small></li>'
                    for item in d["attention"])
    if not items:
        items = "<li>No agent proposals awaiting review.</li>"
    return (
        '<section class="ov-hero"><span>VELXTRIA · MISSION CONTROL</span>'
        '<h1>Your business at a glance.</h1>'
        '<p>One permission-checked workspace view of revenue pipeline, agent queues, and human approvals. '
        'This dashboard observes existing data; it does not run agents or send messages.</p></section>'
        '<section class="ov-metrics">' + cards + '</section>'
        '<section class="ov-panel"><h2>Requires attention</h2><ul>' + items + '</ul></section>'
        '<section class="ov-panel"><h2>Operations</h2><p>'
        '<a href="/business-agents-v59' + h(q) + '">Review agent proposals</a> · '
        '<a href="/business-os-v59' + h(q) + '">Manage pipeline and approvals</a>'
        '</p><p>Workspace role: ' + h(d["role"]) + '</p></section>'
        '<section class="ov-panel"><h2>Data boundaries</h2><ul>' +
        "".join("<li>" + h(item) + "</li>" for item in d["limitations"]) +
        '</ul></section>'
    )
