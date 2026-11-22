import csv
import io
import unittest
from unittest.mock import patch
import business_os_v59 as crm

class SafeCsvTests(unittest.TestCase):
    def test_formula_prefixes(self):
        for prefix in ("=", "+", "-", "@"):
            self.assertEqual(crm._safe_spreadsheet_cell(prefix+"SUM(1,1)"), "'"+prefix+"SUM(1,1)")
    def test_hidden_prefixes(self):
        for prefix in (" ", "\t", "\r", "\n"):
            self.assertEqual(crm._safe_spreadsheet_cell(prefix+"=1+1"), "'"+prefix+"=1+1")
    def test_safe_text_unchanged(self):
        self.assertEqual(crm._safe_spreadsheet_cell("Normal Customer"),"Normal Customer")
    def test_numeric_unchanged(self):
        self.assertEqual(crm._safe_spreadsheet_cell(120.5),120.5)
    def test_csv_export(self):
        lead={"id":"id1","name":"=HYPERLINK(1)","contact":" jane@example.com",
              "source":"\t+1+2","value":100.0,"status":"new","created":1}
        with patch.object(crm,"overview",return_value={"leads":[lead]}):
            data=crm.export_csv(None,1,"workspace1")
        row=list(csv.DictReader(io.StringIO(data)))[0]
        self.assertEqual(row["name"],"'=HYPERLINK(1)")
        self.assertEqual(row["source"],"'\t+1+2")
        self.assertEqual(row["value"],"100.0")
if __name__=="__main__": unittest.main()
