"""Invoice input integrity regression tests (SQLite, no external sends)."""
import sqlite3
import unittest
import business_v4


class InvoiceInputIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.execute('CREATE TABLE vx3_contacts (id TEXT, user_id INTEGER, name TEXT)')
        self.conn.execute("INSERT INTO vx3_contacts VALUES ('owned', 1, 'Alice')")
        self.conn.execute("INSERT INTO vx3_contacts VALUES ('foreign', 2, 'Bob')")
        self.conn.execute('CREATE TABLE vx4_invoices (id TEXT, user_id INTEGER, contact_id TEXT, description TEXT, amount_cents INTEGER, status TEXT DEFAULT \'draft\', due_at INTEGER, created_at INTEGER)')
        self.valid = dict(action='invoice_create', description='Website design', contact_id='owned', amount='125.50', due_date='2027-01-15')

    def tearDown(self):
        self.conn.close()

    def count(self):
        return self.conn.execute('SELECT COUNT(*) FROM vx4_invoices').fetchone()[0]

    def test_valid_invoice_created_with_exact_cents(self):
        business_v4.process(self.conn, 1, self.valid)
        self.assertEqual(self.conn.execute('SELECT user_id,contact_id,amount_cents FROM vx4_invoices').fetchone(), (1, 'owned', 12550))

    def test_control_characters_rejected_without_write(self):
        for field, value in [('description', 'Service\nextra'), ('description', 'Service\x00'), ('contact_id', 'owned\t')]:
            with self.subTest(field=field, value=repr(value)):
                with self.assertRaises(ValueError):
                    business_v4.process(self.conn, 1, dict(self.valid, **{field: value}))
                self.assertEqual(self.count(), 0)

    def test_oversized_description_and_contact_rejected(self):
        for field, value in [('description', 'X' * 181), ('contact_id', 'x' * 129)]:
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    business_v4.process(self.conn, 1, dict(self.valid, **{field: value}))
                self.assertEqual(self.count(), 0)

    def test_cross_workspace_contact_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Customer not found'):
            business_v4.process(self.conn, 1, dict(self.valid, contact_id='foreign'))
        self.assertEqual(self.count(), 0)

    def test_invalid_dates_rejected(self):
        for value in ['2027-02-30', '2027-1-15', '2027-01-15T12:00', '2027-01-15\n', 'not-a-date']:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    business_v4.process(self.conn, 1, dict(self.valid, due_date=value))
                self.assertEqual(self.count(), 0)

    def test_invalid_amount_never_writes(self):
        for value in ['NaN', '-1', '1.234', 'Infinity']:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    business_v4.process(self.conn, 1, dict(self.valid, amount=value))
                self.assertEqual(self.count(), 0)


if __name__ == '__main__':
    unittest.main()
