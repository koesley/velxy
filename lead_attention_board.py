"""Read-only sales attention board. Manual review only; never sends outreach."""
import html
import time
import sales_pipeline

ACTIVE = ("new", "contacted", "replied", "meeting", "proposal")
THRESHOLDS = {"new": 2, "contacted": 5, "replied": 3, "meeting": 3, "proposal": 7}
BLOCKED = {"do_not_contact", "suppress_permanent", "suppress_rejected"}

def attention(c, owner, now=None, limit=100):
    """Owner-scoped review candidates; updated_at is an activity proxy, not a contact log."""
    sales_pipeline.setup(c)
    now = int(time.time() if now is None else now)
    if not isinstance(limit, int) or not 1 <= limit <= 200:
        raise ValueError("Invalid display limit")
    # Query all active leads for exact totals; cap only the displayed review list.
    rows = c.execute("""SELECT l.id,l.business,l.email,l.stage,l.estimated_value,l.updated_at,
                        COALESCE(s.status,'unverified')
                        FROM sales_pipeline_leads l
                        LEFT JOIN outreach_suppression s
                          ON s.owner_id=l.owner_id AND s.email=LOWER(TRIM(l.email))
                        WHERE l.owner_id=? AND l.stage IN ('new','contacted','replied','meeting','proposal')
                        ORDER BY l.updated_at ASC, l.id ASC""", (owner,)).fetchall()
    result = []
    for ident, business, email, stage, value, updated, status in rows:
        age = max(0, (now-int(updated))//86400)
        due = age >= THRESHOLDS[stage]
        protected = status in BLOCKED
        result.append({"id":ident,"business":business,"email":email,"stage":stage,
                       "estimated_value":value,"age_days":age,"due":due,
                       "contact_status":status,"blocked":protected})
    result.sort(key=lambda x:(not x["due"], not x["blocked"], -x["age_days"], x["id"]))
    return {"active":len(result),"needs_review":sum(x["due"] for x in result),
            "blocked":sum(x["blocked"] for x in result),
            "displayed":result[:limit],"truncated":len(result)>limit}

def dashboard(c, owner, now=None):
    info=attention(c,owner,now)
    e=lambda x:html.escape(str(x),quote=True)
    parts=['<section class="hero"><h1>Lead Attention Board</h1><p>Review stalled opportunities without automatic outreach. Time since last record update is not proof of last customer contact.</p></section>',
           '<section class="panel"><h2>Manual review queue</h2><p>'+str(info["active"])+' active leads · '+str(info["needs_review"])+' due for review · '+str(info["blocked"])+' with permanent contact restrictions</p>',
           '<p>Review thresholds: new 2 days; contacted 5; replied or meeting 3; proposal 7. These are suggestions, not scheduled messages.</p>',
           '<p>Only independently verified contact permission should be used for outreach. No email is sent by this board.</p></section>']
    if info["truncated"]:
        parts.append('<p>Showing the first 100 priority records; totals include every active lead.</p>')
    for r in info["displayed"]:
        state="Review due" if r["due"] else "Not due"
        safety="Do not contact" if r["blocked"] else ("Contact unverified" if r["contact_status"]=="unverified" else "Check contact eligibility")
        parts.append('<section class="panel"><h3>'+e(r["business"])+'</h3><p>'+e(r["stage"].title())+' · '+str(r["age_days"])+' days since update · '+state+'</p><p>'+e(safety)+' · '+e(r["contact_status"])+'</p><p>Estimated deal value: $'+e(r["estimated_value"])+' (not received revenue)</p></section>')
    if not info["active"]:
        parts.append('<section class="panel"><p>No active leads. Add prospects in the Sales Pipeline to begin reviewing opportunities.</p></section>')
    parts.append('<p><a href="/sales-pipeline">Manage leads and contact restrictions in Sales Pipeline</a></p>')
    return ''.join(parts)
