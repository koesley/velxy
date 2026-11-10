"""VELXTRIA V5 local operator: tenant-scoped observation, proposed tasks and approval-gated execution."""
import html, secrets, time

def esc(v): return html.escape(str(v), quote=True)
def setup(c):
    c.execute('''CREATE TABLE IF NOT EXISTS vx5_proposals (id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL, evidence TEXT NOT NULL, status TEXT NOT NULL, created_at INTEGER NOT NULL, decided_at INTEGER NOT NULL DEFAULT 0, task_id TEXT, FOREIGN KEY(user_id) REFERENCES users(id))''')
    c.execute('CREATE INDEX IF NOT EXISTS vx5_proposals_user ON vx5_proposals(user_id,created_at)')
    c.execute('''CREATE TABLE IF NOT EXISTS vx5_audit (id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, proposal_id TEXT, event TEXT NOT NULL, created_at INTEGER NOT NULL)''')
    c.execute('CREATE INDEX IF NOT EXISTS vx5_audit_user ON vx5_audit(user_id,created_at)')
    c.execute('''CREATE TABLE IF NOT EXISTS vx51_executions (id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, proposal_id TEXT NOT NULL, action_type TEXT NOT NULL, target_id TEXT NOT NULL, result TEXT NOT NULL, created_at INTEGER NOT NULL, UNIQUE(user_id,proposal_id,action_type,target_id))''')
    c.execute('CREATE INDEX IF NOT EXISTS vx51_executions_user ON vx51_executions(user_id,created_at)')

def log(c,uid,pid,event):
    c.execute('INSERT INTO vx5_audit(id,user_id,proposal_id,event,created_at) VALUES (?,?,?,?,?)',(secrets.token_hex(16),uid,pid,event,int(time.time())))

def candidates(c,uid):
    now=int(time.time()); recent=now-30*86400
    result=[]
    overdue=c.execute("SELECT COUNT(*),COALESCE(SUM(amount_cents),0) FROM vx4_invoices WHERE user_id=? AND status='issued' AND due_at<?",(uid,now)).fetchone()
    if overdue[0]: result.append(('overdue','Review overdue invoices',f'{overdue[0]} issued invoices are overdue; recorded amount ${overdue[1]/100:,.2f}. Verify payment status before contacting customers.'))
    leads=c.execute("SELECT COUNT(*) FROM vx3_contacts WHERE user_id=? AND stage IN ('lead','qualified')",(uid,)).fetchone()[0]
    if leads: result.append(('leads','Review qualified and new leads',f'{leads} lead/qualified contacts in CRM. Verify consent and prioritize suitable follow-ups.'))
    rows=c.execute('SELECT kind,amount_cents FROM vx3_entries WHERE user_id=? AND created_at>=?',(uid,recent)).fetchall()
    inc=sum(v for k,v in rows if k=='income'); exp=sum(v for k,v in rows if k=='expense')
    if rows and exp>inc: result.append(('cashflow','Review negative recorded cash flow',f'Last 30 days: recorded income ${inc/100:,.2f}; expenses ${exp/100:,.2f}. Difference ${((inc-exp)/100):,.2f}. This is not an accounting profit figure.'))
    if not rows: result.append(('records','Complete business records', 'No income or expense entries in the past 30 days. Enter accurate transactions before relying on financial analysis.'))
    return result

def scan(c,uid):
    made=0
    for kind,title,evidence in candidates(c,uid):
        # Only one pending proposal per category; do not generate duplicates on refresh.
        existing=c.execute("SELECT 1 FROM vx5_proposals WHERE user_id=? AND kind=? AND status='pending'",(uid,kind)).fetchone()
        if existing:continue
        ident=secrets.token_hex(16)
        c.execute('INSERT INTO vx5_proposals(id,user_id,kind,title,evidence,status,created_at) VALUES (?,?,?,?,?,?,?)',(ident,uid,kind,title,evidence,'pending',int(time.time())))
        log(c,uid,ident,'proposed');made+=1
    log(c,uid,None,'scan_completed')
    return made

def decide(c,uid,pid,decision):
    row=c.execute('SELECT title,status FROM vx5_proposals WHERE id=? AND user_id=?',(pid,uid)).fetchone()
    if not row or row[1]!='pending':raise ValueError('Proposal not found or already reviewed.')
    if decision not in ('approve','reject'):raise ValueError('Invalid decision.')
    task_id=None
    if decision=='approve':
        task_id=secrets.token_hex(16)
        c.execute('INSERT INTO vx3_tasks(id,user_id,title,status,created_at) VALUES (?,?,?,?,?)',(task_id,uid,'Operator: '+row[0],'open',int(time.time())))
    c.execute('UPDATE vx5_proposals SET status=?,decided_at=?,task_id=? WHERE id=? AND user_id=? AND status=?',('approved' if decision=='approve' else 'rejected',int(time.time()),task_id,pid,uid,'pending'))
    log(c,uid,pid,'approved_task_created' if decision=='approve' else 'rejected')

