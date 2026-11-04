"""VELXTRIA V3 modular business workspace. Manual-only workflows; no external side effects."""
import html, time, secrets
from datetime import datetime, timezone

MODULES=('small_business','online_seller','freelancer','agency')
def e(v): return html.escape(str(v),quote=True)
def setup(c):
    import persistent
    if persistent.REMOTE: c.execute('SELECT pg_advisory_xact_lock(731245, 921035)')
    c.execute('''CREATE TABLE IF NOT EXISTS vx3_profiles (user_id INTEGER PRIMARY KEY, business_name TEXT NOT NULL DEFAULT '', business_type TEXT NOT NULL DEFAULT 'small_business', FOREIGN KEY(user_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS vx3_contacts (id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,name TEXT NOT NULL,email TEXT NOT NULL DEFAULT '',stage TEXT NOT NULL DEFAULT 'lead',created_at INTEGER NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS vx3_entries (id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,kind TEXT NOT NULL,description TEXT NOT NULL,amount_cents INTEGER NOT NULL,created_at INTEGER NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS vx3_tasks (id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,title TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',due_at INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id))''')
    c.execute('CREATE INDEX IF NOT EXISTS vx3_contacts_user ON vx3_contacts(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS vx3_entries_user ON vx3_entries(user_id,created_at)')
    c.execute('CREATE INDEX IF NOT EXISTS vx3_tasks_user ON vx3_tasks(user_id,status)')

def process(c,uid,fields):
    action=fields.get('action','')
    if action=='profile':
        name=fields.get('business_name','').strip(); typ=fields.get('business_type','')
        if not 1<=len(name)<=100 or typ not in MODULES: raise ValueError('Enter a business name and valid workspace type.')
        c.execute('''INSERT INTO vx3_profiles(user_id,business_name,business_type) VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET business_name=excluded.business_name,business_type=excluded.business_type''',(uid,name,typ))
    elif action=='contact':
        name=fields.get('name','').strip();email=fields.get('email','').strip();stage=fields.get('stage','lead')
        if not 1<=len(name)<=120 or len(email)>254 or ('@' not in email and email) or stage not in ('lead','contacted','qualified','won','lost'): raise ValueError('Invalid contact details.')
        c.execute('INSERT INTO vx3_contacts(id,user_id,name,email,stage,created_at) VALUES (?,?,?,?,?,?)',(secrets.token_hex(16),uid,name,email,stage,int(time.time())))
    elif action=='entry':
        kind=fields.get('kind','');desc=fields.get('description','').strip();amount=fields.get('amount','').strip()
        from decimal import Decimal, InvalidOperation
        try:
            val=Decimal(amount)
            if not val.is_finite() or val<=0 or val>100000000 or val.as_tuple().exponent < -2: raise ValueError()
            cents=int(val*100)
        except (InvalidOperation,ValueError): raise ValueError('Enter a positive amount with at most two decimal places.')
        if kind not in ('income','expense') or not 1<=len(desc)<=180: raise ValueError('Invalid finance entry.')
        c.execute('INSERT INTO vx3_entries(id,user_id,kind,description,amount_cents,created_at) VALUES (?,?,?,?,?,?)',(secrets.token_hex(16),uid,kind,desc,cents,int(time.time())))
    elif action=='task':
        title=fields.get('title','').strip()
        if not 1<=len(title)<=180: raise ValueError('Task title must be 1–180 characters.')
        c.execute('INSERT INTO vx3_tasks(id,user_id,title,created_at) VALUES (?,?,?,?)',(secrets.token_hex(16),uid,title,int(time.time())))
    elif action=='complete_task':
        c.execute("UPDATE vx3_tasks SET status='done' WHERE id=? AND user_id=? AND status='open'",(fields.get('id',''),uid))
    elif action=='stage':
        stage=fields.get('stage','')
        if stage not in ('lead','contacted','qualified','won','lost'): raise ValueError('Invalid CRM stage.')
        c.execute('UPDATE vx3_contacts SET stage=? WHERE id=? AND user_id=?',(stage,fields.get('id',''),uid))
    else: raise ValueError('Unknown action.')

