"""OMEGA V62: permission-gated, deterministic internal execution tools.

Runs only on active missions with explicitly approved tasks.
Never invokes shell, network, AI providers, publishing, email or payments.
"""
import html
import json
import secrets
import time
import omega_reasoning_v63
from omega_mission_v61 import check, record

TOOLS={
 "Strategy":("business_brief","Business strategy brief"),
 "Marketing":("landing_draft","Landing-page copy draft"),
 "Sales":("outreach_draft","Unsent outreach draft"),
 "Finance":("unit_economics","Illustrative unit economics"),
 "Operations":("roadmap","Milestone roadmap"),
 "Guardian":("risk_review","Permissions and risk review"),
}
def e(s):return html.escape(str(s),quote=True)
def produce(role,objective,title,description):
    """Pure generation; output is advisory and never executed externally."""
    prefix=f"Mission: {objective}\nTask: {title}\n"
    if role=="Strategy":
        return prefix+"Business brief\n- Identify ideal customers and their primary problem.\n- Define one measurable offer.\n- Interview prospects before committing resources.\n- Measure conversion and retention."
    if role=="Marketing":
        return prefix+"DRAFT ONLY — not published\nHeadline: A simpler way to solve your customer's problem\nSubheading: Explain your specific offer and measurable benefit.\nCTA: Request a consultation\nSections: problem, solution, proof, pricing, FAQ."
    if role=="Sales":
        return prefix+"UNSENT DRAFT — do not contact anyone automatically\nSubject: A question about your current workflow\nHello, I wanted to learn how your team handles this challenge. Would a short conversation be useful?\nRegards, Your team"
    if role=="Finance":
        return prefix+"Illustrative financial worksheet\nRevenue = customers × average price\nGross profit = revenue − direct costs\nBreak-even customers = fixed costs ÷ contribution margin per customer\nEnter verified figures before drawing conclusions."
    if role=="Operations":
        return prefix+"Roadmap\n1. Validate customer needs.\n2. Define deliverables and ownership.\n3. Build a small prototype.\n4. Test with permission.\n5. Review outcomes and revise."
    if role=="Guardian":
        return prefix+"Risk and permissions review\n- Verify data ownership and consent.\n- Require approval before publication, spending, or outreach.\n- Limit access by workspace.\n- Log changes and provide a rollback procedure."
    raise ValueError("Unsupported agent role")
def run(c,user,w,task_id,ai=False):
    check(c,user,w)
    row=c.execute(
      "SELECT t.id,t.mission,t.role,t.title,t.description,t.status,m.objective,m.status "
      "FROM v61_tasks t JOIN v61_missions m ON m.id=t.mission AND m.workspace=t.workspace "
      "WHERE t.id=? AND t.workspace=?",(task_id,w)).fetchone()
    if not row:raise ValueError("Task not found")
    tid,mid,role,title,description,status,objective,mission_status=row
    if mission_status!="active":raise ValueError("Mission must be active")
    if status!="approved":raise ValueError("Task requires explicit approval")
    if role not in TOOLS:raise ValueError("No permitted tool for role")
    tool=TOOLS[role][0]
    # Exactly one output per approved task. The transaction must commit atomically.
    if c.execute("SELECT 1 FROM v62_runs WHERE workspace=? AND task=? AND status='completed'",(w,tid)).fetchone():
        raise ValueError("Task already has a completed execution")
    if ai and not omega_reasoning_v63.enabled():raise ValueError('AI reasoning is not configured')
    output=(omega_reasoning_v63.generate(role,objective,title,description) if ai else produce(role,objective,title,description))
    if len(output)>12000:raise ValueError("Output limit exceeded")
    if ai:tool="ai_"+tool
    rid=secrets.token_hex(16)
    c.execute("INSERT INTO v62_runs(id,workspace,mission,task,tool,status,output,actor,created) VALUES (?,?,?,?,?,?,?,?,?)",
      (rid,w,mid,tid,tool,"completed",output,user,int(time.time())))
    record(c,w,mid,user,"internal_tool_completed",tool+" / "+tid)
    return rid
def render(c,user,w,csrf):
    check(c,user,w)
    hidden=f'<input type="hidden" name="csrf" value="{e(csrf)}"><input type="hidden" name="workspace" value="{e(w)}">'
    out=['<section class="hero"><h1>OMEGA V62 · Execution Engine</h1><p>Approved tasks generate internal drafts and reports. No external actions. Optional AI drafts may incur provider costs.</p></section>']
    rows=c.execute(
      "SELECT t.id,t.title,t.role,t.status,m.objective,m.status "
      "FROM v61_tasks t JOIN v61_missions m ON m.id=t.mission AND m.workspace=t.workspace "
      "WHERE t.workspace=? ORDER BY t.created DESC LIMIT 100",(w,)).fetchall()
    for tid,title,role,status,objective,mission_status in rows:
        out.append(f'<section class="panel"><h3>{e(role)} · {e(title)}</h3><p>{e(objective)} · Task: {e(status)} · Mission: {e(mission_status)}</p>')
        results=c.execute("SELECT tool,output FROM v62_runs WHERE workspace=? AND task=? ORDER BY created DESC LIMIT 3",(w,tid)).fetchall()
        if status=="approved" and mission_status=="active" and not results:
            out.append('<form method="post" action="/omega-execution-v62">'+hidden+f'<input type="hidden" name="task" value="{e(tid)}"><button>Run approved internal tool</button></form>')
        if status=="approved" and mission_status=="active" and not results and omega_reasoning_v63.enabled():
            out.append('<form method="post" action="/omega-execution-v62">'+hidden+f'<input type="hidden" name="task" value="{e(tid)}"><input type="hidden" name="ai" value="1"><button>Generate AI draft (API cost)</button></form>')
        for tool,output in results:out.append(f'<h4>{e(tool)}</h4><pre style="white-space:pre-wrap">{e(output)}</pre>')
        out.append('</section>')
    return "".join(out)
