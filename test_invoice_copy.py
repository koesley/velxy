"""Regression coverage for opt-in invoice copy-as-draft workflow."""
import sqlite3
import unittest
from unittest.mock import patch
import business_v4


class InvoiceCopyTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY)')
        self.db.executemany('INSERT INTO users(id) VALUES (?)',[(1,),(2,)])
        self.db.execute('CREATE TABLE vx3_contacts(id TEXT PRIMARY KEY,user_id INTEGER,name TEXT,created_at INTEGER)')
        self.db.execute('CREATE TABLE vx3_entries(id TEXT,user_id INTEGER,kind TEXT,description TEXT,amount_cents INTEGER,created_at INTEGER)')
        self.db.execute('CREATE TABLE vx3_tasks(id TEXT,user_id INTEGER,title TEXT,status TEXT,created_at INTEGER)')
        business_v4.setup(self.db)
        self.db.execute('INSERT INTO vx3_contacts VALUES (?,?,?,?)',('c1',1,'Client',1))
        self.db.execute('INSERT INTO vx4_invoices(id,user_id,contact_id,description,amount_cents,status,due_at,created_at) VALUES (?,?,?,?,?,?,?,?)',
                        ('original',1,'c1','Annual service',12345,'paid',100,100))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_copy_is_draft_with_fresh_due_date_and_no_income(self):
        fixed=2000000000
        with patch.object(business_v4.time,'time',return_value=fixed):
            business_v4.process(self.db,1,{'action':'invoice_duplicate','id':'original'})
        rows=self.db.execute('SELECT id,contact_id,description,amount_cents,status,due_at FROM vx4_invoices WHERE user_id=1 ORDER BY created_at DESC').fetchall()
        copied=next(r for r in rows if r[0]!='original')
        self.assertEqual(copied[1:],('c1','Annual service',12345,'draft',fixed-fixed%86400+7*86400))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM vx3_entries').fetchone()[0],0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM vx4_events WHERE event_type='draft_copied'").fetchone()[0],1)

    def test_cannot_copy_another_tenants_invoice(self):
        with self.assertRaisesRegex(ValueError,'not found'):
            business_v4.process(self.db,2,{'action':'invoice_duplicate','id':'original'})
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM vx4_invoices').fetchone()[0],1)

    def test_missing_contact_rejects_without_partial_copy(self):
        self.db.execute('DELETE FROM vx3_contacts WHERE id=?',('c1',))
        with self.assertRaisesRegex(ValueError,'no longer available'):
            business_v4.process(self.db,1,{'action':'invoice_duplicate','id':'original'})
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM vx4_invoices').fetchone()[0],1)

    def test_invalid_source_amount_rejected(self):
        self.db.execute('UPDATE vx4_invoices SET amount_cents=-1 WHERE id=?',('original',))
        with self.assertRaisesRegex(ValueError,'invalid'):
            business_v4.process(self.db,1,{'action':'invoice_duplicate','id':'original'})
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM vx4_invoices').fetchone()[0],1)

    def test_ui_escapes_content_and_offers_explicit_copy(self):
        self.db.execute('UPDATE vx4_invoices SET description=? WHERE id=?',('<script>alert(1)</script>','original'))
        page=business_v4.render(self.db,1,'csrf-value')
        self.assertIn('Copy as draft',page)
        self.assertIn('value="invoice_duplicate"',page)
        self.assertIn('&lt;script&gt;',page)
        self.assertNotIn('<script>alert(1)</script>',page)
        self.assertIn('value="csrf-value"',page)


if __name__=='__main__':
    unittest.main()
