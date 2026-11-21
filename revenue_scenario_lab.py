"""Revenue sensitivity from reconciled aggregate sales reports.

Scenarios are arithmetic what-ifs, not forecasts. No customer rows or
personal information are read, persisted, or sent externally.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

SHIFTS = (Decimal('-0.10'), Decimal('0'), Decimal('0.10'), Decimal('0.20'))


def _money(value):
    return '${:,.2f}'.format(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _parse_money(raw):
    try:
        amount = Decimal(str(raw).strip().replace(',', '').replace('$', ''))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return amount if amount.is_finite() and amount >= 0 else None


def _revenue(rows):
    if not isinstance(rows, (tuple, list)) or len(rows) < 2:
        return None
    header = rows[0]
    if not isinstance(header, (tuple, list)):
        return None
    names = [str(item).strip().lower() for item in header]
    if names.count('revenue') != 1:
        return None
    index = names.index('revenue')
    total = Decimal(0)
    for row in rows[1:]:
        if not isinstance(row, (tuple, list)) or len(row) <= index:
            return None
        value = _parse_money(row[index])
        if value is None:
            return None
        total += value
    return total


def scenario(report):
    if not isinstance(report, dict):
        return None
    monthly = _revenue(report.get('monthly_rows'))
    products = _revenue(report.get('product_rows'))
    if monthly is None or products is None or monthly <= 0:
        return None
    if abs(monthly - products) > Decimal('0.01'):
        return None
    return {'baseline': monthly, 'cases': [
        {'shift': shift, 'revenue': monthly * (Decimal(1) + shift),
         'difference': monthly * shift} for shift in SHIFTS]}


def html_panel(report):
    data = scenario(report)
    if data is None:
        return ''
    cells = []
    for case in data['cases']:
        label = '{:+.0f}%'.format(case['shift'] * 100)
        difference = case['difference']
        cells.append('<tr><th scope="row">' + label + '</th><td>' +
                     _money(case['revenue']) + '</td><td>' +
                     ('+' if difference > 0 else '') +
                     _money(difference) + '</td></tr>')
    return ('<section class="vx-scenario-lab" aria-label="Revenue scenario lab">'
            '<h3>Revenue Scenario Lab</h3>'
            '<p>Explore arithmetic what-if changes using revenue measured in your '
            'uploaded report. These examples are not forecasts, guarantees, '
            'or recommended prices.</p>'
            '<p><strong>Baseline paid revenue: ' + _money(data['baseline']) + '</strong></p>'
            '<div class="vx-table-scroll"><table><thead><tr>'
            '<th scope="col">Assumed change</th>'
            '<th scope="col">Scenario revenue</th>'
            '<th scope="col">Difference</th></tr></thead><tbody>' +
            ''.join(cells) + '</tbody></table></div>'
            '<p>Assumptions: the same reporting period, constant revenue mix '
            'and a uniform percentage adjustment. Costs, seasonality, demand '
            'and profit are not modeled. Review the underlying report before acting.</p>'
            '</section>')
