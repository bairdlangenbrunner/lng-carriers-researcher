"""
Local review server: the shared server in ../gem-review-app (review_core/server.py) bound to the LNG store (core_store.py) and config (trackers/lng/config.py).

    python review_app/server.py [--batches <dir> ...] [--reviewer NAME] [--port 8765] [--no-open] [--no-living]

Standard library only; binds 127.0.0.1 and refuses anything but loopback. With --batches it rebuilds work/review_data.json first (review_data.py); otherwise it serves the existing one. The file on disk keeps the form push.py, living.py and suggestions.py read; the server serves it in the shared app's form (review_data.adapt).

    GET  /              the shared page, titled "LNG carriers reviewer" (core files under /core/, the LNG extension under /tracker/)
    GET  /api/data      the dataset with every batch's decisions laid over it (core_store.overlay)
    GET  /api/whoami    {"reviewer": initials, "caps": {"decide", "refresh", "push"}, "store": false}
    POST /api/decide    [{key, decision, suggested_value?, suggest_kind?, suggested_refs?, note?, via?} | {key, undo: true}, ...] -> {"saved": [...]}  review_log.jsonl + decisions.csv (400 = nothing written)
    POST /api/item      [{key, call, note?} | {key, undo: true}, ...] -> {"saved": [...]}  review_items.jsonl + a conflict's call in conflicts.csv `decision`
    POST /api/refresh   {} -> {"backend_pulled", "accepted", "resolved", "living"}  re-pull the backend (pull_backend.py, read-only profile), rebuild, then core_store.sync_backend. Reads the backend; never writes it.
    POST /api/push/plan {"batch"?} -> push.plan(): re-pull, then every cell the accepted lines would change (live row, column, old -> new) and a token. Writes nothing.
    POST /api/push      {"token", "include_applied", "batch"?} -> {"written", "mismatches", ...}  the ONE backend write (push.py, gws write profile, AP §2b): re-pull, recompute, refuse (409) unless the plan still has the token the reviewer confirmed, write, re-pull, verify.

Every POST must be application/json (415 otherwise): a cross-site page cannot send that without a preflight this server never answers.
"""
import argparse
import json
import subprocess
import sys
import webbrowser
from http import HTTPStatus
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for p in (ROOT / "scripts", HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import core_store as store  # noqa: E402
import living  # noqa: E402
import push  # noqa: E402
import review_data  # noqa: E402
from paths import work_dir  # noqa: E402
from review_core import server as core  # noqa: E402

ensure_loopback = core.ensure_loopback
Refusal = core.Refusal


class PullFailed(RuntimeError):
    """pull_backend.py did not produce a fresh backend csv (HTTP 502; nothing changed)."""


def pull_backend():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "pull_backend.py")],
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        raise PullFailed("backend pull failed: " + (r.stderr.strip().splitlines() or ["no output"])[-1])


