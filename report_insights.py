"""Evidence-based next steps from VELXTRIA's existing CSV report summaries.

No AI claims, external requests, or persistence. Never infer profit from revenue.
"""
from decimal import Decimal, InvalidOperation
from html import escape


def _money(value):
    try:
        amount = Decimal(str(value).strip())
        if not amount.is_finite() or amount < 0:
            return None
        return amount
    except (InvalidOperation, ValueError, TypeError):
        return None


def _records(rows, expected):
    if not rows or list(rows[0]) != expected:
        return []
    output = []
    for row in rows[1:]:
        if len(row) != len(expected):
            continue
        amount = _money(row[2])
        try:
            count = int(row[1])
        except (ValueError, TypeError):
            continue
        if amount is None or count < 0:
            continue
        output.append((str(row[0]), count, amount))
    return output


def insights(monthly_rows, product_rows, accepted, rejected):
    """Return bounded, factual suggestions based only on validated summary rows."""
    try:
        accepted, rejected = int(accepted), int(rejected)
    except (ValueError, TypeError):
        return []
    if accepted < 0 or rejected < 0:
        return []
    messages = []
    total = accepted + rejected
    if total and rejected:
        rate = Decimal(rejected) * 100 / total
        messages.append(
            f"Data quality: {rejected} of {total} source rows were flagged "
            f"({rate:.1f}%). Review rejected_rows.csv before making decisions."
        )
    elif total:
        messages.append("Data quality: all source rows passed the report checks.")
    else:
        messages.append("No source rows were processed; upload sales data to see trends.")

    months = _records(monthly_rows, ['Month', 'Paid Orders', 'Paid Revenue'])
    months = sorted((m for m in months if len(m[0]) == 7 and m[0][4] == '-'))
    if len(months) >= 2:
        previous, current = months[-2], months[-1]
        if previous[2] > 0:
            change = (current[2] - previous[2]) * 100 / previous[2]
            direction = "higher" if change > 0 else "lower" if change < 0 else "unchanged"
            messages.append(
                f"Paid revenue in {escape(current[0])} was {abs(change):.1f}% "
                f"{direction} than {escape(previous[0])} in the uploaded records. "
                "Compare complete periods before treating this as a trend."
            )
        else:
            messages.append(
                "The previous reported month had zero paid revenue; "
                "a percentage change is not meaningful."
            )
    products = _records(product_rows, ['Product', 'Paid Orders', 'Paid Revenue'])
    total_paid = sum((r[2] for r in products), Decimal('0'))
    if products and total_paid > 0:
        leader = max(products, key=lambda r: r[2])
        share = leader[2] * 100 / total_paid
        if share >= 50:
            messages.append(
                f"Product concentration: {escape(leader[0][:100])} represents "
                f"{share:.1f}% of paid revenue in these records. "
                "Review reliance on this product before changing your sales plan."
            )
    messages.append(
        "These are descriptive observations from uploaded records, "
        "not verified bank receipts, profit, forecasts, or guaranteed recommendations."
    )
    return messages[:5]


def render(monthly_rows, product_rows, accepted, rejected):
    notes = insights(monthly_rows, product_rows, accepted, rejected)
    return ('<section class="v8-report-insights"><h3>What to review next</h3><ul>'
            + ''.join('<li>' + note + '</li>' for note in notes)
            + '</ul></section>')
