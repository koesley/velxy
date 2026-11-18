"""Workspace-scoped cumulative pipeline goals, not verified revenue targets."""
import html
import urllib.parse
from decimal import Decimal, InvalidOperation
import business_os_v59 as bos

def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS vx_revenue_goals27 (
        workspace_id TEXT PRIMARY KEY, target_cents BIGINT NOT NULL,
        updated_by INTEGER NOT NULL, updated_at BIGINT NOT NULL)""")

def set_goal(c,uid,wid,amount):
    bos.core.access(c,uid,wid,write=True)
    setup(c)
    try:
        value=Decimal(str(amount))
        if not value.is_finite() or value<=0 or value>Decimal("1000000000") or value.as_tuple().exponent < -2:
            raise ValueError()
        cents=int(value*100)
    except (InvalidOperation,ValueError,TypeError):
        raise ValueError("Enter a positive target up to $1 billion, with at most two decimal places.")
    import time
    c.execute("""INSERT INTO vx_revenue_goals27(workspace_id,target_cents,updated_by,updated_at)
        VALUES(?,?,?,?) ON CONFLICT(workspace_id) DO UPDATE SET
        target_cents=excluded.target_cents,updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
        (wid,cents,uid,int(time.time())))

def snapshot(c,uid,wid):
    bos.core.access(c,uid,wid)
    setup(c)
    row=c.execute("SELECT target_cents FROM vx_revenue_goals27 WHERE workspace_id=?",(wid,)).fetchone()
    target=row[0] if row else None
    totals=c.execute("""SELECT status,COALESCE(SUM(value),0),COUNT(*) FROM bos59_leads
        WHERE workspace_id=? AND status IN ('new','contacted','won') GROUP BY status""",(wid,)).fetchall()
    sums={status:(Decimal(str(value)),count) for status,value,count in totals}
    won=sums.get("won",(Decimal(0),0))[0]
    open_value=sum((sums.get(s,(Decimal(0),0))[0] for s in ("new","contacted")),Decimal(0))
    target_value=Decimal(target)/100 if target is not None else None
    return {"target":target_value,"won_marked":won,"open_potential":open_value,
            "gap":max(Decimal(0),target_value-won) if target_value is not None else None,
            "progress_pct":min(100,round(float(won/target_value*100),1)) if target_value else None}

def render(c,uid,wid,csrf):
    data=snapshot(c,uid,wid)
    e=lambda x:html.escape(str(x),quote=True)
    money=lambda x:"$"+format(x,",.2f")
    out=['<section class="panel"><h1>Pipeline Goal Tracker</h1>',
         '<p>Set a cumulative goal for leads marked won. This is NOT a monthly revenue '
         'goal or proof of collected payments: lead values are manually entered estimates. '
         'No automatic customer contact or transactions.</p>',
         '<form method="post" action="/revenue-goals">',
         '<input type="hidden" name="csrf" value="'+e(csrf)+'">',
         '<input type="hidden" name="workspace" value="'+e(wid)+'">',
         '<label>Cumulative won-marked pipeline target ($)<input type="number" name="target" '
         'step="0.01" min="0.01" max="1000000000" required value="'+e(data["target"] or "")+'"></label>',
         '<button>Save target</button></form></section>',
         '<section class="panel"><h2>Progress</h2>']
    if data["target"] is None:
        out.append('<p>Set a target to see progress and remaining gap.</p>')
    else:
        out.append('<p>Target: '+money(data["target"])+' · Won-marked pipeline: '+
                   money(data["won_marked"])+' · Remaining gap: '+money(data["gap"])+
                   ' · Progress: '+e(data["progress_pct"])+'%</p>')
    out.append('<p>Open pipeline potential: '+money(data["open_potential"])+
               ' (not guaranteed conversions).</p><p><a href="/revenue-command?w='+
               urllib.parse.quote(wid,safe="")+'">Revenue Command Center</a></p></section>')
    return ''.join(out)
