"""VELXTRIA V4: tenant-scoped invoice workflows and actionable insights. No external sends."""
import html, secrets, time
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone

def e(v): return html.escape(str(v), quote=True)
def money(cents): return f'${cents/100:,.2f}'
def amount_cents(raw):
    try:
        d=Decimal(str(raw))
        if not d.is_finite() or d<=0 or d>100000000 or d.as_tuple().exponent < -2: raise ValueError()
        return int(d*100)
    except (ValueError, InvalidOperation): raise ValueError('Enter a positive amount with at most two decimal places.')
def setup(c):
    import persistent
    if persistent.REMOTE: c.execute('SELECT pg_advisory_xact_lock(731245, 921036)')
    c.execute('''CREATE TABLE IF NOT EXISTS vx4_invoices (id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, contact_id TEXT, description TEXT NOT NULL, amount_cents INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'draft', due_at INTEGER NOT NULL, created_at INTEGER NOT NULL, paid_at INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(user_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS vx4_events (id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,invoice_id TEXT NOT NULL,event_type TEXT NOT NULL,created_at INTEGER NOT NULL,UNIQUE(user_id,invoice_id,event_type))''')
    c.execute('CREATE INDEX IF NOT EXISTS vx4_invoices_user ON vx4_invoices(user_id,created_at)')
    c.execute('CREATE INDEX IF NOT EXISTS vx4_events_user ON vx4_events(user_id,invoice_id)')

def process(c,uid,fields):
    action=fields.get('action','')
    if action=='invoice_create':
        desc=fields.get('description','').strip(); cid=fields.get('contact_id','').strip() or None
        if not 1<=len(desc)<=180: raise ValueError('Invoice description must be 1–180 characters.')
        if cid and not c.execute('SELECT 1 FROM vx3_contacts WHERE id=? AND user_id=?',(cid,uid)).fetchone(): raise ValueError('Customer not found.')
        try:
            due=datetime.strptime(fields.get('due_date',''),'%Y-%m-%d').replace(tzinfo=timezone.utc)
            due_at=int(due.timestamp())
            if due_at<0 or due_at>4102444800: raise ValueError()
        except (ValueError,OverflowError): raise ValueError('Choose a valid due date.')
        c.execute('INSERT INTO vx4_invoices(id,user_id,contact_id,description,amount_cents,due_at,created_at) VALUES (?,?,?,?,?,?,?)',(secrets.token_hex(16),uid,cid,desc,amount_cents(fields.get('amount','')),due_at,int(time.time())))
    elif action in ('invoice_issue','invoice_pay','invoice_void'):
        ident=fields.get('id','')
        row=c.execute('SELECT contact_id,description,amount_cents,status FROM vx4_invoices WHERE id=? AND user_id=?',(ident,uid)).fetchone()
        if not row: raise ValueError('Invoice not found.')
        cid,desc,cents,status=row
        if action=='invoice_issue' and status=='draft':
            c.execute("UPDATE vx4_invoices SET status='issued' WHERE id=? AND user_id=? AND status='draft'",(ident,uid))
        elif action=='invoice_void' and status in ('draft','issued'):
            c.execute("UPDATE vx4_invoices SET status='void' WHERE id=? AND user_id=? AND status=?",(ident,uid,status))
        elif action=='invoice_pay' and status=='issued':
            ts=int(time.time())
            c.execute("UPDATE vx4_invoices SET status='paid',paid_at=? WHERE id=? AND user_id=? AND status='issued'",(ts,ident,uid))
            c.execute('INSERT INTO vx3_entries(id,user_id,kind,description,amount_cents,created_at) VALUES (?,?,?,?,?,?)',(secrets.token_hex(16),uid,'income','Invoice paid: '+desc,cents,ts))
            if cid:
                c.execute("UPDATE vx3_contacts SET stage='won' WHERE id=? AND user_id=? AND stage NOT IN ('won','lost')",(cid,uid))
            c.execute('INSERT INTO vx4_events(id,user_id,invoice_id,event_type,created_at) VALUES (?,?,?,?,?)',(secrets.token_hex(16),uid,ident,'paid',ts))
            # Close only system-created overdue reminder, not user-created tasks.
            task_title='Invoice follow-up ['+ident+']'
            c.execute("UPDATE vx3_tasks SET status='done' WHERE user_id=? AND title=? AND status='open'",(uid,task_title))
        else: raise ValueError('Invoice action is not allowed in its current status.')
    elif action=='invoice_reminders':
        ts=int(time.time())
        rows=c.execute("SELECT id FROM vx4_invoices WHERE user_id=? AND status='issued' AND due_at<?",(uid,ts)).fetchall()
        for (ident,) in rows:
            # UNIQUE event + transaction makes repeated runs safe.
            event=c.execute('SELECT 1 FROM vx4_events WHERE user_id=? AND invoice_id=? AND event_type=?',(uid,ident,'overdue_task')).fetchone()
            if event: continue
            c.execute('INSERT INTO vx3_tasks(id,user_id,title,status,created_at) VALUES (?,?,?,?,?)',(secrets.token_hex(16),uid,'Invoice follow-up ['+ident+']','open',ts))
            c.execute('INSERT INTO vx4_events(id,user_id,invoice_id,event_type,created_at) VALUES (?,?,?,?,?)',(secrets.token_hex(16),uid,ident,'overdue_task',ts))
    else: raise ValueError('Unknown V4 action.')

