"""Regression tests for the customer journey deployment gate."""
import os
import unittest
from types import SimpleNamespace
import customer_journey_gate as gate


class CustomerJourneyGateTests(unittest.TestCase):
    def test_scrubs_credentials_and_enforces_local_mode(self):
        source = {key: 'sensitive' for key in gate.SECRET_KEYS}
        source.update({'VELXTRIA_REQUIRE_PERSISTENCE': '1',
                       'VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT': '1',
                       'UNRELATED': 'safe'})
        result = gate.test_environment(source, '/tmp/isolated')
        self.assertTrue(all(key not in result for key in gate.SECRET_KEYS))
        self.assertEqual(result['VELXTRIA_REQUIRE_PERSISTENCE'], '0')
        self.assertEqual(result['VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT'], '0')
        self.assertEqual(result['VELXTRIA_DEPLOYMENT_MODE'], 'local')
        self.assertEqual(result['UNRELATED'], 'safe')
        self.assertEqual(source['VELXTRIA_REQUIRE_PERSISTENCE'], '1')

    def test_modules_run_in_distinct_temporary_directories(self):
        observed = []
        def fake_invoke(command, env, check):
            self.assertFalse(check)
            self.assertEqual(command[:3], [gate.sys.executable, '-m', 'unittest'])
            self.assertTrue(os.path.isdir(env['VELXTRIA_DATA_DIR']))
            observed.append((command[-1], env['VELXTRIA_DATA_DIR']))
            return SimpleNamespace(returncode=0)
        self.assertEqual(gate.run(modules=gate.MODULES[:2], source={}, invoke=fake_invoke), 0)
        self.assertEqual(len(observed), 2)
        self.assertNotEqual(observed[0][1], observed[1][1])
        self.assertTrue(all(not os.path.exists(directory) for _, directory in observed))

    def test_failure_stops_remaining_tests(self):
        observed = []
        def fake_invoke(command, env, check):
            observed.append(command[-1])
            return SimpleNamespace(returncode=3)
        self.assertEqual(gate.run(modules=gate.MODULES[:2], source={}, invoke=fake_invoke), 3)
        self.assertEqual(observed, [gate.MODULES[0]])

    def test_unknown_modules_are_rejected_before_execution(self):
        with self.assertRaises(ValueError):
            gate.run(modules=('arbitrary_module',), source={}, invoke=lambda **kw: None)


if __name__ == '__main__':
    unittest.main()
