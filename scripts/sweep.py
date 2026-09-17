"""
Polite bulk fetch — many URLs from the same host without earning an IP ban.

Why this exists: on 2026-09-17 a throwaway loop sent 323 per-IMO lookups to
vesselfinder.com at a fixed 1 s, with no backoff and no stop condition. After
~150 requests the host dropped this machine's IP at the network level (TCP
connects time out on every origin IP, fetch_page() returns "000"), and the ban
outlasted the batch. The fetch ladder (curl -> curl_cffi -> real-Chrome
clearance cookie) only clears HTTP-level walls, where the server answers and
refuses; a firewall drop happens before TLS, so no UA, fingerprint, or cookie
helps. The only remedies are another source, another egress IP, or waiting —
and retrying in a loop tends to extend the ban. So: every bulk sweep of one
host goes through here.

What it does, per host (the key is the host minus a leading "www."):

  pacing    a minimum gap between requests, with random jitter. Default
            6 s +/- 2 s; tracker sites in HOST_DELAYS get 10 s +/- 3 s.
            --delay raises the base gap but never lowers a host's own floor.
  breaker   MAX_CONSEC_FAILS (3) consecutive failures — status "000"/timeout,
            429, or 403 — stop the host for the rest of the run. So do
            MAX_CONSEC_404S (8) consecutive 404s on a host that had been
            answering 200: that pattern preceded the 2026-09-17 ban and may be
            a soft block. The host's remaining URLs are recorded as skipped,
            with the reason. A host whose breaker tripped in an earlier run
            (same --out) re-trips on its first failure.
  cap       --max requests per host per run; the rest wait for a re-run.

Output is resumable JSONL under work/ — one record per URL: url, host, status,
title, description (the meta description), notes, ts, plus `imo` for template
runs, or skipped/reason when the breaker tripped. A re-run skips URLs the
server already answered (200, 404, ...) and retries the skipped ones and the
failures (000/429/403); the file is append-only, so the LATEST record for a
URL wins (load_records()).

URLs are fetched in the order given — put the rows that matter most first.

Usage:
    python scripts/sweep.py --urls work/urls.txt --out my_sweep.jsonl
    python scripts/sweep.py --template 'https://www.vesselfinder.com/vessels/details/{imo}' \\
        --imos work/imos.txt --out vesselfinder_sweep.jsonl --max 40
    python scripts/sweep.py --template '...{imo}' --imos 9904675 --max 1   # single probe

Module use:
    from sweep import Sweeper
    Sweeper(out_path, max_per_host=40).run(urls)      # or [(url, {"imo": ...}), ...]

Exit code 1 when any host's breaker tripped.
"""
import argparse
import html
import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from fetch import fetch_page, page_title
from paths import work_dir

DEFAULT_DELAY = 6.0          # seconds between requests to one host
DEFAULT_JITTER = 2.0         # +/- seconds, uniform
# Slower floors for vessel trackers — they ban at the firewall, not with a wall.
HOST_DELAYS = {
    "vesselfinder.com": (10.0, 3.0),
    "marinetraffic.com": (10.0, 3.0),
    "marinetraffic.org": (10.0, 3.0),
}
FAIL_STATUSES = {"000", "429", "403"}
MAX_CONSEC_FAILS = 3
MAX_CONSEC_404S = 8

_META_DESC_RE = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]*?content=["\'](.*?)["\']',
    re.IGNORECASE | re.DOTALL)


def host_key(url: str) -> str:
    """Pacing / breaker key: the URL's host, lowercased, minus a leading www."""
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def host_delay(host: str, delay: float | None = None,
               jitter: float | None = None) -> tuple[float, float]:
    """(delay, jitter) for `host`. A HOST_DELAYS entry (matched on the host or
    any parent domain) is a floor: an explicit `delay` can raise it, not lower it."""
    base = DEFAULT_DELAY if delay is None else delay
    jit = DEFAULT_JITTER if jitter is None else jitter
    for domain, (d, j) in HOST_DELAYS.items():
        if host == domain or host.endswith("." + domain):
            return max(base, d), (j if jitter is None else jit)
    return base, jit


