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
            # Verify real HTTP responses, not only static source strings.
            base = "http://127.0.0.1:%s" % port
            with urllib.request.urlopen(base + "/command-palette.js", timeout=5) as response:
                script = response.read(250000)
                if response.status != 200:
                    raise RuntimeError("Command search asset returned non-200")
                if "javascript" not in response.headers.get("Content-Type", ""):
                    raise RuntimeError("Command search asset has incorrect MIME type")
                if b"dialog.showModal()" not in script or b"aria-current" not in script:
                    raise RuntimeError("Command search behavior missing")
                if "nosniff" != response.headers.get("X-Content-Type-Options"):
                    raise RuntimeError("Command search MIME sniffing protection missing")
            with urllib.request.urlopen(base + "/style.css", timeout=5) as response:
                css = response.read()
                if response.status != 200 or "text/css" not in response.headers.get("Content-Type", ""):
                    raise RuntimeError("Production stylesheet unavailable")
                for selector in (b".vx-command-dialog", b".cmd-shell", b".studio-panel"):
                    if selector not in css:
                        raise RuntimeError("Production stylesheet is missing a design layer")
                if css.rfind(b".vx-command-dialog") < css.find(b".studio-panel"):
                    raise RuntimeError("Modern command styles precede legacy studio styles")
            with urllib.request.urlopen(base + "/", timeout=5) as response:
                html = response.read(250000)
                policy = response.headers.get("Content-Security-Policy", "")
                if "script-src 'self'" not in policy or "'unsafe-inline'" in policy:
                    raise RuntimeError("Command search is blocked or CSP is too permissive")
                for marker in (b'/command-palette.js', b'id="vx-command-dialog"',
                               b'id="vx-command-open"', b'id="vx-command-search"'):
                    if marker not in html:
                        raise RuntimeError("Command search shell markup missing")
            database = pathlib.Path(directory) / "portal.sqlite3"
            if not database.is_file():
                raise RuntimeError("Local database was not initialized")
            print("VELXTRIA real HTTP startup, command search, CSS, CSP and disposable database: PASS")
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
