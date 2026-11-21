"""Run HTTP signup regressions with production credentials removed.

Render exposes its production DATABASE_URL during builds. Never allow test
HTTP handlers to connect to that database. This wrapper creates an isolated
SQLite data directory and runs the suite in a fresh Python interpreter.
"""
import os
import subprocess
import sys
import tempfile

TEST_MODULES = ("test_demo_signup",)
UNSAFE_KEYS = (
    "VELXTRIA_DATABASE_URL", "DATABASE_URL",
    "VELXTRIA_SUPABASE_URL", "VELXTRIA_SUPABASE_SERVICE_KEY",
    "VELXTRIA_BTCPAY_MAINNET_API_KEY",
    "VELXTRIA_BTCPAY_MAINNET_WEBHOOK_SECRET",
    "VELXTRIA_BREVO_API_KEY", "VELXTRIA_SENDGRID_API_KEY",
    "VELXTRIA_PREVIEW_PASSWORD",
)


def isolated_environment(source, data_dir):
    """Return a new environment without production DB or service credentials."""
    env = dict(source)
    for key in UNSAFE_KEYS:
        env.pop(key, None)
    env.update({
        "VELXTRIA_DATA_DIR": data_dir,
        "VELXTRIA_REQUIRE_PERSISTENCE": "0",
        "VELXTRIA_DEPLOYMENT_MODE": "local",
        "VELXTRIA_LOCAL_STUDIO": "1",
        "VELXTRIA_ENABLE_BTCPAY_MAINNET_CHECKOUT": "0",
    })
    return env


def main():
    with tempfile.TemporaryDirectory(prefix="velxtria-test-") as data_dir:
        env = isolated_environment(os.environ, data_dir)
        # Do not use shell=True or pass secrets as command-line arguments.
        return subprocess.call(
            [sys.executable, "-m", "unittest", "-v", *TEST_MODULES],
            env=env,
        )


if __name__ == "__main__":
    raise SystemExit(main())
