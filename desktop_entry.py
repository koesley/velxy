"""VELXTRIA Windows desktop entry point, health probe, and safe shutdown."""
import argparse
import logging
import os
import sys
import threading
import urllib.request
import webbrowser
from pathlib import Path
from http.server import ThreadingHTTPServer

PORT = 8878
URL = f"http://127.0.0.1:{PORT}/sovereign-singularity-v58"

def data_dir():
    path = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / "VELXTRIA" / "Data"
    path.mkdir(parents=True, exist_ok=True)
    return path

def configure():
    os.environ["VELXTRIA_DEPLOYMENT_MODE"] = "local"
    os.environ["VELXTRIA_LOCAL_STUDIO"] = "1"
    os.environ["VELXTRIA_DATA_DIR"] = str(data_dir())
    os.environ["PORT"] = str(PORT)
    # Desktop is always local-only. Remove accidentally inherited cloud configuration.
    for name in ("VELXTRIA_DATABASE_URL", "VELXTRIA_REQUIRE_PERSISTENCE", "VELXTRIA_SMTP_HOST"):
        os.environ.pop(name, None)

def health_check(url=URL):
    with urllib.request.urlopen(url, timeout=8) as response:
        return response.status == 200 and len(response.read(512)) > 0

def main(argv=None):
    args = argparse.ArgumentParser()
    args.add_argument("--smoke-test", action="store_true", help="Start server, check HTTP response, then exit")
    opts = args.parse_args(argv)
    configure()
    log_path = data_dir() / "desktop.log"
    logging.basicConfig(filename=log_path, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    server = None
    worker = None
    try:
        from desktop_maintenance import backup
        import portal
        # Database migration happens on first connection. Never overwrite a backup.
        database = data_dir() / "portal.sqlite3"
        if database.exists():
            try:
                backup(data_dir())
            except Exception:
                logging.exception("Pre-start backup failed; refusing to migrate database")
                raise RuntimeError("Database backup failed. Startup stopped to protect your data.")
        portal.db().close()
        try:
            server = ThreadingHTTPServer(("127.0.0.1", PORT), portal.Handler)
        except OSError as exc:
            raise RuntimeError(f"Cannot bind localhost port {PORT}. Another instance may already be running.") from exc
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        if not health_check():
            raise RuntimeError("Local server failed its startup health check")
        if opts.smoke_test:
            print("VELXTRIA desktop smoke test passed", flush=True)
            return 0
        if portal.DELIVERY_ENABLED:
            threading.Thread(target=portal.delivery_worker, daemon=True).start()
        try:
            import webview
        except ImportError:
            webbrowser.open(URL)
            try:
                while worker.is_alive(): worker.join(timeout=1)
            except KeyboardInterrupt:
                pass
        else:
            webview.create_window("VELXTRIA Desktop", URL, width=1320, height=850, min_size=(850, 600))
            webview.start(debug=False)
        return 0
    except Exception as exc:
        logging.exception("Desktop startup failed")
        print(f"VELXTRIA could not start: {exc}. See {log_path}", file=sys.stderr, flush=True)
        if not opts.smoke_test:
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, f"VELXTRIA could not start:\n{exc}\n\nDiagnostic log: {log_path}", "VELXTRIA startup error", 0x10)
            except Exception:
                pass
        return 1
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if worker is not None:
            worker.join(timeout=5)

if __name__ == "__main__":
    raise SystemExit(main())
