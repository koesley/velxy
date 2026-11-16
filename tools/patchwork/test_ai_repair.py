"""Mocked AI proposal tests: no external network requests."""
import json
import tempfile
import unittest
from pathlib import Path
from ai_repair import propose_with_ai

class AIRepairTests(unittest.TestCase):
    def test_ai_response_is_validated_and_never_applied(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'example.py'
            path.write_text('if True\n    print(1)\n')
            def mock(request):
                self.assertIn(b'if True', request.data)
                response = {'choices': [{'message': {'content': json.dumps({
                    'replacement': 'if True:\n    print(1)\n', 'explanation': 'Added colon'
                })}}]}
                return json.dumps(response).encode()
            result = propose_with_ai(root, 'example.py', api_key='test', model='test-model', transport=mock)
            self.assertEqual(result['status'], 'ready_for_review')
            self.assertTrue(result['ai_generated'])
            self.assertFalse(result['applied'])
            self.assertEqual(path.read_text(), 'if True\n    print(1)\n')

    def test_bad_ai_response_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / 'example.py').write_text('x=1\n')
            with self.assertRaises(ValueError):
                propose_with_ai(root, 'example.py', api_key='test', model='test-model', transport=lambda request: b'not json')

    def test_rejects_custom_endpoint(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / 'example.py').write_text('x=1\n')
            with self.assertRaises(ValueError):
                propose_with_ai(root, 'example.py', api_key='test', model='test-model', endpoint='http://localhost:9999')

if __name__ == '__main__':
    unittest.main()