def meta_description(body: str) -> str:
    m = _META_DESC_RE.search(body or "")
    return html.unescape(m.group(1)).strip() if m else ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_records(path) -> dict:
    """Latest record per URL from a sweep JSONL ({} if the file is absent)."""
    records = {}
    p = Path(path)
    if not p.exists():
        return records
    with open(p, encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
                records[rec["url"]] = rec
            except (ValueError, KeyError, TypeError):
                continue
    return records


class _Host:
    def __init__(self):
        self.last = None         # clock() after the previous request
        self.requests = 0
        self.fails = 0           # consecutive FAIL_STATUSES
        self.not_found = 0       # consecutive 404s
        self.seen_200 = False
        self.tripped = ""        # breaker reason once tripped
        self.prior_trip = False  # tripped in an earlier run of this --out
        self.skipped = 0
        self.deferred = 0        # over --max; not recorded, picked up on re-run
        self.statuses = {}


class Sweeper:
    """Paced, breaker-guarded fetch loop over one resumable JSONL.

    `fetch`, `sleep`, `clock`, `rng` and `now` are injectable so tests run
    offline and instantly. `extract(page) -> dict` adds caller fields to each
    fetched record.
    """

    def __init__(self, out_path, *, delay=None, jitter=None,
                 max_fails=MAX_CONSEC_FAILS, max_404s=MAX_CONSEC_404S,
                 max_per_host=None, timeout=30, extract=None, fetch=None,
                 sleep=None, clock=None, rng=None, now=None, echo=print):
        self.out_path = Path(out_path)
        self.delay, self.jitter = delay, jitter
        self.max_fails, self.max_404s = max_fails, max_404s
        self.max_per_host = max_per_host
        self.timeout = timeout
        self.extract = extract
        self.fetch = fetch or fetch_page
        self.sleep = sleep or time.sleep
        self.clock = clock or time.monotonic
        self.rng = rng or random.uniform
        self.now = now or _utc_now
        self.echo = echo
        self.hosts: dict[str, _Host] = {}

    def _host(self, host: str) -> _Host:
        if host not in self.hosts:
            self.hosts[host] = _Host()
        return self.hosts[host]

    def _pace(self, host: str, st: _Host) -> None:
        if st.last is None:
            return
        delay, jitter = host_delay(host, self.delay, self.jitter)
        gap = max(0.0, delay + self.rng(-jitter, jitter))
        wait = st.last + gap - self.clock()
        if wait > 0:
            self.sleep(wait)

    def _judge(self, host: str, st: _Host, status: str) -> None:
        """Update the host's breaker counters; trip it if a threshold is met."""
        if status in FAIL_STATUSES:
            st.fails += 1
            st.not_found = 0
            limit = 1 if st.prior_trip else self.max_fails
            if st.fails >= limit:
                what = "timeout / no connection" if status == "000" else f"HTTP {status}"
                st.tripped = (f"breaker: {st.fails} consecutive failure(s) on {host} "
                              f"(last: {what})"
                              + (" after a trip in an earlier run" if st.prior_trip else ""))
            return
        st.fails = 0
        if status == "404":
            st.not_found += 1
            if st.seen_200 and st.not_found >= self.max_404s:
                st.tripped = (f"breaker: {st.not_found} consecutive 404s on {host} after "
                              f"200s — possible soft block")
            return
        st.not_found = 0
        if status == "200":
            st.seen_200 = True
            st.prior_trip = False        # the host is answering again

    def run(self, items) -> dict:
        """Fetch `items` — URLs or (url, extra_fields) pairs — in order.
        Returns {host: {...}} run stats; records go to the JSONL as they land."""
        items = [(it, {}) if isinstance(it, str) else (it[0], dict(it[1])) for it in items]
        prior = load_records(self.out_path)
        for rec in prior.values():
            if rec.get("skipped") and str(rec.get("reason", "")).startswith("breaker"):
                self._host(rec.get("host") or host_key(rec["url"])).prior_trip = True
        done = {u for u, rec in prior.items()
                if not rec.get("skipped") and str(rec.get("status")) not in FAIL_STATUSES}
        seen = set()
        todo = []
        for url, extra in items:
            if url not in done and url not in seen:
                seen.add(url)
                todo.append((url, extra))
        self.echo(f"{len(todo)} to fetch ({len(items) - len(todo)} already recorded) "
                  f"-> {self.out_path}")

        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.out_path, "a", encoding="utf-8") as out:
            for n, (url, extra) in enumerate(todo, 1):
                host = host_key(url)
                st = self._host(host)
                if st.tripped:
                    st.skipped += 1
                    self._write(out, {"url": url, "host": host, **extra, "skipped": True,
                                      "reason": st.tripped, "ts": self.now()})
                    continue
                if self.max_per_host is not None and st.requests >= self.max_per_host:
                    st.deferred += 1
                    continue
                self._pace(host, st)
                rec = {"url": url, "host": host, **extra}
                try:
                    page = self.fetch(url, timeout=self.timeout)
                    status = str(page.status)
                    rec.update(status=status, title=html.unescape(page_title(page.text or "")),
                               description=meta_description(page.text),
                               notes=list(page.notes))
                    if page.final_url and page.final_url != url:
                        rec["final_url"] = page.final_url
                    if self.extract:
                        rec.update(self.extract(page) or {})
                except Exception as e:  # noqa: BLE001 — a crash mid-sweep loses the pacing state
                    status = "000"
                    rec.update(status=status, title="", description="", notes=[f"error: {e!r}"])
                rec["ts"] = self.now()
                st.last = self.clock()
                st.requests += 1
                st.statuses[status] = st.statuses.get(status, 0) + 1
                self._write(out, rec)
                self.echo(f"[{n}/{len(todo)}] {status} {url} {rec['title'][:70]}".rstrip())
                self._judge(host, st, status)
                if st.tripped:
                    self.echo(f"!! {st.tripped}. No more requests to {host} this run; "
                              f"its remaining URLs are recorded as skipped.")
        return self.summary()

    @staticmethod
    def _write(out, rec: dict) -> None:
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()

    def summary(self) -> dict:
        return {h: {"requests": st.requests, "statuses": dict(st.statuses),
                    "tripped": st.tripped, "skipped": st.skipped, "deferred": st.deferred}
                for h, st in self.hosts.items()}


