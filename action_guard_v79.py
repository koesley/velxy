"""V79 fail-closed policy gate for proposed AI actions; no side effects."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

SENSITIVE = frozenset({'send_message', 'issue_refund', 'delete_record', 'change_permissions', 'transfer_funds'})
ALLOWED = SENSITIVE | frozenset({'draft_message', 'summarize', 'classify'})

@dataclass(frozen=True)
class Proposal:
    workspace_id: str
    action: str
    amount_usd: str = '0'
    approval_id: str = ''

def evaluate(proposal, *, workspace_id, paused=True, approved_ids=()):
    """Return a decision, never execute an action. Approval IDs require server verification."""
    if not isinstance(proposal, Proposal) or not isinstance(workspace_id, str) or not workspace_id.strip():
        raise ValueError('invalid proposal or workspace')
    if type(paused) is not bool:
        raise ValueError('paused must be boolean')
    if proposal.workspace_id != workspace_id:
        return {'decision': 'deny', 'reason': 'workspace_mismatch'}
    if proposal.action not in ALLOWED:
        return {'decision': 'deny', 'reason': 'unknown_action'}
    try:
        amount = Decimal(proposal.amount_usd)
    except (InvalidOperation, ValueError, TypeError):
        return {'decision': 'deny', 'reason': 'invalid_amount'}
    if not amount.is_finite() or amount < 0:
        return {'decision': 'deny', 'reason': 'invalid_amount'}
    if paused:
        return {'decision': 'deny', 'reason': 'automation_paused'}
    if proposal.action in SENSITIVE or amount > 0:
        if not proposal.approval_id or proposal.approval_id not in approved_ids:
            return {'decision': 'review', 'reason': 'human_approval_required'}
    return {'decision': 'allow', 'reason': 'policy_satisfied'}
