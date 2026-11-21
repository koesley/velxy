"""VELXTRIA V4: tenant-scoped invoice workflows and actionable insights. No external sends."""
import html, secrets, time
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone

def e(v): return html.escape(str(v), quote=True)
def money(cents):
    # Format integer cents exactly; floating-point conversion can lose pennies
    # once portfolio totals grow beyond binary float's exact integer range.
    cents=int(cents)
    sign='-' if cents<0 else ''
    whole, remainder=divmod(abs(cents),100)
    return f'${sign}{whole:,}.{remainder:02d}'
def amount_cents(raw):
    try:
        d=Decimal(str(raw))
        if not d.is_finite() or d<=0 or d>100000000 or d.as_tuple().exponent < -2: raise ValueError()
        return int(d*100)
    except (ValueError, InvalidOperation): raise ValueError('Enter a positive amount with at most two decimal places.')
def setup(c):
    import persistent
    # Guard on the connection itself, not the REMOTE flag: the flag
    # describes the deployment, but setup can be handed a sqlite
    # connection while the flag is set (tests, the Render build), and the
    # Postgres-only lock call crashes on sqlite.
    if isinstance(c, persistent.PgConnection): c.execute('SELECT pg_advisory_xact_lock(731245, 921036)')
    # PostgreSQL INTEGER overflows above $21,474,836.47 in cents and at
    # Unix timestamps after 2038. SQLite INTEGER is already 64-bit.
    invoice_schema='''CREATE TABLE IF NOT EXISTS vx4_invoices (id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, contact_id TEXT, description TEXT NOT NULL, amount_cents BIGINT NOT NULL, status TEXT NOT NULL DEFAULT 'draft', due_at BIGINT NOT NULL, created_at BIGINT NOT NULL, paid_at BIGINT NOT NULL DEFAULT 0, FOREIGN KEY(user_id) REFERENCES users(id))'''
    c.execute(invoice_schema)
    if isinstance(c, persistent.PgConnection):
        # Idempotent upgrade of tables created by older deployments.
        # This runs under the existing transaction-scoped schema lock.
        for column in ('amount_cents','due_at','created_at','paid_at'):
            c.execute('ALTER TABLE vx4_invoices ALTER COLUMN '+column+' TYPE BIGINT')
    c.execute('''CREATE TABLE IF NOT EXISTS vx4_events (id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,invoice_id TEXT NOT NULL,event_type TEXT NOT NULL,created_at INTEGER NOT NULL,UNIQUE(user_id,invoice_id,event_type))''')
    c.execute('CREATE INDEX IF NOT EXISTS vx4_invoices_user ON vx4_invoices(user_id,created_at)')
    c.execute('CREATE INDEX IF NOT EXISTS vx4_events_user ON vx4_events(user_id,invoice_id)')
    # Supports overdue scans and outstanding invoice totals per tenant.
    c.execute('CREATE INDEX IF NOT EXISTS vx4_invoices_due ON vx4_invoices(user_id,status,due_at)')
    # Supports customer history without scanning unrelated tenants.
    c.execute('CREATE INDEX IF NOT EXISTS vx4_invoices_contact ON vx4_invoices(user_id,contact_id,created_at)')

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
    elif action=='invoice_duplicate':
        # Explicit internal action: reuse an invoice without issuing, sending,
        # collecting payment, or copying a stale due date.
        ident=fields.get('id','')
        source=c.execute(
            'SELECT contact_id,description,amount_cents FROM vx4_invoices WHERE id=? AND user_id=?',
            (ident,uid)
        ).fetchone()
        if not source: raise ValueError('Invoice not found.')
        cid,desc,cents=source
        if cid and not c.execute(
            'SELECT 1 FROM vx3_contacts WHERE id=? AND user_id=?',(cid,uid)
        ).fetchone():
            raise ValueError('Linked customer is no longer available.')
        if not isinstance(cents,int) or cents<=0 or cents>10000000000:
            raise ValueError('Source invoice amount is invalid.')
        # Due date defaults to seven UTC calendar days from now. The owner
        # must review and issue the new draft explicitly.
        ts=int(time.time())
        today=ts-ts%86400
        new_id=secrets.token_hex(16)
        c.execute(
            'INSERT INTO vx4_invoices(id,user_id,contact_id,description,amount_cents,status,due_at,created_at) '
            'VALUES (?,?,?,?,?,?,?,?)',
            (new_id,uid,cid,desc,cents,'draft',today+7*86400,ts)
        )
        c.execute(
            'INSERT INTO vx4_events(id,user_id,invoice_id,event_type,created_at) VALUES (?,?,?,?,?)',
            (secrets.token_hex(16),uid,new_id,'draft_copied',ts)
        )
    elif action in ('invoice_issue','invoice_pay','invoice_void'):
        ident=fields.get('id','')
        row=c.execute('SELECT contact_id,description,amount_cents,status FROM vx4_invoices WHERE id=? AND user_id=?',(ident,uid)).fetchone()
        if not row: raise ValueError('Invoice not found.')
        cid,desc,cents,status=row
        if action=='invoice_issue' and status=='draft':
            if c.execute("UPDATE vx4_invoices SET status='issued' WHERE id=? AND user_id=? AND status='draft'",(ident,uid)).rowcount != 1:
                raise ValueError('Invoice changed; refresh before retrying.')
            c.execute(
                "INSERT INTO vx4_events(id,user_id,invoice_id,event_type,created_at) VALUES (?,?,?,?,?)",
                (secrets.token_hex(16),uid,ident,'issued',int(time.time()))
            )
        elif action=='invoice_void' and status in ('draft','issued'):
            if c.execute("UPDATE vx4_invoices SET status='void' WHERE id=? AND user_id=? AND status=?",(ident,uid,status)).rowcount != 1:
                raise ValueError('Invoice changed; refresh before retrying.')
            c.execute(
                "INSERT INTO vx4_events(id,user_id,invoice_id,event_type,created_at) VALUES (?,?,?,?,?)",
                (secrets.token_hex(16),uid,ident,'voided',int(time.time()))
            )
            # A voided invoice must not leave an actionable overdue task.
            c.execute(
                "UPDATE vx3_tasks SET status='done' WHERE user_id=? AND title=? AND status='open'",
                (uid,'Invoice follow-up ['+ident+']')
            )
        elif action=='invoice_pay' and status=='issued':
            ts=int(time.time())
            changed=c.execute("UPDATE vx4_invoices SET status='paid',paid_at=? WHERE id=? AND user_id=? AND status='issued'",(ts,ident,uid)).rowcount
            if changed != 1:
                raise ValueError('Invoice was already changed; refresh before retrying.')
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
        today=ts-ts%86400
        rows=c.execute("SELECT id FROM vx4_invoices WHERE user_id=? AND status='issued' AND due_at<?",(uid,today)).fetchall()
        for (ident,) in rows:
            # Guarded no-op UPDATE acquires the invoice row lock in PostgreSQL.
            # A concurrent payment/void must complete before we decide whether
            # an overdue task is still appropriate.
            current=c.execute(
                "UPDATE vx4_invoices SET status=status "
                "WHERE id=? AND user_id=? AND status='issued' AND due_at<?",
                (ident,uid,today)
            ).rowcount
            if current != 1: continue
            # UNIQUE event + transaction makes repeated runs safe.
            event=c.execute('SELECT 1 FROM vx4_events WHERE user_id=? AND invoice_id=? AND event_type=?',(uid,ident,'overdue_task')).fetchone()
            if event: continue
            # Claim the unique event before creating a task. Concurrent workers
            # must not both create a reminder for the same invoice.
            claimed=c.execute(
                "INSERT INTO vx4_events(id,user_id,invoice_id,event_type,created_at) "
                "VALUES (?,?,?,?,?) ON CONFLICT(user_id,invoice_id,event_type) DO NOTHING",
                (secrets.token_hex(16),uid,ident,'overdue_task',ts)
            ).rowcount
            if claimed != 1: continue
            c.execute('INSERT INTO vx3_tasks(id,user_id,title,status,created_at) VALUES (?,?,?,?,?)',(secrets.token_hex(16),uid,'Invoice follow-up ['+ident+']','open',ts))
    else: raise ValueError('Unknown V4 action.')

