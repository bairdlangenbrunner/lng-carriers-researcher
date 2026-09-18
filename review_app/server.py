"""
Local review server — the phase 1 Store behind review_app/web/.

    python review_app/server.py [--batches <dir> ...] [--reviewer NAME] [--port 8765] [--no-open]

Standard library only; binds 127.0.0.1 and refuses anything but loopback. With --batches it
rebuilds work/review_data.json first (review_data.py); otherwise it serves the existing one.

    GET  /             static front end (review_app/web/)
    GET  /api/data     review_data.json with the batches' current decisions laid over it
    GET  /api/whoami   {"reviewer": ...}
    POST /api/decide   [decision record, ...] -> {"saved": [...]}  (store.decide; 400 = nothing written)
"""
import argparse
import ipaddress
import json
import mimetypes
import subprocess
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WEB = HERE / "web"
for p in (ROOT / "scripts", HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import review_data  # noqa: E402
import store  # noqa: E402
from paths import work_dir  # noqa: E402


def ensure_loopback(host):
    """Raise ValueError unless `host` is a loopback address (the data is unreleased)."""
    if host == "localhost":
        return
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise ValueError(f"refusing to bind {host!r}: the review server is loopback-only")


class App:
    """Server state: the dataset, where its batch dirs live, who is reviewing."""

    def __init__(self, data_path, reviewer, batches_root=None):
        self.data_path = Path(data_path)
        self.reviewer = reviewer
        self.batches_root = Path(batches_root) if batches_root else ROOT / "batches"
        self.lock = threading.Lock()
        self.data = json.loads(self.data_path.read_text(encoding="utf-8"))
        self.dirs = {b["dir"]: self.batches_root / b["dir"] for b in self.data["batches"]}

    def current(self):
        with self.lock:
            return store.overlay(self.data, self.dirs)

    def decide(self, records):
        with self.lock:
            return store.decide(records, self.data, self.dirs, self.reviewer)


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version = "review_app/1"

        def log_message(self, fmt, *args):  # quiet; errors still reach stderr via send_error
            pass

        def _host_ok(self):
            # DNS-rebinding guard: only answer requests addressed to the loopback host
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
            try:
                ensure_loopback(host)
                return True
            except ValueError:
                return False

        def _json(self, obj, status=HTTPStatus.OK):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self._host_ok():
                return self._json({"error": "bad host"}, HTTPStatus.FORBIDDEN)
            path = self.path.split("?", 1)[0]
            if path == "/api/data":
                return self._json(app.current())
            if path == "/api/whoami":
                return self._json({"reviewer": app.reviewer})
            rel = "index.html" if path in ("/", "") else path.lstrip("/")
            f = (WEB / rel).resolve()
            if WEB not in f.parents or not f.is_file():
                return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            body = f.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mimetypes.guess_type(f.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if not self._host_ok():
                return self._json({"error": "bad host"}, HTTPStatus.FORBIDDEN)
            # a cross-site page cannot send application/json without a preflight we never answer
            if (self.headers.get("Content-Type") or "").split(";")[0].strip() != "application/json":
                return self._json({"error": "expected application/json"}, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return self._json({"error": "body is not JSON"}, HTTPStatus.BAD_REQUEST)
            path = self.path.split("?", 1)[0]
            try:
                if path == "/api/decide":
                    return self._json({"saved": app.decide(body)})
            except store.Invalid as e:
                return self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
            except Exception as e:  # a failed write: report it loudly, the UI keeps the line undecided
                print(f"review app: write failed: {e!r}", file=sys.stderr)
                return self._json({"error": f"write failed: {e}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    return Handler


def make_server(app, host="127.0.0.1", port=8765):
    ensure_loopback(host)
    return ThreadingHTTPServer((host, port), make_handler(app))


def git_user():
    try:
        return subprocess.run(["git", "config", "user.name"], capture_output=True, text=True,
                              cwd=ROOT).stdout.strip() or "reviewer"
    except OSError:
        return "reviewer"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--batches", nargs="+", help="rebuild work/review_data.json from these first")
    ap.add_argument("--data", default=None, help="default work/review_data.json")
    ap.add_argument("--reviewer", default=None, help="default: git config user.name")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args(argv)
    try:
        ensure_loopback(args.host)
    except ValueError as e:
        raise SystemExit(str(e))
    data_path = Path(args.data) if args.data else work_dir() / "review_data.json"
    if args.batches:
        review_data.main(["--batches", *args.batches, "--out", str(data_path)])
    elif not data_path.exists():
        raise SystemExit(f"{data_path} not found — pass --batches, or run review_app/review_data.py first")
    app = App(data_path, args.reviewer or git_user())
    httpd = make_server(app, args.host, args.port)
    url = f"http://{args.host}:{httpd.server_address[1]}/"
    print(f"review app: {url}  (reviewer: {app.reviewer}; Ctrl-C to stop)", file=sys.stderr)
    if not args.no_open:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
