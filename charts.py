"""Inline SVG revenue charts for report summaries.

The site shell is modern, but the report output — demo result, share
page, report view, landing sample — was plain HTML tables. These charts
make the product itself look like next-level tech: a monthly revenue
bar chart and a product revenue bar chart, rendered as dependency-free
inline SVG (no JavaScript, no external assets, no cookies), so they
work everywhere the summaries render and pass the site's strict CSP.

Only the aggregated summaries are charted — never the file or a raw
row. Labels are user data (product names, months), so every label is
HTML-escaped. Revenue is parsed defensively: a row whose revenue does
not parse is skipped, and a chart with no chartable rows renders as ''.
"""
import html
from decimal import Decimal, InvalidOperation

MAX_MONTHS = 12
MAX_PRODUCTS = 8

_ACCENT = '#9d9cff'
_CYAN = '#67e8f9'
_INK = '#f2f5ff'
_MUTED = '#b1bdd2'
_GRID = '#ffffff14'


def _money(value):
    """$470.00, trimmed to $470 when it is a whole number."""
    text = f'{value:.2f}'
    if text.endswith('.00'):
        text = text[:-3]
    return '$' + text


def _parse(rows):
    """(label, Decimal revenue) pairs from summary rows. rows[0] is the
    header; revenue is the last column. Unparseable rows are skipped."""
    out = []
    if not rows or len(rows) < 2:
        return out
    for row in rows[1:]:
        if len(row) < 2:
            continue
        try:
            value = Decimal(str(row[-1]).replace(',', '').strip())
        except (InvalidOperation, ValueError):
            continue
        if value < 0:
            continue
        out.append((str(row[0]), value))
    return out


def _month_label(label):
    """2026-10 -> Oct 26; anything else is shown as-is."""
    try:
        year, month = label.split('-', 1)
        names = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
        num = int(month)
        if 1 <= num <= 12 and len(year) == 4 and year.isdigit():
            return '%s %s' % (names[num - 1], year[2:])
    except (ValueError, AttributeError):
        pass
    return label


def monthly_chart(rows):
    """Vertical bar chart of paid revenue by month. '' when no data."""
    data = _parse(rows)[-MAX_MONTHS:]
    if not data:
        return ''
    width, height = 560, 260
    pad_x, top, bottom = 16, 34, 30
    plot_h = height - top - bottom
    max_v = max(v for _, v in data)
    if max_v <= 0:
        max_v = Decimal('1')
    n = len(data)
    gap = 10
    # Cap the bar width so a single month is a bar, not a full-width slab.
    bar_w = min(120, max(14, (width - 2 * pad_x - (n - 1) * gap) // n))
    total_w = n * bar_w + (n - 1) * gap
    x0 = (width - total_w) // 2
    parts = [
        '<svg class="vx-chart" viewBox="0 0 %d %d" role="img" '
        'aria-label="Monthly paid revenue chart">'
        '<defs><linearGradient id="vx-monthly-grad" x1="0" y1="0" x2="0" '
        'y2="1"><stop offset="0" stop-color="%s"/>'
        '<stop offset="1" stop-color="%s"/></linearGradient></defs>'
        % (width, height, _ACCENT, _CYAN)]
    # Light gridlines at 0/50/100% of the max.
    for frac in (0.0, 0.5, 1.0):
        y = top + plot_h - int(plot_h * frac)
        parts.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" '
                     'stroke-width="1"/>' % (pad_x, y, width - pad_x, y, _GRID))
    for i, (label, value) in enumerate(data):
        bar_h = max(2, int(plot_h * float(value / max_v)))
        x = x0 + i * (bar_w + gap)
        y = top + plot_h - bar_h
        parts.append('<rect x="%d" y="%d" width="%d" height="%d" rx="4" '
                     'fill="url(#vx-monthly-grad)"/>' % (x, y, bar_w, bar_h))
        parts.append('<text x="%d" y="%d" fill="%s" font-size="12" '
                     'font-weight="700" text-anchor="middle">%s</text>'
                     % (x + bar_w // 2, y - 8, _INK, _money(value)))
        parts.append('<text x="%d" y="%d" fill="%s" font-size="12" '
                     'text-anchor="middle">%s</text>'
                     % (x + bar_w // 2, height - 10, _MUTED,
                        html.escape(_month_label(label))))
    parts.append('</svg>')
    return ''.join(parts)


def product_chart(rows):
    """Horizontal bar chart of paid revenue by product, top 8 by revenue.
    '' when no data."""
    data = sorted(_parse(rows), key=lambda pair: pair[1], reverse=True)
    data = data[:MAX_PRODUCTS]
    if not data:
        return ''
    label_w, value_w, row_h, bar_h = 150, 72, 32, 18
    width = 560
    height = 16 + len(data) * row_h + 10
    max_v = max(v for _, v in data)
    if max_v <= 0:
        max_v = Decimal('1')
    bar_max = width - label_w - value_w - 16
    parts = [
        '<svg class="vx-chart" viewBox="0 0 %d %d" role="img" '
        'aria-label="Paid revenue by product chart">'
        '<defs><linearGradient id="vx-product-grad" x1="0" y1="0" x2="1" '
        'y2="0"><stop offset="0" stop-color="%s"/>'
        '<stop offset="1" stop-color="%s"/></linearGradient></defs>'
        % (width, height, _ACCENT, _CYAN)]
    for i, (label, value) in enumerate(data):
        y = 16 + i * row_h
        bar_len = max(2, int(bar_max * float(value / max_v)))
        short = label if len(label) <= 20 else label[:19] + '…'
        parts.append('<text x="%d" y="%d" fill="%s" font-size="12" '
                     'text-anchor="end">%s</text>'
                     % (label_w - 10, y + bar_h - 4, _MUTED,
                        html.escape(short)))
        parts.append('<rect x="%d" y="%d" width="%d" height="%d" rx="4" '
                     'fill="url(#vx-product-grad)"/>'
                     % (label_w, y, bar_len, bar_h))
        parts.append('<text x="%d" y="%d" fill="%s" font-size="12" '
                     'font-weight="700">%s</text>'
                     % (label_w + bar_len + 8, y + bar_h - 4, _INK,
                        _money(value)))
    parts.append('</svg>')
    return ''.join(parts)
