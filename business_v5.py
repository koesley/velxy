"""VELXTRIA V5: server-rendered analytics, deal pipeline, and safe internal automations."""
import html, secrets, time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

def e(x): return html.escape(str(x), quote=True)
def cash(c): return '${:,.2f}'.format(c/100)
def token(csrf): return '<input type="hidden" name="csrf" value="'+e(csrf)+'">'
def setup(c):
    import persistent
    if persistent.REMOTE: c.execute('SELECT pg_advisory_xact_lock(731245, 921037)')
    c.execute('''CREATE TABLE IF NOT EXISTS vx5_deals(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,contact_id TEXT NOT NULL,title TEXT NOT NULL,value_cents INTEGER NOT NULL,stage TEXT NOT NULL,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS vx5_rules(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,kind TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,created_at INTEGER NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS vx5_audit(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,rule_id TEXT NOT NULL,object_id TEXT NOT NULL,event TEXT NOT NULL,created_at INTEGER NOT NULL,UNIQUE(user_id,rule_id,object_id,event))''')
    c.execute('CREATE INDEX IF NOT EXISTS vx5_deals_user ON vx5_deals(user_id,stage)')
    c.execute('CREATE INDEX IF NOT EXISTS vx5_rules_user ON vx5_rules(user_id)')

def process(c,uid,f):
    action=f.get('action','')
    if action=='v5_deal_create':
        cid=f.get('contact_id','');title=f.get('title','').strip();stage=f.get('stage','lead')
        if not c.execute('SELECT 1 FROM vx3_contacts WHERE id=? AND user_id=?',(cid,uid)).fetchone(): raise ValueError('Choose a customer from your CRM.')
        if not 1<=len(title)<=120 or stage not in ('lead','contacted','qualified','won','lost'): raise ValueError('Invalid deal.')
        try:
            value=Decimal(f.get('value',''))
            if not value.is_finite() or value<0 or value>100000000 or value.as_tuple().exponent < -2: raise ValueError()
        except (InvalidOperation,ValueError): raise ValueError('Enter a valid deal value (USD).')
        ts=int(time.time())
        c.execute('INSERT INTO vx5_deals VALUES (?,?,?,?,?,?,?,?)',(secrets.token_hex(16),uid,cid,title,int(value*100),stage,ts,ts))
    elif action=='v5_deal_stage':
        stage=f.get('stage','')
        if stage not in ('lead','contacted','qualified','won','lost'): raise ValueError('Invalid stage.')
        c.execute('UPDATE vx5_deals SET stage=?,updated_at=? WHERE id=? AND user_id=?',(stage,int(time.time()),f.get('id',''),uid))
    elif action=='v5_rule_add':
        kind=f.get('kind','')
        if kind not in ('overdue_invoice','qualified_deal'): raise ValueError('Invalid rule.')
        if not c.execute('SELECT 1 FROM vx5_rules WHERE user_id=? AND kind=?',(uid,kind)).fetchone():
            c.execute('INSERT INTO vx5_rules VALUES (?,?,?,?,?)',(secrets.token_hex(16),uid,kind,1,int(time.time())))
    elif action=='v5_rule_toggle':
        row=c.execute('SELECT enabled FROM vx5_rules WHERE id=? AND user_id=?',(f.get('id',''),uid)).fetchone()
        if not row: raise ValueError('Rule not found.')
        c.execute('UPDATE vx5_rules SET enabled=? WHERE id=? AND user_id=?',(0 if row[0] else 1,f.get('id',''),uid))
    elif action=='v5_run':
        ts=int(time.time())
        rules=c.execute('SELECT id,kind FROM vx5_rules WHERE user_id=? AND enabled=1',(uid,)).fetchall()
        for rid,kind in rules:
            if kind=='overdue_invoice':
                rows=c.execute("SELECT id,description FROM vx4_invoices WHERE user_id=? AND status='issued' AND due_at<?",(uid,ts)).fetchall()
            else:
                rows=c.execute("SELECT id,title FROM vx5_deals WHERE user_id=? AND stage='qualified'",(uid,)).fetchall()
            for oid,title in rows:
                if c.execute('SELECT 1 FROM vx5_audit WHERE user_id=? AND rule_id=? AND object_id=? AND event=?',(uid,rid,oid,'task_created')).fetchone(): continue
                task='Review overdue invoice: '+title if kind=='overdue_invoice' else 'Follow up on qualified deal: '+title
                c.execute('INSERT INTO vx3_tasks(id,user_id,title,status,created_at) VALUES (?,?,?,?,?)',(secrets.token_hex(16),uid,task[:180],'open',ts))
                c.execute('INSERT INTO vx5_audit VALUES (?,?,?,?,?,?)',(secrets.token_hex(16),uid,rid,oid,'task_created',ts))
    else: raise ValueError('Unknown V5 action.')

