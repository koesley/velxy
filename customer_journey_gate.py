"""Run public acquisition regressions without production credentials.

Each test module runs in a separate Python process and temporary SQLite
directory, avoiding portal import-time DB state and suite collisions.
"""
import os
import subprocess
import sys
import tempfile

MODULES = (
    'test_freemium_demo', 'test_demo_signup', 'test_demo_shares',
    'test_demo_email', 'test_instant_demo', 'test_sample_demo',
)
SECRET_KEYS = (
    'VELXTRIA_DATABASE_URL', 'DATABASE_URL',
    'VELXTRIA_SUPABASE_URL', 'VELXTRIA_SUPABASE_SERVICE_KEY',
    'VELXTRIA_BTCPAY_MAINNET_API_KEY', 'VELXTRIA_BTCPAY_MAINNET_WEBHOOK_SECRET',
    'VELXTRIA_BREVO_API_KEY', 'VELXTRIA_SENDGRID_API_KEY',
    'VELXTRIA_PREVIEW_PASSWORD', 'VELXTRIA_BTCPAY_MAINNET_URL',
    'VELXTRIA_BTCPAY_MAINNET_STORE_ID',
)


def test_environment(source, directory):
    env = {key: value for key, value in source.items() if key not in SECRET_KEYS}
    env.update({
        'VELXTRIA_DATA_DIR': directory,
        'VELXTRIA_REQUIRE_PERSISTENCE': '0',
        'VELXTRIA_DEPLOYMENT_MODE': 'local',
        'VELXTRIA_LOCAL_STUDIO': '1',
        'VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT': '0',
    })
    return env


def run(modules=MODULES, source=None, invoke=None):
    if source is None:
        source = os.environ
    if invoke is None:
        invoke = subprocess.run
    for module in modules:
        if module not in MODULES:
            raise ValueError('unknown test module')
        with tempfile.TemporaryDirectory(prefix='vx-customer-gate-') as directory:
            completed = invoke(
                [sys.executable, '-m', 'unittest', '-v', module],
                env=test_environment(source, directory), check=False,
            )
            if completed.returncode != 0:
                return completed.returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(run())