def render(c,uid,csrf):
    profile=c.execute('SELECT business_name,business_type FROM vx3_profiles WHERE user_id=?',(uid,)).fetchone()
    contacts=c.execute('SELECT id,name,email,stage FROM vx3_contacts WHERE user_id=? ORDER BY created_at DESC LIMIT 50',(uid,)).fetchall()
    entries=c.execute('SELECT kind,description,amount_cents,created_at FROM vx3_entries WHERE user_id=? ORDER BY created_at DESC LIMIT 50',(uid,)).fetchall()
    tasks=c.execute('SELECT id,title,status FROM vx3_tasks WHERE user_id=? ORDER BY created_at DESC LIMIT 50',(uid,)).fetchall()
    sums=dict(c.execute('SELECT kind,COALESCE(SUM(amount_cents),0) FROM vx3_entries WHERE user_id=? GROUP BY kind',(uid,)).fetchall())
    income=sums.get('income',0);expenses=sums.get('expense',0)
    fmt=lambda x:f'${x/100:,.2f}'
    stages=dict(c.execute('SELECT stage,COUNT(*) FROM vx3_contacts WHERE user_id=? GROUP BY stage',(uid,)).fetchall())
    stages={s:stages.get(s,0) for s in ('lead','contacted','qualified','won','lost')}
    total_contacts=c.execute('SELECT COUNT(*) FROM vx3_contacts WHERE user_id=?',(uid,)).fetchone()[0]
    open_tasks=c.execute("SELECT COUNT(*) FROM vx3_tasks WHERE user_id=? AND status='open'",(uid,)).fetchone()[0]
    token='<input type="hidden" name="csrf" value="'+e(csrf)+'">'
    typ=profile[1] if profile else 'small_business'
    options=''.join('<option value="'+e(x)+'"'+(' selected' if x==typ else '')+'>'+e(x.replace('_',' ').title())+'</option>' for x in MODULES)
    body='<section class="hero"><p class="eyebrow">VELXTRIA V3 / BUSINESS WORKSPACE</p><h1>'+e(profile[0] if profile else 'Your business command center')+'</h1><p>Private workspace · Manual entries and actionable summaries · No automatic messages or charges.</p></section>'
    body+='<section class="panel"><h2>Workspace settings</h2><form method="post" action="/workspace">'+token+'<input type="hidden" name="action" value="profile"><label>Business name<input name="business_name" maxlength="100" required value="'+e(profile[0] if profile else '')+'"></label><label>Business type<select name="business_type">'+options+'</select></label><button>Save workspace</button></form></section>'
    body+='<div class="stats"><div><b>'+fmt(income)+'</b><small>Recorded income</small></div><div><b>'+fmt(expenses)+'</b><small>Recorded expenses</small></div><div><b>'+fmt(income-expenses)+'</b><small>Net recorded cash flow (not profit)</small></div></div>'
    body+='<section class="panel"><h2>Intelligence</h2><p>'+str(total_contacts)+' total contacts · '+str(stages['qualified'])+' qualified · '+str(stages['won'])+' won · '+str(open_tasks)+' open tasks.</p><p>'+('Recorded expenses exceed income. Review your entries and cash needs.' if expenses>income else 'Recorded income covers recorded expenses so far; add complete records for a meaningful picture.')+'</p><p><small>Insights use manually entered records only. They are not forecasts or accounting advice. Tables display the 50 most recent items; summary counts include all records.</small></p></section>'
    body+='<section class="panel"><h2>CRM · Contacts and opportunities</h2><form method="post" action="/workspace">'+token+'<input type="hidden" name="action" value="contact"><label>Name<input name="name" maxlength="120" required></label><label>Email (optional)<input name="email" type="email" maxlength="254"></label><label>Stage<select name="stage"><option>lead</option><option>contacted</option><option>qualified</option><option>won</option><option>lost</option></select></label><button>Add contact</button></form><div class="scroll"><table><tr><th>Name</th><th>Email</th><th>Stage</th><th>Update</th></tr>'
    for cid,name,email,stage in contacts:
        opts=''.join('<option value="'+s+'"'+(' selected' if s==stage else '')+'>'+s.title()+'</option>' for s in stages)
        body+='<tr><td>'+e(name)+'</td><td>'+e(email)+'</td><td>'+e(stage)+'</td><td><form method="post" action="/workspace">'+token+'<input type="hidden" name="action" value="stage"><input type="hidden" name="id" value="'+e(cid)+'"><select name="stage">'+opts+'</select><button>Update</button></form></td></tr>'
    body+='</table></div></section>'
    body+='<section class="panel"><h2>Finance · Manual cash ledger</h2><p>Tracks recorded income and expenses; does not send invoices or move funds.</p><form method="post" action="/workspace">'+token+'<input type="hidden" name="action" value="entry"><label>Type<select name="kind"><option value="income">Income</option><option value="expense">Expense</option></select></label><label>Description<input name="description" maxlength="180" required></label><label>Amount (USD)<input name="amount" type="number" min="0.01" max="100000000" step="0.01" required></label><button>Record entry</button></form><div class="scroll"><table><tr><th>Date UTC</th><th>Type</th><th>Description</th><th>Amount</th></tr>'
    for kind,desc,cents,created in entries: body+='<tr><td>'+e(datetime.fromtimestamp(created,timezone.utc).strftime('%Y-%m-%d'))+'</td><td>'+e(kind)+'</td><td>'+e(desc)+'</td><td>'+fmt(cents)+'</td></tr>'
    body+='</table></div></section>'
    body+='<section class="panel"><h2>Automation · Task queue</h2><p>Safe foundation: create and complete follow-up tasks. No emails are sent automatically.</p><form method="post" action="/workspace">'+token+'<input type="hidden" name="action" value="task"><label>Next action<input name="title" maxlength="180" required placeholder="Follow up with customer"></label><button>Add task</button></form><div class="scroll"><table><tr><th>Task</th><th>Status</th><th>Action</th></tr>'
    for tid,title,status in tasks:
        action=('<form method="post" action="/workspace">'+token+'<input type="hidden" name="action" value="complete_task"><input type="hidden" name="id" value="'+e(tid)+'"><button>Complete</button></form>') if status=='open' else '—'
        body+='<tr><td>'+e(title)+'</td><td>'+e(status)+'</td><td>'+action+'</td></tr>'
    body+='</table></div></section>'
    return body
