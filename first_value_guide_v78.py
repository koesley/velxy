"""V78: deterministic first-value guidance; no external side effects."""
from dataclasses import dataclass

GOALS = {
    "recover_sales": ("Import or add one lead", "Review one stalled opportunity", "Record a verified recovery outcome"),
    "save_time": ("Choose a repetitive task", "Create a draft workflow", "Run an approved workflow and verify the result"),
    "understand_business": ("Connect or import business records", "Review an evidence-backed insight", "Save a decision with supporting evidence"),
}

@dataclass(frozen=True)
class Milestone:
    key: str
    completed: bool
    verified: bool = False

def guide(goal, milestones):
    """Self-reported completion does not prove first value."""
    if goal not in GOALS:
        raise ValueError("Unsupported goal")
    if not isinstance(milestones, (list, tuple)):
        raise ValueError("Milestones must be a list or tuple")
    if len(milestones) > 20:
        raise ValueError("Too many milestones")
    seen = set()
    states = {}
    for item in milestones:
        if not isinstance(item, Milestone) or not isinstance(item.key, str):
            raise ValueError("Invalid milestone")
        if item.key in seen or item.key not in ("step_1", "step_2", "step_3"):
            raise ValueError("Duplicate or unknown milestone")
        if type(item.completed) is not bool or type(item.verified) is not bool:
            raise ValueError("Invalid milestone flags")
        seen.add(item.key)
        states[item.key] = item
    progress = []
    for i, label in enumerate(GOALS[goal], 1):
        state = states.get(f"step_{i}", Milestone(f"step_{i}", False))
        progress.append({"key": f"step_{i}", "label": label, "completed": state.completed,
                         "verified": state.completed and state.verified})
    next_step = next((s for s in progress if not s["completed"]), None)
    return {"goal": goal, "steps": progress,
            "next_action": next_step["label"] if next_step else None,
            "completed_steps": sum(s["completed"] for s in progress),
            "first_value_verified": all(s["verified"] for s in progress),
            "notice": "Verification must come from authenticated, independently checked outcome records."}
