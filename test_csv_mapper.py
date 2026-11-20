"""Regression coverage for the public, browser-local CSV column mapper."""
import os
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import csv_mapper

REQUIRED = ['Order ID','Order Date','Customer','Product','Quantity','Unit Price','Status','Region']

class MapperUnitTests(unittest.TestCase):
    def test_required_headers_and_export_present(self):
        page=csv_mapper.page(REQUIRED)
        for header in REQUIRED:
            self.assertIn(header,page)
        self.assertIn('velxtria-mapped.csv',page)
        self.assertIn('Download mapped CSV',page)

    def test_browser_local_no_network_upload(self):
        page=csv_mapper.page(REQUIRED)
        self.assertIn('f.text()',page)
        self.assertIn('URL.createObjectURL',page)
        self.assertNotIn('fetch(',page)
        self.assertNotIn('XMLHttpRequest',page)
        self.assertNotIn('FormData(',page)

    def test_limits_and_duplicate_mapping_guard(self):
        page=csv_mapper.page(REQUIRED)
        self.assertIn('5*1024*1024',page)
        self.assertIn('10001',page)
        self.assertIn('new Set(indices).size===REQUIRED.length',page)
        self.assertIn('rows.some(r=>r.length!==width)',page)

    def test_formula_escape_and_csv_quoting(self):
        page=csv_mapper.page(REQUIRED)
        self.assertIn('Spreadsheet software may interpret formulas',page)
        self.assertIn('s.replace(/"/g',page)
        self.assertIn('if(quoted)throw Error',page)

    def test_schema_validation_and_script_escape(self):
        with self.assertRaises(ValueError):
            csv_mapper.page(['a']*8)
        with self.assertRaises(ValueError):
            csv_mapper.page(['a'])
        page=csv_mapper.page(['<script>']+REQUIRED[1:])
        self.assertNotIn('["<script>"',page)
        self.assertIn('u003c',page)

class MapperRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.env=patch.dict(os.environ,{'VELXTRIA_DATA_DIR':cls.tmp.name,'VELXTRIA_DEPLOYMENT_MODE':'local','VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT':'0'})
        cls.env.start()
        import portal
        portal.DATA_ROOT.mkdir(parents=True,exist_ok=True)
        portal.REPORTS.mkdir(parents=True,exist_ok=True)
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),portal.Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base='http://127.0.0.1:%s'%cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close()
        cls.env.stop();cls.tmp.cleanup()

    def test_public_mapper_route(self):
        with urllib.request.urlopen(self.base+'/csv-mapper',timeout=20) as r:
            body=r.read().decode()
            self.assertEqual(r.status,200)
        self.assertIn('Match your sales CSV columns',body)
        self.assertIn('/#try',body)

    def test_landing_has_mapper_link(self):
        with urllib.request.urlopen(self.base+'/',timeout=20) as r:
            body=r.read().decode()
        self.assertIn('href="/csv-mapper"',body)

if __name__=='__main__':
    unittest.main()