class App(core.App):
    """Server state: the dataset (raw, as built, and in the shared form), where its batch dirs live,
    who is reviewing. `pull` renews the backend csv and `write` sends planned cells to the sheet;
    tests pass fakes for both."""

    def __init__(self, data_path, reviewer, batches_root=None, backend_path=None, pull=None,
                 write=None, living_wb=None):
        self.backend_path = backend_path      # None = work/backend.csv
        self.pull = pull or pull_backend
        self.write = write or push.write_sheet
        super().__init__(data_path, reviewer, store, root=batches_root or store.BATCHES)
        # the living workbook on Drive, when one is configured for these batches (None = off)
        self.living = None if living_wb is False else (living_wb or living.from_config(self.dirs()))

    def load(self):
        self.raw = json.loads(self.data_path.read_text(encoding="utf-8"))
        self.data = review_data.adapt(self.raw)

    def sink(self, origin="local"):
        return store.sink

    def living_sync(self):
        """Mirror the current decisions into the living workbook's `processed` columns (AP §2c).
        Never fatal: it writes no backend cell, so a failure is reported and nothing else changes."""
        if not self.living:
            return None
        try:
            return self.living.sync(self.raw, self.dirs())
        except living.LivingError as e:
            print(f"review app: living workbook sync failed: {e}", file=sys.stderr)
            return {"error": str(e), "url": self.living.url, "written": 0}

    def _renew(self):
        """Re-pull, rebuild over the same batch dirs, settle what the backend settles. A failed
        pull or build leaves the served dataset as it was."""
        try:
            self.pull()
        except PullFailed as e:
            raise Refusal(HTTPStatus.BAD_GATEWAY, str(e))
        raw = review_data.build(list(self.dirs().values()), self.backend_path)
        review_data.write(raw, self.data_path)
        self.raw, self.data = raw, review_data.adapt(raw)
        out = store.sync_backend(self.data, self.dirs())
        out["backend_pulled"] = raw["backend_pulled"]
        return out

    def refresh(self):
        with self.lock:
            out = self._renew()
            out["living"] = self.living_sync()
            return out

    def push_plan(self, batch=None):
        with self.lock:
            self._renew()
            return push.plan(self.raw, self.dirs(), self.backend_path, batch)

    def push_apply(self, token, include_applied=False, batch=None):
        """Write the confirmed plan. The plan is recomputed on a fresh pull and must still carry
        the token the reviewer confirmed; otherwise nothing is written (409)."""
        with self.lock:
            self._renew()
            dirs = self.dirs()
            plan = push.plan(self.raw, dirs, self.backend_path, batch)
            writes = plan["writes"] + (plan["applied_writes"] if include_applied else [])
            if token != (plan["token_all"] if include_applied else plan["token"]) or not writes:
                raise Refusal(HTTPStatus.CONFLICT, "the backend or a decision changed since the plan was shown: "
                                                   "nothing was written; open the push again")
            failed = None
            try:
                self.write(writes)
            except push.PushFailed as e:
                failed = str(e)
            try:
                self.pull()
            except PullFailed as e:
                raise Refusal(HTTPStatus.BAD_GATEWAY, f"the push ran but the re-pull to verify it failed: {e}")
            bad = push.verify(writes, self.backend_path)
            missed = {(w["row_id"], w["column"]) for w in bad}
            landed = [w for w in writes if (w["row_id"], w["column"]) not in missed]
            push.log(landed, dirs, self.reviewer)
            out = self._renew()
            out.update({"written": len(landed), "mismatches": bad, "error": failed})
            out["living"] = self.living_sync()
            return out


def make_handler(app):
    """The core handler with one more guard: a POST that is not application/json is refused (415)."""
    base = core.make_handler(app, server_version="lng_review_app/1")

    class Handler(base):
        def do_POST(self):
            if not self._host_ok():
                return self._json({"error": "bad host"}, HTTPStatus.FORBIDDEN)
            if (self.headers.get("Content-Type") or "").split(";")[0].strip() != "application/json":
                return self._json({"error": "expected application/json"}, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            return super().do_POST()

    return Handler


def make_server(app, host="127.0.0.1", port=8765):
    ensure_loopback(host)
    return core.ThreadingHTTPServer((host, port), make_handler(app))


def git_user():
    return core.git_user(ROOT)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--batches", nargs="+", help="rebuild work/review_data.json from these first")
    ap.add_argument("--data", default=None, help="default work/review_data.json")
    ap.add_argument("--reviewer", default=None, help="default: git config user.name; recorded as initials")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--no-living", action="store_true",
                    help="do not sync the living workbook on Drive (data/living_workbook.json)")
    args = ap.parse_args(argv)
    try:
        ensure_loopback(args.host)
    except ValueError as e:
        raise SystemExit(str(e))
    data_path = Path(args.data) if args.data else work_dir() / "review_data.json"
    if args.batches:
        review_data.main(["--batches", *args.batches, "--out", str(data_path)])
    elif not data_path.exists():
        raise SystemExit(f"{data_path} not found: pass --batches, or run review_app/review_data.py first")
    app = App(data_path, args.reviewer or git_user(), living_wb=False if args.no_living else None)
    if app.living:
        print(f"review app: living workbook: {app.living.url}", file=sys.stderr)
    httpd = make_server(app, args.host, args.port)
    url = f"http://{args.host}:{httpd.server_address[1]}/"
    print(f"review app: {url}  (reviewer: {app.reviewer}; decisions write to each batch's decisions.csv, "
          "review_log.jsonl and review_items.jsonl; Ctrl-C to stop)", file=sys.stderr)
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
