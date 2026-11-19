"""Workspace-safe workload summary for internal revenue tasks."""
from datetime import date

STATES=("todo","in_progress","done","blocked")

def summary(c, wid, today=None):
    today=today or date.today().isoformat()
    rows=c.execute("""SELECT status,COUNT(*) FROM vx_revenue_tasks29
        WHERE workspace_id=? GROUP BY status""",(wid,)).fetchall()
    counts={s:0 for s in STATES}
    for status,count in rows:
        if status in counts:counts[status]=count
    due=c.execute("""SELECT
      COALESCE(SUM(CASE WHEN status IN ('todo','in_progress') AND due_date<? THEN 1 ELSE 0 END),0),
      COALESCE(SUM(CASE WHEN status IN ('todo','in_progress') AND due_date=? THEN 1 ELSE 0 END),0),
      COALESCE(SUM(CASE WHEN status IN ('todo','in_progress') AND due_date>? THEN 1 ELSE 0 END),0)
      FROM vx_revenue_tasks29 WHERE workspace_id=?""",(today,today,today,wid)).fetchone()
    return counts,tuple(due)

def page(c,wid,status="all",number=1):
    if status not in ("all",)+STATES:raise ValueError("Invalid task filter.")
    try:number=int(number)
    except (ValueError,TypeError,OverflowError):raise ValueError("Invalid page.")
    if not 1<=number<=10000:raise ValueError("Invalid page.")
    where="t.workspace_id=?"
    params=[wid]
    if status!="all":
        where+=" AND t.status=?"
        params.append(status)
    total=c.execute("SELECT COUNT(*) FROM vx_revenue_tasks29 t WHERE "+where,tuple(params)).fetchone()[0]
    rows=c.execute("""SELECT t.id,l.name,t.title,t.due_date,t.status,t.owner_id
        FROM vx_revenue_tasks29 t JOIN bos59_leads l
        ON l.id=t.lead_id AND l.workspace_id=t.workspace_id
        WHERE """+where+""" ORDER BY CASE WHEN t.status='done' THEN 1 ELSE 0 END,
        t.due_date,t.created DESC,t.id LIMIT 25 OFFSET ?""",tuple(params+[25*(number-1)])).fetchall()
    return total,rows
