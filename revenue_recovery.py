from decimal import Decimal, InvalidOperation

def summarize_pending(rows):
    count = 0
    total = Decimal('0')
    for row in rows:
        if row.get('Status') != 'Pending':
            continue
        try:
            qty = int(row['Quantity'])
            price = Decimal(row['Unit Price'])
            if qty <= 0 or not price.is_finite() or price < 0:
                continue
            total += qty * price
        except (KeyError, ValueError, TypeError, InvalidOperation, OverflowError):
            continue
        count += 1
    return {'count': count, 'value': format(total, ',.2f')}