def _read_list(arg: str) -> list[str]:
    """A file (one entry per line, # comments ok) or a comma/space-separated list."""
    p = Path(arg)
    if p.is_file():
        lines = p.read_text(encoding="utf-8").splitlines()
        return [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]
    return [x for x in re.split(r"[,\s]+", arg) if x]


def _out_path(arg: str) -> Path:
    """Relative --out lands under work/ (gitignored)."""
    p = Path(arg).expanduser()
    return p if p.is_absolute() else work_dir() / p


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--urls", default="", help="file of URLs, one per line, fetched in order")
    ap.add_argument("--template", default="", help="URL template containing {imo}")
    ap.add_argument("--imos", default="", help="file of IMOs or a comma-separated list (with --template)")
    ap.add_argument("--out", default="sweep.jsonl",
                    help="JSONL path; relative paths land under work/ (default work/sweep.jsonl)")
    ap.add_argument("--delay", type=float, default=None,
                    help=f"base seconds between requests to one host (default {DEFAULT_DELAY:g}; "
                         f"tracker hosts keep their slower floor)")
    ap.add_argument("--jitter", type=float, default=None,
                    help=f"+/- seconds of random jitter (default {DEFAULT_JITTER:g}; trackers 3)")
    ap.add_argument("--max", type=int, default=None, dest="max_per_host",
                    help="cap on requests per host this run")
    ap.add_argument("--max-fails", type=int, default=MAX_CONSEC_FAILS,
                    help="consecutive 000/429/403 before a host's breaker trips")
    ap.add_argument("--max-404s", type=int, default=MAX_CONSEC_404S,
                    help="consecutive 404s (after 200s) before a host's breaker trips")
    ap.add_argument("--timeout", type=int, default=30)
    args = ap.parse_args()

    if bool(args.urls) == bool(args.template):
        ap.error("give exactly one of --urls or --template (with --imos)")
    if args.template:
        if "{imo}" not in args.template or not args.imos:
            ap.error("--template needs an {imo} placeholder and --imos")
        items = [(args.template.replace("{imo}", imo), {"imo": imo})
                 for imo in _read_list(args.imos)]
    else:
        if not Path(args.urls).is_file():
            ap.error(f"--urls file not found: {args.urls}")
        items = _read_list(args.urls)

    sweeper = Sweeper(_out_path(args.out), delay=args.delay, jitter=args.jitter,
                      max_fails=args.max_fails, max_404s=args.max_404s,
                      max_per_host=args.max_per_host, timeout=args.timeout)
    stats = sweeper.run(items)

    tripped = False
    for host, s in stats.items():
        by_status = ", ".join(f"{k}: {v}" for k, v in sorted(s["statuses"].items())) or "none"
        print(f"{host}: {s['requests']} request(s) [{by_status}]"
              + (f", {s['deferred']} deferred by --max" if s["deferred"] else ""))
        if s["tripped"]:
            tripped = True
            print(f"  STOPPED — {s['tripped']}; {s['skipped']} URL(s) skipped.\n"
                  f"  Do not re-run against {host} in a loop: status 000 on every request is "
                  f"an IP ban the fetch ladder cannot clear.\n"
                  f"  Switch source or egress, and re-test later with one request (--max 1).")
    sys.exit(1 if tripped else 0)


if __name__ == "__main__":
    main()
