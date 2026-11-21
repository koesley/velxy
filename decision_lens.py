"""Evidence-backed Decision Lens for sales CSV reports.

Uses only aggregated monthly/product revenue and accepted/rejected counts.
No predictions, fabricated savings, customer PII, or external AI calls.
"""
from decimal import Decimal, InvalidOperation
from html import escape

MAX_ITEMS = 3


def _amount(value):
    try:
        number = Decimal(str(value).replace(',', '').replace('$', '').strip())
        return number if number.is_finite() and number >= 0 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _series(rows):
    if not isinstance(rows, (list, tuple)) or not rows:
        return []
    head = [str(cell).strip().lower() for cell in rows[0]]
    if not head or 'revenue' not in head:
        return []
    idx = head.index('revenue')
    output = []
    for row in rows[1:]:
        if not isinstance(row, (list, tuple)) or len(row) <= idx:
            continue
        amount = _amount(row[idx])
        if amount is not None and row and str(row[0]).strip():
            output.append((str(row[0]).strip()[:100], amount))
    return output


def recommendations(report):
    """Return up to three bounded, traceable observations and next steps."""
    result = []
    accepted = report.get('accepted', 0)
    rejected = report.get('rejected', 0)
    if isinstance(accepted, int) and isinstance(rejected, int) and accepted >= 0 and rejected >= 0:
        total = accepted + rejected
        if total and rejected:
            pct = Decimal(rejected) * 100 / Decimal(total)
            result.append((
                'Data quality',
                '%d of %d rows flagged (%.1f%%).' % (rejected, total, pct),
                'Review flagged rows before relying on this report for decisions.'
            ))
    monthly = _series(report.get('monthly_rows'))
    if len(monthly) >= 2:
        # The engine produces YYYY-MM chronological labels. Do not compare
        # arbitrary or duplicated labels as if they were successive months.
        ordered = sorted((label, amount) for label, amount in monthly
                         if len(label) == 7 and label[4] == '-' and
                         label[:4].isdigit() and label[5:7].isdigit() and
                         1 <= int(label[5:7]) <= 12)
        if len(ordered) >= 2 and ordered[-1][0] != ordered[-2][0]:
            (prior_month, prior), (current_month, current) = ordered[-2:]
            delta = current - prior
            direction = 'higher' if delta > 0 else 'lower' if delta < 0 else 'unchanged'
            result.append((
                'Revenue movement',
                '%s revenue ($%s) is %s than %s ($%s).' % (
                    current_month, format(current, ',.2f'), direction,
                    prior_month, format(prior, ',.2f')),
                'Compare order counts and seasonality before attributing a cause.'
            ))
    products = _series(report.get('product_rows'))
    if len(products) >= 2:
        total = sum((amount for _, amount in products), Decimal(0))
        if total > 0:
            label, amount = max(products, key=lambda item: item[1])
            share = amount * 100 / total
            if share >= 50:
                result.append((
                    'Revenue concentration',
                    '%s represents %.1f%% of listed product revenue.' % (label, share),
                    'Check whether demand depends heavily on this product or service.'
                ))
    return result[:MAX_ITEMS]


def html_panel(report):
    items = recommendations(report)
    if not items:
        return ''
    cards = []
    for title, evidence, action in items:
        cards.append('<li><strong>' + escape(title) + '</strong><p>' +
                     escape(evidence) + '</p><p><em>Next step:</em> ' +
                     escape(action) + '</p></li>')
    return ('<section class="vx-decision-lens" aria-label="Decision Lens">'
            '<h3>Decision Lens</h3>'
            '<p>Evidence from your uploaded sales summary, not an AI prediction. '
            'These are review prompts, not guaranteed revenue gains.</p>'
            '<ol>' + ''.join(cards) + '</ol></section>')
