"""VELXTRIA V4.5: read-only, tenant-scoped, explainable insights from manually entered records."""
import html,time

def e(v): return html.escape(str(v),quote=True)
def usd(c): return '${:,.2f}'.format(c/100)
def render(c,uid):
    rows=c.execute('SELECT kind,amount_cents,created_at FROM vx3_entries WHERE user_id=?',(uid,)).fetchall()
    now=int(time.time()); recent=now-30*86400; prior=now-60*86400
    def totals(start,end):
        selected=[r for r in rows if start<=r[2]<end]
        return sum(r[1] for r in selected if r[0]=='income'),sum(r[1] for r in selected if r[0]=='expense'),len(selected)
    income,expense,n=totals(recent,now+1); pi,pe,pn=totals(prior,recent)
    stages=dict(c.execute('SELECT stage,COUNT(*) FROM vx3_contacts WHERE user_id=? GROUP BY stage',(uid,)).fetchall())
    open_tasks=c.execute("SELECT COUNT(*) FROM vx3_tasks WHERE user_id=? AND status='open'",(uid,)).fetchone()[0]
    overdue=c.execute("SELECT COUNT(*),COALESCE(SUM(amount_cents),0) FROM vx4_invoices WHERE user_id=? AND status='issued' AND due_at<?",(uid,now)).fetchone()
    outstanding=c.execute("SELECT COALESCE(SUM(amount_cents),0) FROM vx4_invoices WHERE user_id=? AND status='issued'",(uid,)).fetchone()[0]
    suggestions=[]
    if n==0: suggestions.append(('Add business records','No income or expense entries in the past 30 days. Enter real transactions before using financial recommendations.'))
    else:
        if expense>income: suggestions.append(('Review cash outflows','Recorded expenses exceed income by '+usd(expense-income)+' over the past 30 days. Review expense entries for possible reductions; this is not a profit calculation.'))
        if expense>0: suggestions.append(('Review largest expense entries','Recorded expenses total '+usd(expense)+' in the past 30 days. Inspect the ledger for recurring or avoidable costs; the system cannot establish which costs are unnecessary.'))
        if pn>0 and pi>0 and income<pi: suggestions.append(('Investigate lower recorded income','Recorded income decreased '+str(round((pi-income)*100/pi,1))+'% versus the preceding 30 days ('+usd(pi)+' to '+usd(income)+'). Check record completeness before treating this as a sales decline.'))
    leads=stages.get('lead',0)+stages.get('qualified',0)
    if leads: suggestions.append(('Review potential customers',str(leads)+' contacts are marked lead or qualified. Review their status and consider appropriate follow-ups; no messages will be sent.'))
    if overdue[0]: suggestions.append(('Review overdue invoices',str(overdue[0])+' issued invoices totaling '+usd(overdue[1])+' are overdue based on recorded due dates. Verify status before following up.'))
    if open_tasks: suggestions.append(('Prioritize open tasks',str(open_tasks)+' tasks are open. Review them for time-sensitive opportunities.'))
    if not suggestions: suggestions.append(('Continue recording activity','No specific opportunity was detected from the available records. Add complete sales, cost, and customer information for stronger insights.'))
    items=''.join('<li><strong>'+e(t)+'</strong><p>'+e(d)+'</p></li>' for t,d in suggestions)
    return ('<section class="panel"><p class="eyebrow">VELXTRIA V4.5 / READ-ONLY INTELLIGENCE</p><h2>Business intelligence agent</h2>'
      '<p>Evidence-based suggestions from your manually entered records. No AI API, external calls, publishing, or automatic actions.</p>'
      '<div class="stats"><div><b>'+usd(income)+'</b><small>Recorded income · last 30 days</small></div><div><b>'+usd(expense)+'</b><small>Recorded expenses · last 30 days</small></div><div><b>'+usd(income-expense)+'</b><small>Net recorded cash flow · not profit</small></div></div>'
      '<p>Previous 30 days: income '+usd(pi)+'; expenses '+usd(pe)+'. Open issued invoices: '+usd(outstanding)+'.</p>'
      '<h3>Suggested next actions</h3><ol>'+items+'</ol>'
      '<p><small>Limitations: incomplete or duplicated records can distort insights. No margin, profitability, or sales forecasts are inferred without adequate data. All recommendations are informational and require human review.</small></p></section>')
