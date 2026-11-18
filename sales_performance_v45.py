"""V45 read-only, workspace-scoped sales performance and follow-up intelligence.

Metrics are descriptive, based on manually recorded tasks, not verified revenue.
"""
from collections import Counter,defaultdict
from datetime import date
import html,urllib.parse
import business_os_v59 as bos
import sales_execution_v44 as sales

CLOSED=frozenset(("won","lost"))
def analyze(c,uid,wid,today=None):
 bos.core.access(c,uid,wid)
 sales.setup(c)
 today=today or date.today().isoformat()
 date.fromisoformat(today)
 # Aggregate across the full workspace, not the capped 200-item display queue.
 rows=c.execute("""SELECT a.id,a.owner_id,a.action_kind,a.due,a.stage,
 p.id,p.title,a.contact_label,a.summary,a.created
 FROM vx_sales_actions44 a JOIN vx_growth_strategy42 p
 ON p.id=a.plan_id AND p.workspace_id=a.workspace_id
 WHERE a.workspace_id=? ORDER BY a.due,a.created,a.id""",(wid,)).fetchall()
 stages=Counter(r[4] for r in rows)
 by_plan=defaultdict(lambda:{"total":0,"open":0,"won":0,"lost":0,"overdue":0})
 by_owner=defaultdict(lambda:{"total":0,"open":0,"overdue":0,"due_today":0})
 due=[]
 for identifier,owner,kind,due_date,stage,plan_id,plan,contact,summary,created in rows:
  active=stage not in CLOSED
  overdue=active and due_date<today
  current=active and due_date==today
  ps=by_plan[(plan_id,plan)];ps["total"]+=1;ps["open"]+=int(active);ps["won"]+=int(stage=="won");ps["lost"]+=int(stage=="lost");ps["overdue"]+=int(overdue)
  os=by_owner[owner];os["total"]+=1;os["open"]+=int(active);os["overdue"]+=int(overdue);os["due_today"]+=int(current)
  if active and due_date<=today:
   due.append({"id":identifier,"owner":owner,"contact":contact,"kind":kind,"due":due_date,"stage":stage,"plan":plan,"summary":summary,"overdue":overdue})
 count=len(rows);closed=stages["won"]+stages["lost"]
 return {"total":count,"stages":dict(stages),"open":count-closed,"closed":closed,
         "won_marked":stages["won"],"lost_marked":stages["lost"],
         "overdue":sum(v["overdue"] for v in by_owner.values()),
         "due_today":sum(v["due_today"] for v in by_owner.values()),
         "owners":sorted(by_owner.items(),key=lambda x:(-x[1]["overdue"],-x[1]["open"],x[0])),
         "plans":sorted(by_plan.items(),key=lambda x:(-x[1]["overdue"],-x[1]["open"],x[0][1])),
         "attention":due[:50],
         "attention_total":len(due),
         "close_rate":round(100*closed/count,1) if count else None,
         "won_share_of_closed":round(100*stages["won"]/closed,1) if closed else None}

def render(c,uid,wid):
 d=analyze(c,uid,wid);e=lambda v:html.escape(str(v),quote=True)
 w=urllib.parse.quote(wid,safe="")
 out=['<section class="panel"><h1>Sales Performance & Follow-up Intelligence</h1>',
 '<p>Workspace-wide, read-only operational metrics from manually entered follow-up actions. '
 'Won/lost statuses are self-reported labels, not verified purchases or revenue. '
 'Multiple actions may refer to one customer; these are action counts, not unique customers. '
 'No emails, calls, payments, or CRM changes are performed here.</p>',
 '<p>Actions: '+str(d["total"])+' · Open: '+str(d["open"])+' · Overdue: '+str(d["overdue"])+
 ' · Due today: '+str(d["due_today"])+' · Won-marked: '+str(d["won_marked"])+
 ' · Lost-marked: '+str(d["lost_marked"])+'</p>',
 '<p>Closed-action share: '+(str(d["close_rate"])+'%' if d["close_rate"] is not None else 'Not available')+
 ' · Won share of closed actions: '+(str(d["won_share_of_closed"])+'%' if d["won_share_of_closed"] is not None else 'Not available')+'</p>',
 '<p><a href="/sales-execution?w='+w+'">Manage follow-ups</a></p></section>',
 '<section class="panel"><h2>Attention queue</h2><p>'+str(d["attention_total"])+
 ' open actions due today or overdue; showing first '+str(len(d["attention"]))+'.</p>']
 for item in d["attention"]:
  out.append('<p><strong>'+e(item["contact"])+'</strong> · '+e(item["kind"])+
   ' · '+('Overdue' if item["overdue"] else 'Due today')+' ('+e(item["due"])+') · owner #'+
   str(item["owner"])+' · '+e(item["plan"])+' · '+e(item["summary"])+'</p>')
 if not d["attention"]:out.append('<p>No overdue or due-today actions recorded.</p>')
 out.append('</section><section class="panel"><h2>Strategy outcomes</h2>')
 for (pid,name),v in d["plans"][:50]:
  out.append('<p><strong>'+e(name)+'</strong> — '+str(v["total"])+' actions; '+
   str(v["open"])+' open; '+str(v["overdue"])+' overdue; '+str(v["won"])+
   ' won-marked; '+str(v["lost"])+' lost-marked</p>')
 if not d["plans"]:out.append('<p>No linked sales actions yet.</p>')
 out.append('</section><section class="panel"><h2>Owner workload</h2>')
 for owner,v in d["owners"][:50]:
  out.append('<p>Member #'+str(owner)+': '+str(v["open"])+' open; '+
   str(v["overdue"])+' overdue; '+str(v["due_today"])+' due today</p>')
 if not d["owners"]:out.append('<p>No owner workloads recorded.</p>')
 out.append('</section>')
 if d["overdue"]:out.append('<section class="panel"><h2>Recommended next action</h2><p>Review overdue follow-ups, starting with the oldest due dates. Assignments and customer communication require deliberate human action in the Sales Execution Queue.</p></section>')
 elif d["total"] and not d["closed"]:out.append('<section class="panel"><h2>Recommended next action</h2><p>Review open tasks and record evidence of actual customer responses before interpreting conversion performance.</p></section>')
 elif not d["total"]:out.append('<section class="panel"><h2>Recommended next action</h2><p>Create a growth strategy and its first customer follow-up to begin tracking execution.</p></section>')
 return ''.join(out)
