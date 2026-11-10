import unittest,sqlite3
import sovereign_opportunities_v57 as o
from unittest.mock import patch
class OpportunityTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:')
  self.data={'role':'owner','nodes':[{'id':'a','name':'Sales','confidence':'hypothesis','source':'interview'}],'edges':[]}
 def tearDown(self):self.c.close()
 def test_suggestions_and_review(self):
  with patch.object(o.core,'setup'),patch.object(o.core,'access',return_value='owner'),patch.object(o.graph,'overview',return_value=self.data),patch.object(o.core,'audit'):
   d=o.suggestions(self.c,1,'workspace');self.assertEqual(d['total'],2)
   o.review(self.c,1,'workspace','hypothesis:a','investigate','Verify with source records')
   self.assertEqual(next(x for x in o.suggestions(self.c,1,'workspace')['suggestions'] if x['id']=='hypothesis:a')['review']['decision'],'investigate')
   with self.assertRaises(ValueError):o.review(self.c,1,'another-workspace','hypothesis:missing','dismiss','reason')
   with self.assertRaises(ValueError):o.review(self.c,1,'workspace','hypothesis:a','approve','reason')
if __name__=='__main__':unittest.main()
