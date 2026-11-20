"""Launch the real VELXTRIA HTTP server against disposable local storage.

No external services, production credentials, or customer data are used.
"""
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request


def main():
    root = pathlib.Path(__file__).resolve().parent
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="velxtria-smoke-") as directory:
        env = os.environ.copy()
        # Deliberately isolate smoke tests from any developer or CI secrets.
        for name in list(env):
            if name.startswith("VELXTRIA_"):
                env.pop(name)
        env.update({
            "VELXTRIA_DEPLOYMENT_MODE": "local",
            "VELXTRIA_REQUIRE_PERSISTENCE": "0",
            "VELXTRIA_DATA_DIR": directory,
            "PORT": str(port),
            "PYTHONUNBUFFERED": "1",
        })
        proc = subprocess.Popen(
            [sys.executable, "-u", str(root / "portal.py")],
            cwd=root, env=env, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, text=True,
        )
        try:
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError("Portal exited during startup (no secrets printed)")
                try:
                    with urllib.request.urlopen(
                        "http://127.0.0.1:%s/healthz" % port, timeout=2
                    ) as response:
                        if response.status != 200 or response.read() != b"ok":
                            raise RuntimeError("Unexpected liveness response")
                    break
                except (urllib.error.URLError, TimeoutError, ConnectionError):
                    time.sleep(0.25)
            else:
                raise RuntimeError("Portal did not start within 45 seconds")
            with urllib.request.urlopen(
                "http://127.0.0.1:%s/" % port, timeout=5
            ) as response:
                body = response.read(250000)
                if response.status != 200 or b"VELXTRIA" not in body:
                    raise RuntimeError("Home page smoke test failed")
            database = pathlib.Path(directory) / "portal.sqlite3"
            if not database.is_file():
                raise RuntimeError("Local database was not initialized")
            print("VELXTRIA HTTP startup, home page and disposable database: PASS")
        finally:
            proc.terminate()
            try:
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=5)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("VELXTRIA HTTP smoke test: FAIL (%s)" % type(exc).__name__, file=sys.stderr)
        sys.exit(1)
