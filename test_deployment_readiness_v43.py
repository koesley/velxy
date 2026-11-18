import tempfile,unittest
from pathlib import Path
from deployment_readiness_v43 import inspect

class ReadinessTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.root=Path(self.tmp.name)
  (self.root/"portal.py").write_text("import json\nimport sample_module\n")
  (self.root/"sample_module.py").write_text("VALUE=1\n")
  (self.root/"requirements.txt").write_text("cryptography>=43,<47\npsycopg[binary]>=3.2,<4\n")
  self.find=lambda name:object()
 def tearDown(self):self.tmp.cleanup()
 def run_check(self,env=None,finder=None):
  return inspect(self.root,{} if env is None else env,self.find if finder is None else finder)
 def test_valid_environment(self):
  self.assertTrue(self.run_check()["ready"])
 def test_missing_dependency(self):
  report=self.run_check(finder=lambda name:None if name=="cryptography" else object())
  self.assertFalse(report["ready"])
  self.assertIn("installed_cryptography",[x["check"] for x in report["checks"] if not x["ok"]])
 def test_missing_local_import(self):
  (self.root/"sample_module.py").unlink()
  self.assertFalse(self.run_check()["ready"])
 def test_syntax_error(self):
  (self.root/"portal.py").write_text("def broken(:")
  self.assertFalse(self.run_check()["ready"])
 def test_mainnet_fail_closed(self):
  env={"VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT":"1"}
  report=self.run_check(env)
  self.assertFalse(report["ready"])
  self.assertIn("mainnet_configuration",[x["check"] for x in report["checks"] if not x["ok"]])
 def test_mainnet_valid_keys_and_host(self):
  env={key:"placeholder" for key in ("VELXTRIA_BTCPAY_MAINNET_STORE_ID","VELXTRIA_BTCPAY_MAINNET_API_KEY","VELXTRIA_BTCPAY_MAINNET_WEBHOOK_SECRET")}
  env.update(VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT="1",VELXTRIA_BTCPAY_MAINNET_URL="https://btcpay.example.com")
  self.assertTrue(self.run_check(env)["ready"])
 def test_no_secrets_leak(self):
  env={"VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT":"1","VELXTRIA_BTCPAY_MAINNET_API_KEY":"secret-token-should-never-print"}
  self.assertNotIn("secret-token-should-never-print",str(self.run_check(env)))
if __name__=="__main__":unittest.main()
