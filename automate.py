"""VELXTRIA Demo 001. Standard-library-only CSV cleanup and reporting."""
from pathlib import Path
from collections import defaultdict,Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
import csv

ROOT=Path(__file__).resolve().parent
INPUT=ROOT/'messy_sales_input.csv'
OUT=ROOT/'output'
COLUMNS=['Order ID','Order Date','Customer','Product','Quantity','Unit Price','Status','Region','Revenue']

def write_csv(path,columns,rows):
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(rows)

def parse_date(s):
    for fmt in ('%Y-%m-%d','%m/%d/%Y','%Y/%m/%d'):
        try:return datetime.strptime(s.strip(),fmt).date().isoformat()
        except ValueError:pass
    raise ValueError('invalid date')

def main():
    OUT.mkdir(exist_ok=True)
    with INPUT.open(newline='',encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        expected=COLUMNS[:-1]
        if reader.fieldnames != expected:raise ValueError(f'Unexpected input columns: {reader.fieldnames}')
        source=list(reader)
    accepted=[];rejected=[];seen=set();counts=Counter()
    for line,row in enumerate(source,start=2):
        issues=[]
        order=row['Order ID'].strip().upper(); customer=' '.join(row['Customer'].split()).title()
        product=' '.join(row['Product'].split());region=row['Region'].strip().title();status=row['Status'].strip().title()
        if not order:issues.append('missing order ID')
        elif order in seen:issues.append('duplicate order ID')
        if not customer:issues.append('missing customer')
        if not product:issues.append('missing product')
        if not region:issues.append('missing region')
        if status not in {'Paid','Pending','Refunded'}:issues.append('unknown status')
        try:date=parse_date(row['Order Date'])
        except ValueError:date='';issues.append('invalid date')
        try:
            qty=int(row['Quantity'].strip())
            if qty<=0:raise ValueError()
        except ValueError:qty=0;issues.append('quantity must be a positive integer')
        try:
            price=Decimal(row['Unit Price'].strip().replace('$','').replace(',',''))
            if not price.is_finite() or price<0:raise InvalidOperation()
        except (InvalidOperation,ValueError):price=Decimal('0');issues.append('invalid unit price')
        if issues:
            for issue in issues:counts[issue]+=1
            rejected.append({'Source Line':line,**row,'Issue(s)':'; '.join(issues)})
            continue
        seen.add(order)
        revenue=(Decimal(qty)*price).quantize(Decimal('0.01'))
        accepted.append(dict(zip(COLUMNS,[order,date,customer,product,qty,f'{price:.2f}',status,region,f'{revenue:.2f}'])))
    write_csv(OUT/'cleaned_sales.csv',COLUMNS,accepted)
    write_csv(OUT/'rejected_rows.csv',['Source Line']+COLUMNS[:-1]+['Issue(s)'],rejected)
    by_month=defaultdict(lambda:[0,Decimal('0')]);by_product=defaultdict(lambda:[0,Decimal('0')])
    paid_total=Decimal('0')
    for r in accepted:
        if r['Status']!='Paid':continue
        amount=Decimal(r['Revenue']);paid_total+=amount
        for group,key in ((by_month,r['Order Date'][:7]),(by_product,r['Product'])):
            group[key][0]+=1;group[key][1]+=amount
    write_csv(OUT/'monthly_summary.csv',['Month','Paid Orders','Paid Revenue'],[{'Month':k,'Paid Orders':v[0],'Paid Revenue':f'{v[1]:.2f}'} for k,v in sorted(by_month.items())])
    write_csv(OUT/'product_summary.csv',['Product','Paid Orders','Paid Revenue'],[{'Product':k,'Paid Orders':v[0],'Paid Revenue':f'{v[1]:.2f}'} for k,v in sorted(by_product.items())])
    summary=f'''VELXTRIA / REPORT AUTOMATION — DEMO 001
=======================================
Source rows: {len(source)}
Accepted rows: {len(accepted)}
Rejected rows: {len(rejected)}
Reconciliation: {len(accepted)} + {len(rejected)} = {len(source)}
Paid revenue (accepted Paid orders only): ${paid_total:,.2f}
Paid orders: {sum(v[0] for v in by_month.values())}

Rejection reasons (a row can have multiple reasons):
'''+''.join(f'- {k}: {v}\n' for k,v in sorted(counts.items()))+'''
BUSINESS RULES
- Unique Order ID required; first valid occurrence retained.
- Valid dates: YYYY-MM-DD, MM/DD/YYYY, YYYY/MM/DD.
- Quantity must be a positive integer; unit price must be nonnegative.
- Only Paid status contributes to sales totals; Pending/Refunded retained but excluded.
- Rejected records are not silently discarded; review rejected_rows.csv.
- No taxes, shipping, discounts, currency conversion, or refund netting modeled.
- Demo uses entirely fictional data. No network calls or third-party packages.
'''
    (OUT/'run_summary.txt').write_text(summary,encoding='utf-8')
    print(summary)
if __name__=='__main__':main()
