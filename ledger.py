"""The Sales Ledger: log sales one at a time, get a living report.

VELXTRIA used to be a one-shot tool — upload a CSV, get a report, leave.
Nothing gave a business a reason to come back the next day. The ledger
changes that: a signed-in user logs each sale as it happens (date,
customer, product, quantity, price, status), and the dashboard shows a
live monthly + product summary of everything logged so far, using the
same aggregation the report engine uses (Paid orders only, revenue =
quantity x unit price). The ledger can be downloaded as a clean CSV or
turned into a full report (which counts against the free allowance, the
same as an upload).

Entries are validated on add with the engine's own rules, so a ledger can
never hold a row the engine would flag: order ID is required and unique
per user, the date must parse, quantity must be a positive integer, unit
price must be a nonnegative number, and status must be Paid, Pending or
Refunded. Region is required, the same as the CSV schema.
"""
import csv
import io
import secrets
import time
import zipfile
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation

STATUSES = ('Paid', 'Pending', 'Refunded')
HEADER = ['Order ID', 'Order Date', 'Customer', 'Product', 'Quantity',
          'Unit Price', 'Status', 'Region']
_DATE_FORMATS = ('%Y-%m-%d', '%m/%d/%Y', '%Y/%m/%d')


def setup(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS ledger_entries (
      id TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
      order_id TEXT NOT NULL, order_date TEXT NOT NULL,
      customer TEXT NOT NULL, product TEXT NOT NULL,
      quantity INTEGER NOT NULL, unit_price TEXT NOT NULL,
      status TEXT NOT NULL, region TEXT NOT NULL, created INTEGER NOT NULL,
      UNIQUE(user_id, order_id),
      FOREIGN KEY(user_id) REFERENCES users(id))''')


def parse_date(raw):
    """Parse a date the way the report engine does; return ISO YYYY-MM-DD."""
    text = (raw or '').strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError('invalid date')


def validate(order_id, order_date, customer, product, quantity, unit_price,
             status, region):
    """Validate one ledger entry with the engine's rules. Returns the
    normalised values as a dict, or raises ValueError with a plain message."""
    oid = (order_id or '').strip().upper()
    if not oid:
        raise ValueError('missing order ID')
    try:
        date = parse_date(order_date)
    except ValueError:
        raise ValueError('invalid date')
    cust = ' '.join((customer or '').split()).title()
    if not cust:
        raise ValueError('missing customer')
    prod = ' '.join((product or '').split())
    if not prod:
        raise ValueError('missing product')
    reg = (region or '').strip().title()
    if not reg:
        raise ValueError('missing region')
    stat = (status or '').strip().title()
    if stat not in STATUSES:
        raise ValueError('unknown status')
    try:
        qty = int(str(quantity).strip())
        if qty <= 0:
            raise ValueError()
    except ValueError:
        raise ValueError('quantity must be a positive integer')
    try:
        price = Decimal(str(unit_price).strip().replace('$', '').replace(',', ''))
        if not price.is_finite() or price < 0:
            raise InvalidOperation()
    except (InvalidOperation, ValueError):
        raise ValueError('invalid unit price')
    return {'order_id': oid, 'order_date': date, 'customer': cust,
            'product': prod, 'quantity': qty, 'unit_price': f'{price:.2f}',
            'status': stat, 'region': reg}


def add_entry(conn, user_id, order_id, order_date, customer, product,
              quantity, unit_price, status, region, now=None):
    """Validate and store one sale. Raises ValueError on bad data or on a
    duplicate order ID for this user. Returns the new entry id."""
    setup(conn)
    entry = validate(order_id, order_date, customer, product, quantity,
                     unit_price, status, region)
    existing = conn.execute(
        'SELECT 1 FROM ledger_entries WHERE user_id=? AND order_id=?',
        (user_id, entry['order_id'])).fetchone()
    if existing:
        raise ValueError('Order ID already in your ledger')
    ident = secrets.token_hex(8)
    conn.execute(
        'INSERT INTO ledger_entries (id,user_id,order_id,order_date,'
        'customer,product,quantity,unit_price,status,region,created)'
        ' VALUES (?,?,?,?,?,?,?,?,?,?,?)',
        (ident, user_id, entry['order_id'], entry['order_date'],
         entry['customer'], entry['product'], entry['quantity'],
         entry['unit_price'], entry['status'], entry['region'],
         int(time.time()) if now is None else now))
    return ident


SEED_LIMIT = 50


def seed_from_zip_bytes(conn, user_id, zip_bytes, limit=SEED_LIMIT):
    """Seed the ledger from a report ZIP's cleaned_sales.csv.

    Demo-to-Workspace: when a visitor claims an own-CSV demo into their
    account, the demo's accepted sales become the starting ledger, so the
    dashboard opens on their real numbers instead of an empty workspace.
    Returns how many entries were stored. A row that cannot be stored
    (duplicate order ID, invalid data) is skipped, and a ZIP without a
    readable cleaned_sales.csv seeds nothing — never raises.
    """
    if not zip_bytes:
        return 0
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            if 'cleaned_sales.csv' not in z.namelist():
                return 0
            text = z.read('cleaned_sales.csv').decode('utf-8-sig')
    except Exception:
        return 0
    seeded = 0
    # Give each seeded row its own created timestamp, increasing in CSV
    # order: they are all inserted in the same second, and created is the
    # only thing ordering them, so identical timestamps would leave the
    # order to chance.
    base = int(time.time())
    for idx, row in enumerate(csv.DictReader(io.StringIO(text))):
        if seeded >= limit:
            break
        try:
            add_entry(conn, user_id,
                      row.get('Order ID'), row.get('Order Date'),
                      row.get('Customer'), row.get('Product'),
                      row.get('Quantity'), row.get('Unit Price'),
                      row.get('Status'), row.get('Region'),
                      now=base + idx)
        except ValueError:
            continue
        seeded += 1
    return seeded


def list_entries(conn, user_id, limit=10):
    """Most recent entries first, as (id, order_id, order_date, customer,
    product, quantity, unit_price, status, region, created) tuples."""
    rows = conn.execute(
        'SELECT id,order_id,order_date,customer,product,quantity,'
        'unit_price,status,region,created FROM ledger_entries'
        ' WHERE user_id=? ORDER BY created DESC, id DESC LIMIT ?',
        (user_id, limit)).fetchall()
    return rows


def count_entries(conn, user_id):
    row = conn.execute(
        'SELECT COUNT(*) FROM ledger_entries WHERE user_id=?',
        (user_id,)).fetchone()
    return row[0] if row else 0


def _all_rows(conn, user_id):
    """All entries, oldest first, as dicts in CSV column order."""
    rows = conn.execute(
        'SELECT order_id,order_date,customer,product,quantity,unit_price,'
        'status,region FROM ledger_entries WHERE user_id=?'
        ' ORDER BY created ASC, id ASC',
        (user_id,)).fetchall()
    return [dict(zip(HEADER, [r[0], r[1], r[2], r[3], str(r[4]), r[5],
                              r[6], r[7]])) for r in rows]


def to_csv_bytes(conn, user_id):
    """The whole ledger as a CSV in the report engine's input schema."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=HEADER)
    writer.writeheader()
    writer.writerows(_all_rows(conn, user_id))
    return buf.getvalue().encode('utf-8')


def summaries(conn, user_id):
    """Monthly + product summaries of the ledger, aggregated exactly the
    way the report engine does (Paid orders only). Returns
    (monthly_rows, product_rows, stats) where the rows are lists of lists
    with a header, ready for report_summaries_html."""
    rows = _all_rows(conn, user_id)
    by_month = defaultdict(lambda: [0, Decimal('0')])
    by_product = defaultdict(lambda: [0, Decimal('0')])
    paid_total = Decimal('0')
    paid_orders = 0
    for r in rows:
        if r['Status'] != 'Paid':
            continue
        amount = Decimal(r['Quantity']) * Decimal(r['Unit Price'])
        paid_total += amount
        paid_orders += 1
        month = r['Order Date'][:7]
        by_month[month][0] += 1
        by_month[month][1] += amount
        by_product[r['Product']][0] += 1
        by_product[r['Product']][1] += amount
    monthly_rows = [['Month', 'Paid Orders', 'Paid Revenue']] + [
        [k, str(v[0]), f'{v[1]:.2f}'] for k, v in sorted(by_month.items())]
    product_rows = [['Product', 'Paid Orders', 'Paid Revenue']] + [
        [k, str(v[0]), f'{v[1]:.2f}'] for k, v in sorted(by_product.items())]
    stats = ['Ledger entries: %d' % len(rows),
             'Paid orders: %d' % paid_orders,
             'Paid revenue: $%s' % f'{paid_total:,.2f}']
    return monthly_rows, product_rows, stats