def render(c,uid,csrf):
    token='<input type="hidden" name="csrf" value="'+e(csrf)+'">'
    contacts=c.execute('SELECT id,name FROM vx3_contacts WHERE user_id=? ORDER BY created_at DESC LIMIT 200',(uid,)).fetchall()
    invoices=c.execute('SELECT id,contact_id,description,amount_cents,status,due_at FROM vx4_invoices WHERE user_id=? ORDER BY created_at DESC LIMIT 50',(uid,)).fetchall()
    now=int(time.time())
    overdue=c.execute("SELECT COUNT(*),COALESCE(SUM(amount_cents),0) FROM vx4_invoices WHERE user_id=? AND status='issued' AND due_at<?",(uid,now)).fetchone()
    outstanding=c.execute("SELECT COALESCE(SUM(amount_cents),0) FROM vx4_invoices WHERE user_id=? AND status='issued'",(uid,)).fetchone()[0]
    paid=c.execute("SELECT COALESCE(SUM(amount_cents),0) FROM vx4_invoices WHERE user_id=? AND status='paid'",(uid,)).fetchone()[0]
    options='<option value="">No linked contact</option>'+''.join('<option value="'+e(cid)+'">'+e(name)+'</option>' for cid,name in contacts)
    body='<section class="panel"><h2>V4 · Revenue command center</h2><p>Issued and paid invoices, overdue risk, and customer-linked workflows. Internal records only; no emails, payment requests or money transfers are sent.</p>'
    body+='<div class="stats"><div><b>'+money(outstanding)+'</b><small>Outstanding invoices</small></div><div><b>'+money(overdue[1])+'</b><small>Overdue · '+str(overdue[0])+' invoices</small></div><div><b>'+money(paid)+'</b><small>Marked paid</small></div></div>'
    body+='<p><strong>Next action:</strong> '+('Review '+str(overdue[0])+' overdue invoices and create follow-up tasks.' if overdue[0] else 'No overdue issued invoices in your entered records.')+'</p>'
    body+='<form method="post" action="/workspace">'+token+'<input type="hidden" name="action" value="invoice_reminders"><button>Create overdue follow-up tasks</button></form>'
    body+='<h3>Create invoice</h3><form method="post" action="/workspace">'+token+'<input type="hidden" name="action" value="invoice_create"><label>Customer<select name="contact_id">'+options+'</select></label><label>Description<input name="description" maxlength="180" required></label><label>Amount (USD)<input name="amount" type="number" min="0.01" step="0.01" required></label><label>Due date (UTC)<input name="due_date" type="date" required></label><button>Create draft invoice</button></form>'
    body+='<div class="scroll"><table><tr><th>Invoice</th><th>Amount</th><th>Due (UTC)</th><th>Status</th><th>Actions</th></tr>'
    for ident,cid,desc,cents,status,due in invoices:
        controls=''
        for action,label,allowed in [('invoice_issue','Issue',status=='draft'),('invoice_pay','Mark paid',status=='issued'),('invoice_void','Void',status in ('draft','issued'))]:
            if allowed: controls+='<form method="post" action="/workspace">'+token+'<input type="hidden" name="action" value="'+action+'"><input type="hidden" name="id" value="'+e(ident)+'"><button>'+label+'</button></form>'
        body+='<tr><td>'+e(desc)+'</td><td>'+money(cents)+'</td><td>'+datetime.fromtimestamp(due,timezone.utc).strftime('%Y-%m-%d')+'</td><td>'+e(status)+(' · overdue' if status=='issued' and due<now else '')+'</td><td>'+controls+'</td></tr>'
    body+='</table></div><p><small>Mark paid only after verifying payment outside VELXTRIA. Marking paid records income once and updates linked CRM status. This is not an accounting or payment-processing system.</small></p></section>'
    return body