def render(c,uid,csrf):
    token='<input type="hidden" name="csrf" value="'+e(csrf)+'">'
    contacts=c.execute('SELECT id,name FROM vx3_contacts WHERE user_id=? ORDER BY created_at DESC LIMIT 200',(uid,)).fetchall()
    invoices=c.execute('SELECT id,contact_id,description,amount_cents,status,due_at FROM vx4_invoices WHERE user_id=? ORDER BY created_at DESC LIMIT 50',(uid,)).fetchall()
    now=int(time.time())
    today=now-now%86400  # Invoice due dates are calendar dates in UTC.
    overdue=c.execute("SELECT COUNT(*),COALESCE(SUM(amount_cents),0) FROM vx4_invoices WHERE user_id=? AND status='issued' AND due_at<?",(uid,today)).fetchone()
    outstanding=c.execute("SELECT COALESCE(SUM(amount_cents),0) FROM vx4_invoices WHERE user_id=? AND status='issued'",(uid,)).fetchone()[0]
    paid=c.execute("SELECT COALESCE(SUM(amount_cents),0) FROM vx4_invoices WHERE user_id=? AND status='paid'",(uid,)).fetchone()[0]
    # Overdue aging is calculated from recorded invoices, never estimated.
    # These buckets are mutually exclusive and include only issued invoices.
    aging=c.execute(
        "SELECT "
        "COALESCE(SUM(CASE WHEN due_at>=? THEN amount_cents ELSE 0 END),0),"
        "COALESCE(SUM(CASE WHEN due_at<? AND due_at>=? THEN amount_cents ELSE 0 END),0),"
        "COALESCE(SUM(CASE WHEN due_at<? THEN amount_cents ELSE 0 END),0),"
        "SUM(CASE WHEN due_at>=? THEN 1 ELSE 0 END),"
        "SUM(CASE WHEN due_at<? AND due_at>=? THEN 1 ELSE 0 END),"
        "SUM(CASE WHEN due_at<? THEN 1 ELSE 0 END) "
        "FROM vx4_invoices WHERE user_id=? AND status='issued' AND due_at<?",
        (today-7*86400, today-7*86400, today-30*86400, today-30*86400,
         today-7*86400, today-7*86400, today-30*86400, today-30*86400,
         uid, today)
    ).fetchone()
    aging=tuple(int(value or 0) for value in aging)
    # Surface near-term collection risk before invoices become overdue.
    due_soon=c.execute(
        "SELECT COUNT(*),COALESCE(SUM(amount_cents),0) FROM vx4_invoices "
        "WHERE user_id=? AND status='issued' AND due_at>=? AND due_at<?",
        (uid,today,today+7*86400)
    ).fetchone()
    due_soon_items=c.execute(
        "SELECT description,amount_cents,due_at FROM vx4_invoices "
        "WHERE user_id=? AND status='issued' AND due_at>=? AND due_at<? "
        "ORDER BY due_at ASC, created_at ASC LIMIT 10",
        (uid,today,today+7*86400)
    ).fetchall()
    oldest=c.execute(
        "SELECT description,amount_cents,due_at FROM vx4_invoices "
        "WHERE user_id=? AND status='issued' AND due_at<? "
        "ORDER BY due_at ASC, created_at ASC LIMIT 10",
        (uid,today)
    ).fetchall()
    recent_events=c.execute(
        "SELECT i.description,e.event_type,e.created_at FROM vx4_events e "
        "JOIN vx4_invoices i ON i.id=e.invoice_id AND i.user_id=e.user_id "
        "WHERE e.user_id=? ORDER BY e.created_at DESC LIMIT 20",
        (uid,)
    ).fetchall()
    options='<option value="">No linked contact</option>'+''.join('<option value="'+e(cid)+'">'+e(name)+'</option>' for cid,name in contacts)
    body='<section class="panel"><h2>V4 · Revenue command center</h2><p>Issued and paid invoices, overdue risk, and customer-linked workflows. Internal records only; no emails, payment requests or money transfers are sent.</p>'
    body+='<div class="stats"><div><b>'+money(outstanding)+'</b><small>Outstanding invoices</small></div><div><b>'+money(overdue[1])+'</b><small>Overdue · '+str(overdue[0])+' invoices</small></div><div><b>'+money(paid)+'</b><small>Marked paid</small></div></div>'
    if recent_events:
        body+='<h3>Invoice activity</h3><div class="scroll"><table><tr><th>When (UTC)</th><th>Invoice</th><th>Action</th></tr>'
        for description,event_type,created_at in recent_events:
            body+='<tr><td>'+datetime.fromtimestamp(created_at,timezone.utc).strftime('%Y-%m-%d %H:%M')+'</td><td>'+e(description)+'</td><td>'+e(event_type.replace('_',' '))+'</td></tr>'
        body+='</table></div>'
    body+='<h3>Due within 7 days</h3><p><strong>'+money(due_soon[1])+'</strong> across '+str(due_soon[0])+' issued invoices. These are not yet overdue.</p>'
    if due_soon_items:
        body+='<p><small>Copy as draft reuses the customer, description, and amount with a new due date seven UTC days ahead. Review before issuing; no message or payment is sent.</small></p>'
    body+='<div class="scroll"><table><tr><th>Invoice</th><th>Amount</th><th>Due (UTC)</th></tr>'
        for description,cents,due_at in due_soon_items:
            body+='<tr><td>'+e(description)+'</td><td>'+money(cents)+'</td><td>'+datetime.fromtimestamp(due_at,timezone.utc).strftime('%Y-%m-%d')+'</td></tr>'
        body+='</table></div>'
    body+='<h3>Overdue receivables by age</h3><div class="stats">'
    for label,amount,count in (
        ('1–7 days overdue',aging[0],aging[3]),
        ('8–30 days overdue',aging[1],aging[4]),
        ('Over 30 days overdue',aging[2],aging[5]),
    ):
        body+='<div><b>'+money(amount)+'</b><small>'+label+' · '+str(count)+' invoices</small></div>'
    body+='</div><p><small>Aging uses UTC due dates and is based only on issued invoices. Payment status is manually recorded.</small></p>'
    if oldest:
        body+='<h3>Oldest unpaid invoices</h3><div class="scroll"><table><tr><th>Invoice</th><th>Amount</th><th>Days overdue</th></tr>'
        for description,cents,due_at in oldest:
            days_overdue=max(1,(today-due_at)//86400)
            body+='<tr><td>'+e(description)+'</td><td>'+money(cents)+'</td><td>'+str(days_overdue)+'</td></tr>'
        body+='</table></div>'
    body+='<p><strong>Next action:</strong> '+('Review '+str(overdue[0])+' overdue invoices and create follow-up tasks.' if overdue[0] else 'No overdue issued invoices in your entered records.')+'</p>'
    body+='<form method="post" action="/workspace">'+token+'<input type="hidden" name="action" value="invoice_reminders"><button>Create overdue follow-up tasks</button></form>'
    body+='<h3>Create invoice</h3><form method="post" action="/workspace">'+token+'<input type="hidden" name="action" value="invoice_create"><label>Customer<select name="contact_id">'+options+'</select></label><label>Description<input name="description" maxlength="180" required></label><label>Amount (USD)<input name="amount" type="number" min="0.01" step="0.01" required></label><label>Due date (UTC)<input name="due_date" type="date" required></label><button>Create draft invoice</button></form>'
    body+='<div class="scroll"><table><tr><th>Invoice</th><th>Amount</th><th>Due (UTC)</th><th>Status</th><th>Actions</th></tr>'
    for ident,cid,desc,cents,status,due in invoices:
        controls=''
        for action,label,allowed in [('invoice_duplicate','Copy as draft',True),('invoice_issue','Issue',status=='draft'),('invoice_pay','Mark paid',status=='issued'),('invoice_void','Void',status in ('draft','issued'))]:
            if allowed: controls+='<form method="post" action="/workspace">'+token+'<input type="hidden" name="action" value="'+action+'"><input type="hidden" name="id" value="'+e(ident)+'"><button>'+label+'</button></form>'
        body+='<tr><td>'+e(desc)+'</td><td>'+money(cents)+'</td><td>'+datetime.fromtimestamp(due,timezone.utc).strftime('%Y-%m-%d')+'</td><td>'+e(status)+(' · overdue' if status=='issued' and due<today else '')+'</td><td>'+controls+'</td></tr>'
    body+='</table></div><p><small>Mark paid only after verifying payment outside VELXTRIA. Marking paid records income once and updates linked CRM status. This is not an accounting or payment-processing system.</small></p></section>'
    return body
