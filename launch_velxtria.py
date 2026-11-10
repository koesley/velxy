"""Local desktop-style launcher for VELXTRIA. Requires installed Python."""
import os
import sys
import time
import socket
import subprocess
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get('PORT', '8878'))
URL = f'http://127.0.0.1:{PORT}/sovereign-singularity-v58'

def wait_for_port(port, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.4):
                return True
        except OSError:
            time.sleep(0.2)
    return False

def main():
    os.chdir(ROOT)
    env = os.environ.copy()
    env['VELXTRIA_LOCAL_STUDIO'] = '1'
    env['VELXTRIA_DEPLOYMENT_MODE'] = 'local'
    env['PORT'] = str(PORT)
    try:
        with socket.create_connection(('127.0.0.1', PORT), timeout=0.3):
            print(f'Port {PORT} is already in use. Opening browser; check that the running server is yours.')
            webbrowser.open(URL)
            return 0
    except OSError:
        pass
    print('Starting VELXTRIA locally. Close this window to stop it.')
    proc = subprocess.Popen([sys.executable, '-u', str(ROOT / 'portal.py')], cwd=str(ROOT), env=env)
    try:
        if wait_for_port(PORT):
            print('Opening:', URL)
            webbrowser.open(URL)
        else:
            print('VELXTRIA did not start in time. Check the error above.')
            proc.terminate()
            return 1
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill()
        return 0

if __name__ == '__main__':
    raise SystemExit(main())