def render(c,uid,csrf):
    ts=int(time.time()); t=token(csrf)
    entries=c.execute('SELECT kind,amount_cents,created_at FROM vx3_entries WHERE user_id=? AND created_at>=?',(uid,ts-180*86400)).fetchall()
    buckets={}
    for kind,amount,created in entries:
        month=datetime.fromtimestamp(created,timezone.utc).strftime('%Y-%m')
        if month not in buckets:buckets[month]={'income':0,'expense':0}
        buckets[month][kind]+=amount
    months=[]
    nowdate=datetime.fromtimestamp(ts,timezone.utc)
    for offset in range(5,-1,-1):
        y=nowdate.year; m=nowdate.month-offset
        while m<=0:y-=1;m+=12
        months.append(f'{y:04d}-{m:02d}')
    maxv=max([buckets.get(m,{}).get(k,0) for m in months for k in ('income','expense')]+[1])
    contacts=c.execute('SELECT id,name FROM vx3_contacts WHERE user_id=? ORDER BY created_at DESC LIMIT 200',(uid,)).fetchall()
    deals=c.execute('SELECT d.id,d.title,d.value_cents,d.stage,c.name FROM vx5_deals d JOIN vx3_contacts c ON c.id=d.contact_id AND c.user_id=d.user_id WHERE d.user_id=? ORDER BY d.updated_at DESC LIMIT 100',(uid,)).fetchall()
    total=c.execute('SELECT COUNT(*),COALESCE(SUM(value_cents),0) FROM vx5_deals WHERE user_id=? AND stage NOT IN (\'won\',\'lost\')',(uid,)).fetchone()
    overdue=c.execute("SELECT COUNT(*),COALESCE(SUM(amount_cents),0) FROM vx4_invoices WHERE user_id=? AND status='issued' AND due_at<?",(uid,ts)).fetchone()
    tasks=c.execute("SELECT COUNT(*) FROM vx3_tasks WHERE user_id=? AND status='open'",(uid,)).fetchone()[0]
    rules=c.execute('SELECT id,kind,enabled FROM vx5_rules WHERE user_id=? ORDER BY created_at',(uid,)).fetchall()
    audit=c.execute('SELECT event,created_at FROM vx5_audit WHERE user_id=? ORDER BY created_at DESC LIMIT 12',(uid,)).fetchall()
    body='<div class="vx5"><section class="vx5-head"><span class="vx5-kicker">VELXTRIA / V5 INTELLIGENCE</span><h1>Executive Command Center</h1><p>Connected reporting, opportunity management and controlled internal workflows.</p></section>'
    body+='<div class="vx5-metrics"><div><small>Open pipeline</small><strong>'+cash(total[1])+'</strong><span>'+str(total[0])+' active deals</span></div><div><small>Overdue invoices</small><strong>'+cash(overdue[1])+'</strong><span>'+str(overdue[0])+' need attention</span></div><div><small>Open tasks</small><strong>'+str(tasks)+'</strong><span>Across your workspace</span></div></div>'
    body+='<section class="vx5-panel"><h2>Revenue activity <small>Last 6 calendar months · manually recorded USD</small></h2><div class="vx5-legend"><span>● Income</span> <span>● Expenses</span></div><div class="vx5-chart">'
    for month in months:
        vals=buckets.get(month,{}); inc=vals.get('income',0); exp=vals.get('expense',0)
        body+='<div class="vx5-month"><div class="vx5-bars"><div class="vx5-bar-income" style="height:'+str(max(2,round(100*inc/maxv)))+'%" title="Income '+e(cash(inc))+'"></div><div class="vx5-bar-expense" style="height:'+str(max(2,round(100*exp/maxv)))+'%" title="Expenses '+e(cash(exp))+'"></div></div><small>'+e(month[5:])+'/'+e(month[2:4])+'</small></div>'
    body+='</div><p class="vx5-muted">Hover over bars for values. This chart reflects manual ledger entries, not verified bank balances.</p></section>'
    insights=[]
    if overdue[0]:insights.append(('HIGH','You have '+str(overdue[0])+' overdue issued invoices totaling '+cash(overdue[1])+'. Review payment status before following up.'))
    if total[0]:insights.append(('PIPELINE',str(total[0])+' active opportunities represent '+cash(total[1])+' in potential deals, not guaranteed revenue.'))
    if tasks:insights.append(('TASKS',str(tasks)+' tasks are open. Prioritize overdue customer commitments.'))
    if not insights:insights.append(('GET STARTED','Add contacts, deals and invoices to unlock data-backed recommendations.'))
    body+='<section class="vx5-panel"><h2>VELXTRIA Brain <small>Explainable rules · no paid AI API</small></h2><div class="vx5-insights">'
    for severity,desc in insights:body+='<article><b>'+e(severity)+'</b><p>'+e(desc)+'</p></article>'
    body+='</div></section>'
    body+='<section class="vx5-panel"><h2>Sales Pipeline</h2><form class="vx5-form" method="post" action="/workspace">'+t+'<input type="hidden" name="action" value="v5_deal_create"><label>Contact<select name="contact_id" required><option value="">Select contact</option>'
    for cid,name in contacts:body+='<option value="'+e(cid)+'">'+e(name)+'</option>'
    body+='</select></label><label>Deal name<input name="title" maxlength="120" required placeholder="Website redesign"></label><label>Value (USD)<input name="value" type="number" min="0" step="0.01" required></label><label>Stage<select name="stage">'
    for stage in ('lead','contacted','qualified','won','lost'):body+='<option value="'+stage+'">'+stage.title()+'</option>'
    body+='</select></label><button>Add opportunity</button></form><div class="vx5-pipeline">'
    for stage in ('lead','contacted','qualified','won','lost'):
        matches=[d for d in deals if d[3]==stage]
        body+='<div class="vx5-lane"><h3>'+stage.title()+' <small>'+str(len(matches))+'</small></h3>'
        for did,title,value,_,name in matches:
            body+='<article><b>'+e(title)+'</b><small>'+e(name)+'</small><strong>'+cash(value)+'</strong><form method="post" action="/workspace">'+t+'<input type="hidden" name="action" value="v5_deal_stage"><input type="hidden" name="id" value="'+e(did)+'"><select name="stage">'
            for target in ('lead','contacted','qualified','won','lost'):body+='<option value="'+target+'"'+(' selected' if target==stage else '')+'>'+target.title()+'</option>'
            body+='</select><button>Move</button></form></article>'
        if not matches:body+='<p class="vx5-muted">No deals yet</p>'
        body+='</div>'
    body+='</div></section>'
    body+='<section class="vx5-panel"><h2>Automation Studio <small>Manual execution · internal tasks only</small></h2><form class="vx5-form" method="post" action="/workspace">'+t+'<input type="hidden" name="action" value="v5_rule_add"><label>New workflow<select name="kind"><option value="overdue_invoice">Overdue invoice → create task</option><option value="qualified_deal">Qualified deal → create follow-up task</option></select></label><button>Add rule</button></form>'
    for rid,kind,enabled in rules:
        body+='<div class="vx5-rule"><span>'+e(kind.replace('_',' ').title())+' <small>'+('Enabled' if enabled else 'Paused')+'</small></span><form method="post" action="/workspace">'+t+'<input type="hidden" name="action" value="v5_rule_toggle"><input type="hidden" name="id" value="'+e(rid)+'"><button>'+('Pause' if enabled else 'Enable')+'</button></form></div>'
    body+='<form method="post" action="/workspace">'+t+'<input type="hidden" name="action" value="v5_run"><button>Run enabled workflows now</button></form><p class="vx5-muted">Re-running a rule does not create a second task for the same matching item. No messages, charges or external requests are sent.</p><h3>Recent workflow activity</h3>'
    for event,created in audit:body+='<p class="vx5-log">'+e(datetime.fromtimestamp(created,timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))+' · '+e(event.replace('_',' '))+'</p>'
    if not audit:body+='<p class="vx5-muted">No workflow activity yet.</p>'
    body+='</section><section class="vx5-panel"><h2>Invoice & Proposal Studio</h2><p>Use the connected V4 invoice creator below. Draft, issue and mark invoices paid after independent verification. Printable branded invoice and proposal exports are planned, not yet included.</p></section></div>'
    return body