def execute(c,uid,pid):
    """Perform approved, internal-only, idempotent operational work.

    No customer contact, invoice mutation, website publishing, or external calls.
    """
    row=c.execute('SELECT kind,status FROM vx5_proposals WHERE id=? AND user_id=?',(pid,uid)).fetchone()
    if not row or row[1]!='approved':raise ValueError('Approve this proposal before execution.')
    kind=row[0]
    if c.execute('SELECT 1 FROM vx51_executions WHERE user_id=? AND proposal_id=? LIMIT 1',(uid,pid)).fetchone():
        raise ValueError('This proposal was already executed. Run a new check for fresh work.')
    items=[]
    if kind=='leads':
        contacts=c.execute("SELECT id,name,email,stage FROM vx3_contacts WHERE user_id=? AND stage IN ('lead','qualified') ORDER BY created_at DESC LIMIT 25",(uid,)).fetchall()
        for cid,name,email,stage in contacts:
            title='Review '+stage+' lead: '+name
            note='Draft for internal review only: confirm consent and appropriate next steps for '+name+'. No message has been sent.'
            items.append(('crm_followup',cid,title,note))
    elif kind=='overdue':
        invoices=c.execute("SELECT id,description,amount_cents FROM vx4_invoices WHERE user_id=? AND status='issued' AND due_at<? ORDER BY due_at LIMIT 25",(uid,int(time.time()))).fetchall()
        for iid,desc,amount in invoices:
            title='Verify overdue invoice: '+desc[:95]
            note=f'Internal review: verify payment status and ${amount/100:,.2f} balance before any reminder. No customer was contacted.'
            items.append(('invoice_review',iid,title,note))
    elif kind in ('records','cashflow'):
        title='Reconcile business cash records' if kind=='records' else 'Review recorded cash flow and expenses'
        note='Internal checklist: verify entry dates, amounts, missing transactions, duplicates and categories. No ledger values were changed.'
        items.append(('financial_review','account',title,note))
    else:raise ValueError('Unsupported proposal category.')
    if not items:raise ValueError('No eligible records remain. Run a fresh analysis.')
    count=0
    for action_type,target,title,note in items:
        task_id=secrets.token_hex(16)
        c.execute('INSERT INTO vx3_tasks(id,user_id,title,status,created_at) VALUES (?,?,?,?,?)',(task_id,uid,'Operator: '+title[:160],'open',int(time.time())))
        c.execute('INSERT INTO vx51_executions(id,user_id,proposal_id,action_type,target_id,result,created_at) VALUES (?,?,?,?,?,?,?)',
                  (secrets.token_hex(16),uid,pid,action_type,target,note,int(time.time())))
        count+=1
    log(c,uid,pid,'executed_'+str(count)+'_internal_actions')
    return count

def render(c,uid,csrf):
    rows=c.execute('SELECT id,title,evidence,status,created_at FROM vx5_proposals WHERE user_id=? ORDER BY created_at DESC LIMIT 50',(uid,)).fetchall()
    audit=c.execute('SELECT event,created_at FROM vx5_audit WHERE user_id=? ORDER BY created_at DESC LIMIT 12',(uid,)).fetchall()
    executions=c.execute('SELECT proposal_id,action_type,result,created_at FROM vx51_executions WHERE user_id=? ORDER BY created_at DESC LIMIT 30',(uid,)).fetchall()
    executed={r[0] for r in c.execute('SELECT DISTINCT proposal_id FROM vx51_executions WHERE user_id=?',(uid,)).fetchall()}
    token='<input type="hidden" name="csrf" value="'+esc(csrf)+'">'
    parts=['<section class="hero"><p class="eyebrow">VELXTRIA V5.1 / PRIVATE OPERATOR</p><h1>Business Operator</h1><p>Analyze business records, approve proposed work, and execute internal follow-ups with a full activity trail. No external sends, purchases, publishing, or paid AI calls.</p></section>',
      '<section class="panel"><h2>Run an operational check</h2><p>Reads your company records and prepares evidence-backed task proposals. Scans are manual in this local prototype; no background agent is running.</p><form method="post" action="/operator">'+token+'<input type="hidden" name="action" value="scan"><button>Analyze records and prepare actions</button></form></section>',
      '<section class="panel"><h2>Proposed actions</h2>']
    if not rows:parts.append('<p>No proposals yet. Run a check to create proposals from the available records.</p>')
    for pid,title,evidence,status,created in rows:
        parts.append('<article class="proposal-card"><h3>'+esc(title)+'</h3><p>'+esc(evidence)+'</p><p><small>Status: '+esc('executed' if pid in executed else status)+'</small></p>')
        if status=='pending':
            parts.append('<div class="action-row">')
            for action,label in [('approve','Approve and create task'),('reject','Reject')]:
                parts.append('<form method="post" action="/operator">'+token+'<input type="hidden" name="action" value="'+action+'"><input type="hidden" name="proposal_id" value="'+esc(pid)+'"><button class="'+('secondary-button' if action=='reject' else '')+'">'+label+'</button></form>')
            parts.append('</div>')
        elif status=='approved' and pid not in executed:
            parts.append('<p><small>Approval created a task. You may now execute the related internal work. CRM and invoice actions create review tasks only; no messages are sent.</small></p><form method="post" action="/operator">'+token+'<input type="hidden" name="action" value="execute"><input type="hidden" name="proposal_id" value="'+esc(pid)+'"><button>Execute approved internal actions</button></form>')
        parts.append('</article>')
    parts.append('</section><section class="panel"><h2>Recent operator activity</h2><ul>')
    parts.extend('<li>'+esc(event)+' · '+time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(created))+'</li>' for event,created in audit)
    parts.append('</ul><p><small>Execution creates internal review tasks and checklists only. It does not contact customers or modify money, inventory, or public websites. This prototype uses the signed-in account as its data boundary.</small></p></section>')
    parts.append('<section class="panel"><h2>Executed work · verification log</h2><p>These entries record the internal work actually created. No external actions are implied.</p>')
    if not executions:parts.append('<p>No executed actions yet. Approve a proposal and choose Execute.</p>')
    else:
        parts.append('<div class="execution-list">')
        for pid,typ,result,created in executions:
            parts.append('<article class="execution-item"><strong>'+esc(typ.replace('_',' ').title())+'</strong><p>'+esc(result)+'</p><small>'+time.strftime('%Y-%m-%d %H:%M UTC',time.gmtime(created))+'</small></article>')
        parts.append('</div>')
    parts.append('</section>')
    return ''.join(parts)
