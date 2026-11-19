"""Workspace-scoped follow-up tracking; manual records, no outbound actions."""
import html
import secrets
import time
from datetime import date
from urllib.parse import urlencode
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
    c.execute("UPDATE vx_followup23 SET status=?,updated=? WHERE workspace_id=? AND id=? AND status='planned'",
              (status,int(time.time()),wid,identifier))

def render(c,uid,wid,csrf,page=1,status_filter='all'):
    bos.core.access(c,uid,wid)
    setup(c)
    esc=lambda v:html.escape(str(v),quote=True)
    if type(page) is not int or not 1 <= page <= 10000:
        raise ValueError("Invalid follow-up page.")
    if status_filter not in ('all',) + STATES:
        raise ValueError("Invalid follow-up filter.")
    clause = " AND f.status=?" if status_filter != 'all' else ""
    params = (wid,status_filter) if status_filter != 'all' else (wid,)
    total = c.execute("SELECT COUNT(*) FROM vx_followup23 f WHERE f.workspace_id=?" + clause,params).fetchone()[0]
    pages = max(1,(total+49)//50)
    if page > pages:
        raise ValueError("Follow-up page is out of range.")
    query_url=lambda pg,st:'/revenue-followups?'+urlencode({'w':wid,'page':pg,'status':st})

    leads=c.execute("SELECT id,name FROM bos59_leads WHERE workspace_id=? AND status IN ('new','contacted') ORDER BY updated DESC LIMIT 300",(wid,)).fetchall()
    rows=c.execute("""SELECT f.id,l.name,f.due_date,f.status,f.note FROM vx_followup23 f
        JOIN bos59_leads l ON l.id=f.lead_id AND l.workspace_id=f.workspace_id
        WHERE f.workspace_id=?""" + clause + """ ORDER BY CASE WHEN f.status='planned' THEN 0 ELSE 1 END,
        f.due_date ASC,f.created DESC,f.id ASC LIMIT 50 OFFSET ?""",params+(50*(page-1),)).fetchall()
    today=date.today().isoformat()
    planned=sum(x[3]=="planned" for x in rows)
    overdue=sum(x[3]=="planned" and x[2]<today for x in rows)
    options=''.join('<option value="'+esc(lid)+'">'+esc(name)+'</option>' for lid,name in leads)
    out=['<section class="panel"><h1>Follow-up Tracker</h1><p>Schedule internal follow-up work and record outcomes. '
         'This feature never contacts customers automatically. Statuses are manually entered and do not verify collected revenue.</p>',
         '<p>Planned (displayed): '+str(planned)+' · Overdue (displayed): '+str(overdue)+' · Showing 50 per page.</p></section>']
    out.append('<section class="panel"><h2>Browse follow-ups</h2><form method="get" action="/revenue-followups">'
               '<input type="hidden" name="w" value="'+esc(wid)+'">'
               '<label>Status<select name="status">'+''.join(
                   '<option value="'+esc(st)+'"'+(' selected' if st==status_filter else '')+'>'+esc(st.title())+'</option>'
                   for st in ('all',)+STATES)+'</select></label><button>Filter</button></form>'
               '<p>Matching records: '+str(total)+' · Page '+str(page)+' of '+str(pages)+'</p>'
               +('<a href="'+esc(query_url(page-1,status_filter))+'">Previous</a> ' if page>1 else '')
               +('<a href="'+esc(query_url(page+1,status_filter))+'">Next</a>' if page<pages else '')+'</section>')
    if not rows:
        out.append('<section class="panel"><p>No follow-ups match this filter.</p></section>')
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
