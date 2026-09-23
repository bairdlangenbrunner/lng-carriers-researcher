"""
Archive [ref] URLs to the Wayback Machine via Save Page Now 2 (SPN2), authenticated.

Always authenticated: the Internet Archive S3 key is read from $IA_S3_AUTH
("access:secret"), else $IA_ACCESS_KEY + $IA_SECRET_KEY, else the macOS
keychain item `archive-org-s3` (how Baird's machine stores it). With no key the
script exits — it never silently falls back to anonymous SPN, which is capped
at 3 captures/min and 200/day and fails far more often.

SPN2 limits (official API doc, checked 2026-09-16): authenticated = 7
captures/min and 30k/day, a per-account cap on concurrent capture sessions
(read live from /save/status/user), 5 captures/day per URL. Captures run
server-side, so the script submits at --rate per minute while up to
--concurrency jobs are in flight, then polls each job to completion. Plan
~N/6 minutes for N URLs (the backend's ~440 distinct URLs ≈ 75 min).

What it archives: every distinct URL in a backend [ref] cell (same extraction
as citation_qc.py), minus banned shapes (url_verifier.url_ban_reason — GEM,
abarrelfull, shorteners, /save/ …) and URLs that are already Wayback
snapshots. Or pass --urls FILE (one URL per line).

--within (SPN2 if_not_archived_within, default 30d) makes SPN return the
existing capture instead of re-capturing a URL archived recently.

Output: work/wayback_save.jsonl, one line per finished URL (append-only, so
re-running resumes: URLs already `success` or a permanent error are skipped;
--retry-errors re-tries the errors). `snapshot` is the citable
https://web.archive.org/web/<timestamp>/<url> form.

Never edits the backend. Whether a snapshot goes into a [ref] cell is a
ref_fill.md §7 call (snapshot only as a last resort when the live URL is dead).

Usage:
    python scripts/wayback_save.py --dry-run          # count + auth check, no captures
    python scripts/wayback_save.py                    # whole backend
    python scripts/wayback_save.py --sheet-rows 900-1220
    python scripts/wayback_save.py --urls work/urls.txt --within 0
    python scripts/wayback_save.py --retry-errors
"""
import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter, deque
from datetime import UTC, datetime
from urllib.parse import urlencode

from paths import backend_csv_path, work_dir

SPN = "https://web.archive.org/save"
KEYCHAIN_SERVICE = "archive-org-s3"
AUTH_RATE_CAP = 7          # captures/min for authenticated users (SPN2 doc)
JOB_TIMEOUT_S = 300        # give up polling a job after this long
POLL_EVERY_S = 5

# status_ext values worth another try later (SPN-side load, not the target URL)
RETRYABLE = {
    "error:user-session-limit", "error:cannot-fetch", "error:celery",
    "error:no-browsers-available", "error:proxy-error", "error:job-failed",
    "error:internal-server-error", "error:capture-location-error",
    "error:too-many-requests", "error:browsing-timeout",
    "error:soft-time-limit-exceeded", "error:read-timeout", "error:gateway-timeout",
    "error:service-unavailable", "error:bad-gateway", "http-error", "poll-timeout",
}
MAX_ATTEMPTS = 3


def ia_auth() -> str | None:
    """'access:secret' from env or the macOS keychain, or None."""
    v = os.environ.get("IA_S3_AUTH", "").strip()
    if v:
        return v
    a, s = os.environ.get("IA_ACCESS_KEY", ""), os.environ.get("IA_SECRET_KEY", "")
    if a and s:
        return f"{a}:{s}"
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-a", os.environ.get("USER", ""),
             "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def spn(auth: str, path: str = "", data: dict | None = None, timeout: int = 60):
    """Call SPN2; returns (http_status:int, json|None). The key goes to curl on
    stdin (-K -), never on the command line where `ps` would show it."""
    cfg = f'header = "Authorization: LOW {auth}"\nheader = "Accept: application/json"\n'
    cmd = ["curl", "-sS", "-K", "-", "--max-time", str(timeout),
           "-o", "-", "-w", "\n%{http_code}"]
    if data is not None:
        cmd += ["-X", "POST", "--data", urlencode(data)]
    cmd.append(SPN + path)
    try:
        r = subprocess.run(cmd, input=cfg, capture_output=True, text=True,
                           timeout=timeout + 10)
    except subprocess.SubprocessError:
        return 0, None
    body, _, code = r.stdout.rpartition("\n")
    try:
        return int(code), json.loads(body) if body.strip() else None
    except ValueError:
        return int(code) if code.isdigit() else 0, None


def backend_urls(args) -> list[str]:
    from backend_io import load_backend
    from citation_qc import _parse_range, collect
    be = load_backend(args.backend)
    by_url = collect(be, row_ids=_parse_range(args.rows),
                     sheet_rows=_parse_range(args.sheet_rows))
    return list(by_url)


