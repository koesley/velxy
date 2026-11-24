"""Offline evaluation of two randomized groups with binary outcomes.

Inputs must be independently randomized, unique eligible units with complete
follow-up and the same outcome definition. This module cannot verify design.
No automatic deployment, causal guarantee, or revenue forecast.
"""
import math


def _wilson(successes, total):
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z*z/total
    center = (p + z*z/(2*total))/denominator
    radius = z*math.sqrt(p*(1-p)/total + z*z/(4*total*total))/denominator
    return max(0., center-radius), min(1., center+radius)


def evaluate(control_success, control_total, treatment_success, treatment_total):
    """Return observed lift and approximate Newcombe 95% difference interval.

    Minimum 30 units per arm is a conservative display gate, not a power test.
    No optional stopping or multiple-comparison adjustment is implemented.
    """
    for successes, total in ((control_success, control_total), (treatment_success, treatment_total)):
        if type(successes) is not int or type(total) is not int or not 0 <= successes <= total <= 10**9:
            raise ValueError('Invalid group counts')
    if min(control_total, treatment_total) < 30:
        return {'status': 'insufficient_data', 'control_total': control_total, 'treatment_total': treatment_total}
    c = control_success/control_total
    t = treatment_success/treatment_total
    cl, cu = _wilson(control_success, control_total)
    tl, tu = _wilson(treatment_success, treatment_total)
    delta = t-c
    low = max(-1., delta-math.hypot(t-tl, cu-c))
    high = min(1., delta+math.hypot(tu-t, c-cl))
    return {'status': 'evaluated', 'control_rate': c, 'treatment_rate': t,
            'absolute_lift': delta, 'interval_95': (low, high),
            'signal': 'positive' if low > 0 else 'negative' if high < 0 else 'inconclusive',
            'requires_review': True,
            'limitations': 'Assumes independent randomized groups and complete follow-up; no automatic action.'}
