import unittest
from revenue_recovery import summarize_pending

class RecoveryTests(unittest.TestCase):
    def test_full_stream(self):
        rows = ({'Status':'Pending','Quantity':'2','Unit Price':'10.25'} for _ in range(100))
        self.assertEqual(summarize_pending(rows), {'count':100,'value':'2,050.00','largest':'20.50'})
    def test_exclusions(self):
        rows = [{'Status':s,'Quantity':'2','Unit Price':p} for s,p in [('Paid','5'),('Refunded','5'),('Pending','NaN'),('Pending','-1'),('Pending','5')]]
        self.assertEqual(summarize_pending(rows), {'count':1,'value':'10.00','largest':'10.00'})
    def test_empty(self):
        self.assertEqual(summarize_pending([]), {'count':0,'value':'0.00','largest':'0.00'})

    def test_largest_order(self):
        rows = [{'Status':'Pending','Quantity':'1','Unit Price':p} for p in ('5','200','12')]
        self.assertEqual(summarize_pending(rows)['largest'], '200.00')
