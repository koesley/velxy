import json
import tempfile
import unittest
from pathlib import Path
import singularity_factory_v58 as factory

class FactoryTests(unittest.TestCase):
 def test_validation_rejects_unsupported_fields(self):
  with self.assertRaises(ValueError):factory.validate({'fields':['name','email','password']})
 def test_validation_rejects_duplicate_fields(self):
  with self.assertRaises(ValueError):factory.validate({'fields':['name','email','email']})
 def test_validation_rejects_invalid_name(self):
  with self.assertRaises(ValueError):factory.validate({'name':'<script>'})
 def test_generation_and_test_execution(self):
  with tempfile.TemporaryDirectory() as t:
   out=Path(t)/'app'
   result=factory.build(factory.DEFAULT,out)
   self.assertTrue(result['tests']['passed'],result['tests']['output'])
   self.assertTrue((out/'manifest.json').exists())
   z=factory.package(out,Path(t)/'app.zip')
   self.assertTrue(z.exists())
 def test_no_overwrite(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(FileExistsError):factory.build(factory.DEFAULT,t)
 def test_comparison(self):
  with tempfile.TemporaryDirectory() as t:
   results=factory.compare(factory.DEFAULT,Path(t)/'candidates')
   self.assertEqual(len(results),2)
   self.assertTrue(all(r['verified'] for r in results))
if __name__=='__main__':unittest.main()
