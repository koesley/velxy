"""Actionable goal-gap coverage using existing ranked pipeline opportunities."""
import html
import urllib.parse
from decimal import Decimal, InvalidOperation
import business_os_v59 as bos
import revenue_goals_v27 as goals
import revenue_priority_live as priorities


def plan(c, uid, wid):
    bos.core.access(c, uid, wid)
    goal = goals.snapshot(c, uid, wid)
    gap = goal["gap"]
    ranked = priorities.live_rankings(c, uid, wid, limit=50)
    if gap is None:
        return {"goal":goal,"candidates":[],"covered":Decimal(0),
                "remaining":None,"eligible_count":len(ranked)}
    remaining=gap
    candidates=[]
    covered=Decimal(0)
    if remaining>0:
        for item in ranked:
            try:
                amount=Decimal(str(item["estimated_value"]))
            except (InvalidOperation,ValueError,TypeError):
                continue
            if not amount.is_finite() or amount<=0:
                continue
            candidates.append(item)
            covered+=amount
            remaining=max(Decimal(0),gap-covered)
            if remaining==0:
                break
    return {"goal":goal,"candidates":candidates,"covered":covered,
            "remaining":remaining,"eligible_count":len(ranked)}


def render(c,uid,wid):
    result=plan(c,uid,wid)
    goal=result["goal"]
    esc=lambda v:html.escape(str(v),quote=True)
    money=lambda v:"$"+format(v,",.2f")
    w=urllib.parse.quote(wid,safe="")
    out=['<section class="panel"><h1>Revenue Gap Action Plan</h1>',
         '<p>Illustrative opportunity coverage based on manually entered lead values. '
         'Not a revenue forecast: winning leads, payment collection, and conversion '
         'rates are not verified. Ranking is heuristic and no actions are executed.</p>',
         '<p><a href="/revenue-goals?w='+w+'">Edit pipeline goal</a> · '
         '<a href="/revenue-priority/live?w='+w+'">Review lead priorities</a></p></section>']
    if goal["target"] is None:
        out.append('<section class="panel"><p>Set a cumulative pipeline goal first to '
                   'generate an action plan.</p></section>')
        return ''.join(out)
    out.append('<section class="panel"><h2>Gap-to-target</h2><p>Goal: '+
               money(goal["target"])+' · Won-marked: '+money(goal["won_marked"])+
               ' · Gap: '+money(goal["gap"])+'</p>')
    if goal["gap"]==0:
        out.append('<p>Your won-marked pipeline meets this goal. This does not confirm '
                   'collected revenue.</p></section>')
        return ''.join(out)
    out.append('<p>Selected opportunity potential: '+money(result["covered"])+
               ' · Gap not covered by selected estimates: '+money(result["remaining"])+
               '</p><p>Selected in existing priority order until estimated values '
               'cover the gap, or the top 50 eligible leads are exhausted. '
               'Potential coverage is not expected revenue.</p></section>')
    if not result["candidates"]:
        out.append('<section class="panel"><p>No eligible ranked open leads. '
                   'Add or qualify leads in Business OS.</p></section>')
    for i,item in enumerate(result["candidates"],1):
        out.append('<section class="panel"><h2>'+str(i)+'. '+esc(item["title"])+
                   '</h2><p>Estimated value: '+money(Decimal(str(item["estimated_value"])))+
                   ' · Priority score: '+esc(item["priority_score"])+
                   '</p><p>'+esc(item["evidence"])+'</p>'
                   '<p><a href="/revenue-priority/live?w='+w+
                   '">Review and create approval-controlled draft</a></p></section>')
    return ''.join(out)
