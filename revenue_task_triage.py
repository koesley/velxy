"""Read-only, workspace-scoped triage for overdue and stalled revenue tasks."""
import html
import urllib.parse
from datetime import date
import time
import business_os_v59 as bos
import revenue_execution_v29 as execution

def triage(c, uid, wid, now=None, limit=20):
    bos.core.access(c, uid, wid)
    execution.setup(c)
    current = int(time.time()) if now is None else int(now)
    today = date.fromtimestamp(current).isoformat()
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("Invalid triage limit.")
    # Join both lead ID and workspace ID to prevent cross-tenant lead disclosure.
    rows = c.execute(
        """SELECT t.id,t.title,t.status,t.due_date,t.updated,t.owner_id,l.name
           FROM vx_revenue_tasks29 t
           JOIN bos59_leads l ON l.id=t.lead_id AND l.workspace_id=t.workspace_id
           WHERE t.workspace_id=? AND t.status IN ('todo','in_progress','blocked')
           ORDER BY t.due_date ASC,t.updated ASC,t.id ASC""", (wid,)
    ).fetchall()
    counts = {"overdue": 0, "blocked": 0, "stalled": 0, "due_today": 0}
    ranked = []
    for identifier,title,status,due,updated,owner,name in rows:
        overdue = bool(due and due < today)
        blocked = status == "blocked"
        stalled = status in ("todo","in_progress") and current-int(updated) >= 7*86400
        due_today = due == today
        counts["overdue"] += int(overdue)
        counts["blocked"] += int(blocked)
        counts["stalled"] += int(stalled)
        counts["due_today"] += int(due_today)
        if overdue or blocked or stalled or due_today:
            priority = 0 if overdue else 1 if blocked else 2 if due_today else 3
            ranked.append((priority,due or "9999-12-31",int(updated),str(identifier),
                           {"id":identifier,"title":title,"status":status,"due":due,
                            "lead":name,"owner_id":owner,"overdue":overdue,
                            "blocked":blocked,"stalled":stalled,"due_today":due_today}))
    ranked.sort(key=lambda row: row[:4])
    return {"today":today,"counts":counts,"items":[r[4] for r in ranked[:limit]],
            "total_attention":len(ranked),"limit":limit}

def render(c, uid, wid, now=None):
    data = triage(c,uid,wid,now=now)
    esc = lambda v: html.escape(str(v),quote=True)
    w = urllib.parse.quote(wid,safe="")
    out = ['<section class="panel"><h2>Task attention queue</h2>',
           '<p>Read-only priorities based on manually recorded tasks. '
           'Overdue first, then blocked, due today, and stalled. '
           'Stalled means no update in at least seven days. '
           'These are not verified sales outcomes.</p>',
           '<p>Overdue: '+str(data["counts"]["overdue"])+
           ' · Blocked: '+str(data["counts"]["blocked"])+
           ' · Due today: '+str(data["counts"]["due_today"])+
           ' · Stalled: '+str(data["counts"]["stalled"])+
           '</p><p>Showing '+str(len(data["items"]))+' of '+
           str(data["total_attention"])+' tasks needing attention.</p>']
    if not data["items"]:
        out.append('<p>No recorded tasks currently meet these attention rules.</p>')
    for task in data["items"]:
        flags = [label for key,label in (("overdue","Overdue"),("blocked","Blocked"),
                 ("due_today","Due today"),("stalled","Stalled")) if task[key]]
        out.append('<article><h3>'+esc(task["title"])+'</h3><p>'+
                   esc(task["lead"])+' · '+esc(task["due"])+
                   ' · '+esc(", ".join(flags))+' · '+
                   ("Assigned to you" if task["owner_id"]==uid else "Assigned to another member")+
                   '</p></article>')
    out.append('<p><a href="/revenue-execution?w='+w+
               '">Review and update tasks manually</a></p></section>')
    return "".join(out)
