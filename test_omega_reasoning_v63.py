"""Offline tests for optional AI reasoning; no network calls or API charges."""
import io
import json
import os
import unittest
from unittest.mock import patch
import omega_reasoning_v63 as ai
class FakeResponse:
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n):return json.dumps({"choices":[{"message":{"content":"Suggested business plan."}}]}).encode()
class ReasoningTests(unittest.TestCase):
    def test_disabled_without_opt_in(self):
        with patch.dict(os.environ,{"VELXTRIA_OMEGA_AI_ENABLED":"0","OPENAI_API_KEY":"fake"}):
            with self.assertRaises(ValueError):ai.generate("Strategy","A business","Plan","Draft")
    def test_safe_configured_request(self):
        seen=[]
        def transport(request,timeout):
            seen.append((request.full_url,timeout,json.loads(request.data)))
            return FakeResponse()
        with patch.dict(os.environ,{"VELXTRIA_OMEGA_AI_ENABLED":"1","OPENAI_API_KEY":"fake","VELXTRIA_OMEGA_AI_MODEL":"gpt-4o-mini"}):
            result=ai.generate("Strategy","Create a service company","Plan","Draft",transport=transport)
        self.assertIn("HUMAN REVIEW REQUIRED",result)
        self.assertEqual(seen[0][0],"https://api.openai.com/v1/chat/completions")
        self.assertNotIn("tools",seen[0][2])
    def test_model_allowlist(self):
        with patch.dict(os.environ,{"VELXTRIA_OMEGA_AI_ENABLED":"1","OPENAI_API_KEY":"fake","VELXTRIA_OMEGA_AI_MODEL":"untrusted-model"}):
            with self.assertRaises(ValueError):ai.generate("Strategy","A business","Plan","Draft")
if __name__=="__main__":unittest.main()
