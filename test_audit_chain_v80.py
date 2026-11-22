import unittest
from dataclasses import replace
from audit_chain_v80 import AuditEvent, build_chain, verify_chain, GENESIS
def e(n, workspace="a"):
    return AuditEvent(workspace,n,"actor","lead_updated","lead-1","2026-11-22T00:00:00Z")
class AuditChainTests(unittest.TestCase):
    def test_valid(self):
        rows=build_chain("a",[e(1),e(2)])
        self.assertTrue(verify_chain("a",rows,rows[-1]["hash"]))
    def test_modified_event(self):
        rows=build_chain("a",[e(1)])
        rows[0]["event"]=replace(e(1),action="deleted")
        self.assertFalse(verify_chain("a",rows,rows[0]["hash"]))
    def test_deleted_tail(self):
        rows=build_chain("a",[e(1),e(2)])
        self.assertFalse(verify_chain("a",rows[:1],rows[-1]["hash"]))
    def test_cross_tenant(self):
        with self.assertRaises(ValueError):build_chain("a",[e(1,"b")])
    def test_gap(self):
        with self.assertRaises(ValueError):build_chain("a",[e(2)])
    def test_wrong_workspace_verification(self):
        rows=build_chain("a",[e(1)])
        self.assertFalse(verify_chain("b",rows,rows[-1]["hash"]))
    def test_empty(self):
        self.assertTrue(verify_chain("a",[],GENESIS))
    def test_wrong_head(self):
        rows=build_chain("a",[e(1)])
        self.assertFalse(verify_chain("a",rows,GENESIS))
if __name__=="__main__":unittest.main()
