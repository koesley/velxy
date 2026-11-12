import sqlite3
import unittest
from unittest.mock import patch
import native_integrations_v66 as v66
import business_os_v59 as crm

class NativeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.access=patch.object(crm.core,"access",return_value="owner")
        self.audit=patch.object(crm.core,"audit")
        self.access.start();self.audit.start()
    def tearDown(self):
        self.access.stop();self.audit.stop();self.c.close()
    def test_csv_import_deduplicates_and_scopes(self):
        data="name,contact,source,value\nAlice,alice@example.com,website,200\nBob,bob@example.com,referral,50"
        self.assertEqual(v66.import_csv(self.c,1,"a",data),2)
        self.assertEqual(v66.import_csv(self.c,1,"a",data),0)
        self.assertEqual(len(crm.overview(self.c,1,"a")["leads"]),2)
        self.assertEqual(len(crm.overview(self.c,1,"b")["leads"]),0)
    def test_invalid_csv_does_not_write(self):
        data="name,contact,source,value\nAlice,a@example.com,web,200\nBad,b@example.com,web,nan"
        with self.assertRaises(ValueError):v66.import_csv(self.c,1,"a",data)
        self.assertEqual(len(crm.overview(self.c,1,"a")["leads"]),0)
    def test_only_approved_email(self):
        lid=crm.add_lead(self.c,1,"a","Alice","alice@example.com","web",0)
        aid=crm.propose(self.c,1,"a",lid,"Hello Alice")
        with self.assertRaises(ValueError):v66.approved_email(self.c,1,"a",aid)
        crm.review(self.c,1,"a",aid,"approved","Looks good")
        link=v66.approved_email(self.c,1,"a",aid)
        self.assertIn("mailto:alice@example.com",link)
        self.assertIn("Hello+Alice",link)
        with self.assertRaises(ValueError):v66.approved_email(self.c,1,"b",aid)
    def test_html_escaped(self):
        crm.add_lead(self.c,1,"a","<script>","test@example.com","web",0)
        self.assertNotIn("<script>",v66.render(self.c,1,"a","csrf"))

if __name__=="__main__":unittest.main()
