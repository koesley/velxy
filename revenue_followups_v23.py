"""Workspace-scoped follow-up tracking; manual records, no outbound actions."""
import html
import secrets
import time
from datetime import date, timedelta
import business_os_v59 as bos

STATES = ("planned", "contacted", "replied", "won", "lost")

def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS vx_followup23 (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, lead_id TEXT NOT NULL,
        due_date TEXT NOT NULL, status TEXT NOT NULL, note TEXT NOT NULL,
        created_by INTEGER NOT NULL, created INTEGER NOT NULL, updated INTEGER NOT NULL)""")
    c.execute("CREATE INDEX IF NOT EXISTS vx_followup23_scope ON vx_followup23(workspace_id,status,due_date)")

def create(c, uid, wid, lid, due_date, note):
    bos.core.access(c, uid, wid, write=True)
    setup(c)
    try:
        date.fromisoformat(due_date)
        if date.fromisoformat(due_date).isoformat() != due_date:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError("Enter a valid follow-up date (YYYY-MM-DD).")
    if not isinstance(note,str) or len(note.strip()) > 500:
        raise ValueError("Note must be at most 500 characters.")
    lead = c.execute("SELECT status FROM bos59_leads WHERE workspace_id=? AND id=?",
                     (wid,lid)).fetchone()
    if not lead or lead[0] not in ("new","contacted"):
        raise ValueError("Select an open lead from this workspace.")
    if c.execute("SELECT 1 FROM vx_followup23 WHERE workspace_id=? AND lead_id=? AND status='planned'",
                 (wid,lid)).fetchone():
        raise ValueError("A planned follow-up already exists for this lead.")
    identifier=secrets.token_hex(12)
    now=int(time.time())
    c.execute("INSERT INTO vx_followup23 VALUES(?,?,?,?,?,?,?,?,?)",
              (identifier,wid,lid,due_date,"planned",note.strip(),uid,now,now))
    return identifier

def change_status(c, uid, wid, identifier, status):
    bos.core.access(c,uid,wid,write=True)
    setup(c)
    if status not in STATES[1:]:
        raise ValueError("Invalid follow-up outcome.")
    row=c.execute("SELECT status FROM vx_followup23 WHERE workspace_id=? AND id=?",
                  (wid,identifier)).fetchone()
    if not row or row[0]!="planned":
        raise ValueError("Only planned follow-ups can be completed.")
    result = c.execute("UPDATE vx_followup23 SET status=?,updated=? WHERE workspace_id=? AND id=? AND status='planned'",
                       (status,int(time.time()),wid,identifier))
    if result.rowcount != 1:
        raise ValueError("Follow-up was already completed; refresh and try again.")

def workload(c, uid, wid, today=None):
    """Accurate, workspace-wide manual follow-up workload, not limited to visible rows."""
    bos.core.access(c, uid, wid)
    setup(c)
    today = today or date.today()
    if not isinstance(today, date):
        raise ValueError("Expected a date.")
    start = today.isoformat()
    end = (today + timedelta(days=7)).isoformat()
    row = c.execute("""SELECT
        COUNT(*),
        COALESCE(SUM(CASE WHEN status='planned' THEN 1 ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN status='planned' AND due_date<? THEN 1 ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN status='planned' AND due_date=? THEN 1 ELSE 0 END),0),
        COALESCE(SUM(CASE WHEN status='planned' AND due_date>? AND due_date<=? THEN 1 ELSE 0 END),0)
        FROM vx_followup23 WHERE workspace_id=?""",
        (start,start,start,end,wid)).fetchone()
    return dict(zip(("total","planned","overdue","due_today","next_seven_days"),
                    (int(value) for value in row)))


def render(c,uid,wid,csrf):
    bos.core.access(c,uid,wid)
    setup(c)
    esc=lambda v:html.escape(str(v),quote=True)
    leads=c.execute("SELECT id,name FROM bos59_leads WHERE workspace_id=? AND status IN ('new','contacted') ORDER BY updated DESC LIMIT 300",(wid,)).fetchall()
    rows=c.execute("""SELECT f.id,l.name,f.due_date,f.status,f.note FROM vx_followup23 f
        JOIN bos59_leads l ON l.id=f.lead_id AND l.workspace_id=f.workspace_id
        WHERE f.workspace_id=? ORDER BY CASE WHEN f.status='planned' THEN 0 ELSE 1 END,
        f.due_date ASC,f.created DESC LIMIT 100""",(wid,)).fetchall()
    today=date.today().isoformat()
    summary=workload(c,uid,wid)
    options=''.join('<option value="'+esc(lid)+'">'+esc(name)+'</option>' for lid,name in leads)
    out=['<section class="panel"><h1>Follow-up Tracker</h1><p>Schedule internal follow-up work and record outcomes. '
         'This feature never contacts customers automatically. Statuses are manually entered and do not verify collected revenue.</p>',
         '<p>Workspace totals: '+str(summary['planned'])+' planned · '+str(summary['overdue'])+
         ' overdue · '+str(summary['due_today'])+' due today · '+str(summary['next_seven_days'])+
         ' due in the next 7 days · '+str(summary['total'])+' total records.</p>'+
         '<p>Only the first 100 records are displayed; the lead selector shows at most 300 recent open leads. '
         'Counts cover the entire workspace, including records not displayed.</p>'+
         '<p><a href="/revenue-conversion?w='+esc(wid)+'">View revenue conversion summary</a></p></section>']
    if leads:
        out.append('<section class="panel"><h2>Plan a follow-up</h2><form method="post" action="/revenue-followups">'
                   '<input type="hidden" name="csrf" value="'+esc(csrf)+'">'
                   '<input type="hidden" name="workspace" value="'+esc(wid)+'">'
                   '<input type="hidden" name="action" value="create">'
                   '<label>Lead<select name="lead" required>'+options+'</select></label>'
                   '<label>Due date<input type="date" name="due_date" required></label>'
                   '<label>Internal note<input name="note" maxlength="500"></label>'
                   '<button>Schedule internal follow-up</button></form></section>')
    for identifier,name,due,status,note in rows:
        out.append('<section class="panel"><h3>'+esc(name)+'</h3><p>Due '+esc(due)+
                   ' · '+esc(status)+(' · Overdue' if status=="planned" and due<today else '')+
                   '</p><p>'+esc(note)+'</p>')
        if status=="planned":
            out.append('<form method="post" action="/revenue-followups">'
                       '<input type="hidden" name="csrf" value="'+esc(csrf)+'">'
                       '<input type="hidden" name="workspace" value="'+esc(wid)+'">'
                       '<input type="hidden" name="action" value="status">'
                       '<input type="hidden" name="id" value="'+esc(identifier)+'">'
                       '<label>Record outcome<select name="status">'+
                       ''.join('<option value="'+esc(x)+'">'+esc(x.title())+'</option>' for x in STATES[1:])+
                       '</select></label><button>Save outcome</button></form>')
        out.append('</section>')
    return ''.join(out)