def load_done(path, retry_errors: bool) -> dict:
    """url -> last record, for URLs that should be skipped on resume."""
    last = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                    last[rec["url"]] = rec
                except (ValueError, KeyError):
                    continue
    return {u: r for u, r in last.items()
            if r["status"] == "success" or (r["status"] == "error" and not retry_errors)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--backend", default=str(backend_csv_path()))
    ap.add_argument("--rows", default="", help="row_id range/list")
    ap.add_argument("--sheet-rows", default="", help="LIVE sheet tab rows")
    ap.add_argument("--urls", default="", help="file of URLs (one per line) instead of the backend")
    ap.add_argument("--within", default="30d",
                    help="skip re-capture if archived within this window (SPN2 syntax; 0 = always capture)")
    ap.add_argument("--rate", type=float, default=6, help=f"captures/min (SPN2 cap {AUTH_RATE_CAP})")
    ap.add_argument("--concurrency", type=int, default=0,
                    help="max jobs in flight (default: account's available sessions)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--retry-errors", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=str(work_dir() / "wayback_save.jsonl"))
    args = ap.parse_args()

    auth = ia_auth()
    if not auth or ":" not in auth:
        sys.exit("No Internet Archive S3 key. Set IA_S3_AUTH=access:secret, or store it with\n"
                 f"  security add-generic-password -a \"$USER\" -s {KEYCHAIN_SERVICE} -w 'access:secret'\n"
                 "(keys: https://archive.org/account/s3.php)")
    code, user = spn(auth, f"/status/user?_t={int(time.time() * 1000)}")
    if code != 200 or not isinstance(user, dict) or "available" not in user:
        sys.exit(f"SPN2 auth check failed (HTTP {code}): {user!r}")
    sessions = int(user["available"]) + int(user.get("processing", 0))
    concurrency = args.concurrency or max(1, sessions)
    rate = min(args.rate, AUTH_RATE_CAP)

    from url_verifier import url_ban_reason
    if args.urls:
        with open(args.urls, encoding="utf-8") as fh:
            urls = list(dict.fromkeys(l.strip() for l in fh if l.strip().startswith("http")))
    else:
        urls = backend_urls(args)
    skipped = Counter()
    todo = []
    done = load_done(args.out, args.retry_errors)
    for u in urls:
        if "web.archive.org/" in u.lower() or "archive.org/details/" in u.lower():
            skipped["already archive"] += 1
        elif url_ban_reason(u):
            skipped["banned shape"] += 1
        elif u in done:
            skipped[f"done ({done[u]['status']})"] += 1
        else:
            todo.append(u)
    if args.limit:
        todo = todo[:args.limit]
    print(f"auth ok — {user.get('daily_captures', '?')}/{user.get('daily_captures_limit', '?')} "
          f"captures used today, {concurrency} concurrent sessions")
    print(f"{len(urls)} distinct URLs; skipped {dict(skipped) or 0}; to archive: {len(todo)} "
          f"(~{len(todo) / rate:.0f} min at {rate:g}/min)")
    if args.dry_run or not todo:
        return

    queue = deque((u, 1) for u in todo)
    active = {}                     # job_id -> (url, attempt, submitted_at)
    last_submit = 0.0
    tally = Counter()
    out = open(args.out, "a", encoding="utf-8")

    def finish(url, attempt, rec):
        rec = {"ts": datetime.now(UTC).isoformat(timespec="seconds"),
               "url": url, "attempts": attempt, **rec}
        if rec["status"] == "error" and rec.get("status_ext") in RETRYABLE and attempt < MAX_ATTEMPTS:
            queue.append((url, attempt + 1))
            return
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()
        tally[rec["status"]] += 1
        n = sum(tally.values())
        note = rec.get("snapshot") or rec.get("status_ext") or rec.get("message", "")
        print(f"[{n}/{len(todo)}] {rec['status']:7} {url}  {note}", flush=True)

    try:
        while queue or active:
            now = time.time()
            if queue and len(active) < concurrency and now - last_submit >= 60 / rate:
                url, attempt = queue.popleft()
                data = {"url": url, "skip_first_archive": "1"}
                if args.within not in ("", "0"):
                    data["if_not_archived_within"] = args.within
                code, resp = spn(auth, "", data)
                last_submit = time.time()
                if isinstance(resp, dict) and resp.get("job_id"):
                    active[resp["job_id"]] = (url, attempt, last_submit)
                elif code == 429 or (isinstance(resp, dict) and
                                     resp.get("status_ext") == "error:user-session-limit"):
                    queue.appendleft((url, attempt))
                    time.sleep(30)
                else:
                    resp = resp if isinstance(resp, dict) else {}
                    finish(url, attempt, {"status": "error",
                                          "status_ext": resp.get("status_ext", "http-error"),
                                          "message": resp.get("message", f"HTTP {code}")})
                continue
            for job_id, (url, attempt, t0) in list(active.items()):
                code, st = spn(auth, f"/status/{job_id}")
                st = st if isinstance(st, dict) else {}
                if st.get("status") == "success":
                    del active[job_id]
                    orig = st.get("original_url") or url
                    finish(url, attempt, {"status": "success", "job_id": job_id,
                                          "timestamp": st.get("timestamp"),
                                          "original_url": orig,
                                          "snapshot": f"https://web.archive.org/web/{st.get('timestamp')}/{orig}",
                                          "message": st.get("message", "")})
                elif st.get("status") == "error":
                    del active[job_id]
                    finish(url, attempt, {"status": "error", "job_id": job_id,
                                          "status_ext": st.get("status_ext", ""),
                                          "message": st.get("message", "")})
                elif time.time() - t0 > JOB_TIMEOUT_S:
                    del active[job_id]
                    finish(url, attempt, {"status": "error", "job_id": job_id,
                                          "status_ext": "poll-timeout",
                                          "message": f"still pending after {JOB_TIMEOUT_S}s"})
            time.sleep(POLL_EVERY_S if active else 1)
    except KeyboardInterrupt:
        print("\ninterrupted — in-flight jobs not recorded; re-run to resume", file=sys.stderr)
    finally:
        out.close()
    print(f"done: {dict(tally)} → {args.out}")


if __name__ == "__main__":
    main()
