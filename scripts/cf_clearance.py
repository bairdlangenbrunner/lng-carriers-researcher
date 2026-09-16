"""
Cloudflare clearance cookies for the vessel-tracker hosts (marinetraffic.org,
marinevesseltraffic.com and any other host that serves the JS "Just a
moment..." managed challenge).

Why this exists (2026-09-16): the challenge cannot be passed by curl, by
TLS-fingerprint impersonation, or by any browser Playwright launches (headless
or headed, Chromium/Chrome/Firefox — Turnstile spots the automation flags).
It IS passed, in about five seconds, by a real Google Chrome that we launch
ourselves with a scratch profile and drive over the DevTools protocol using
only the Target/DOM/Storage domains (never `Runtime.enable`, the tell that
Turnstile looks for). The `cf_clearance` cookie Chrome receives is valid for a
year and is honoured for plain `curl` requests as long as the User-Agent
string matches the Chrome that earned it (it is also bound to our egress IP,
so it silently stops working when the laptop changes networks — refresh again).

Library usage (fetch.py calls these; nothing else should need to):
    from cf_clearance import cookie_for, refresh, ClearanceError

    hit = cookie_for("https://www.marinetraffic.org/...")   # (value, ua) | None
    refresh([url])          # opens Chrome, waits for the challenge, stores the cookie

CLI:
    python scripts/cf_clearance.py https://www.marinetraffic.org/ https://www.marinevesseltraffic.com/
    python scripts/cf_clearance.py --show

Store: work/cf_clearance.json (gitignored — the cookie is a credential-like
token for this IP; never commit it). Set LNGCT_NO_BROWSER=1 to forbid the
Chrome launch (CI, unattended runs): fetch.py then reports the wall as blocked.
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from paths import work_dir

CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
)
CDP_PORT = int(os.environ.get("LNGCT_CDP_PORT", "9333"))
CHALLENGE_TITLES = ("just a moment", "verify you are human", "attention required",
                    "checking your browser", "please wait")
COOKIE_NAME = "cf_clearance"


class ClearanceError(RuntimeError):
    pass


def store_path() -> Path:
    return work_dir() / "cf_clearance.json"


def profile_dir() -> Path:
    return work_dir() / "chrome_profile"


def browser_allowed() -> bool:
    return os.environ.get("LNGCT_NO_BROWSER", "") not in ("1", "true", "yes")


def load_store() -> dict:
    """{"ua": str, "cookies": {domain: {"value": str, "expires": float, "saved": float}}}"""
    try:
        d = json.loads(store_path().read_text())
        d.setdefault("cookies", {})
        return d
    except (OSError, ValueError):
        return {"ua": "", "cookies": {}}


def save_store(store: dict) -> None:
    p = store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(store, indent=1))


def _domain_matches(host: str, domain: str) -> bool:
    d = domain.lstrip(".").lower()
    return host == d or host.endswith("." + d)


def cookie_for(url: str, store: dict | None = None) -> tuple[str, str] | None:
    """(cf_clearance value, User-Agent it was earned with) for url's host, or None."""
    host = (urlsplit(url).hostname or "").lower()
    if not host:
        return None
    store = store if store is not None else load_store()
    now = time.time()
    for domain, c in store.get("cookies", {}).items():
        if _domain_matches(host, domain) and c.get("value") and c.get("expires", 0) > now:
            return c["value"], store.get("ua", "")
    return None


def forget(url: str) -> None:
    """Drop the stored cookie for url's host (it stopped working)."""
    store = load_store()
    host = (urlsplit(url).hostname or "").lower()
    for domain in [d for d in store["cookies"] if _domain_matches(host, d)]:
        del store["cookies"][domain]
    save_store(store)


# ---------------------------------------------------------------------------
# Chrome over the DevTools protocol
# ---------------------------------------------------------------------------

def _chrome_binary() -> str:
    for c in CHROME_CANDIDATES:
        if os.path.isabs(c) and os.path.exists(c):
            return c
        if not os.path.isabs(c) and shutil.which(c):
            return c
    raise ClearanceError(
        "Google Chrome not found — install it (https://www.google.com/chrome/) or "
        "add its path to CHROME_CANDIDATES in scripts/cf_clearance.py")


class _CDP:
    """Minimal DevTools client: one browser websocket, flat sessions."""

    def __init__(self, ws_url: str):
        try:
            import websocket  # websocket-client
        except ImportError as e:
            raise ClearanceError("pip install websocket-client (needed to drive Chrome)") from e
        self.ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=60)
        self._id = 0

    def send(self, method: str, params: dict | None = None, session: str | None = None) -> dict:
        self._id += 1
        msg = {"id": self._id, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        self.ws.send(json.dumps(msg))
        while True:
            r = json.loads(self.ws.recv())
            if r.get("id") == self._id:
                if "error" in r:
                    raise ClearanceError(f"CDP {method}: {r['error']}")
                return r.get("result", {})

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass


def _launch_chrome(port: int) -> tuple[subprocess.Popen, dict]:
    binary = _chrome_binary()
    prof = profile_dir()
    prof.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [binary, f"--user-data-dir={prof}", f"--remote-debugging-port={port}",
         "--no-first-run", "--no-default-browser-check", "--window-size=1200,900",
         "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    version = None
    for _ in range(80):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as r:
                version = json.load(r)
            break
        except Exception:
            time.sleep(0.25)
    if version is None:
        proc.terminate()
        raise ClearanceError(f"Chrome did not open its DevTools port {port} "
                             f"(another Chrome on that port? set LNGCT_CDP_PORT)")
    return proc, version


def _is_challenge_title(title: str) -> bool:
    t = (title or "").lower()
    return not t or any(f in t for f in CHALLENGE_TITLES)


def refresh(urls: list[str], wait: int = 60, port: int = CDP_PORT) -> dict:
    """
    Open each URL in a real Chrome, wait for its Cloudflare challenge to clear,
    harvest every cf_clearance cookie the browser now holds and merge them into
    the store. Returns the store. Raises ClearanceError when Chrome is missing,
    the browser is forbidden (LNGCT_NO_BROWSER), or no URL cleared.
    """
    if not browser_allowed():
        raise ClearanceError("browser launch forbidden by LNGCT_NO_BROWSER")
    proc, version = _launch_chrome(port)
    cdp = _CDP(version["webSocketDebuggerUrl"])
    cleared: list[str] = []
    try:
        for url in urls:
            tid = cdp.send("Target.createTarget", {"url": url})["targetId"]
            title = ""
            deadline = time.time() + wait
            while time.time() < deadline:
                time.sleep(2.5)
                info = [t for t in cdp.send("Target.getTargets")["targetInfos"]
                        if t["targetId"] == tid]
                title = info[0]["title"] if info else ""
                if not _is_challenge_title(title):
                    cleared.append(url)
                    break
            print(f"  [cf_clearance] {url} -> {title!r}", file=sys.stderr)
            cdp.send("Target.closeTarget", {"targetId": tid})
        cookies = cdp.send("Storage.getCookies").get("cookies", [])
    finally:
        cdp.close()
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    store = load_store()
    store["ua"] = version.get("User-Agent", store.get("ua", ""))
    now = time.time()
    for c in cookies:
        if c.get("name") == COOKIE_NAME and c.get("value"):
            store["cookies"][c["domain"]] = {"value": c["value"],
                                             "expires": float(c.get("expires") or now + 1800),
                                             "saved": now}
    save_store(store)
    if not cleared:
        raise ClearanceError("no URL cleared the challenge within the wait "
                             f"({wait}s) — is the site down, or the network captive?")
    return store


def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("urls", nargs="*", help="URLs whose Cloudflare challenge to clear")
    p.add_argument("--show", action="store_true", help="print the stored cookies and exit")
    p.add_argument("--wait", type=int, default=60, help="seconds to wait per URL")
    args = p.parse_args()
    store = load_store()
    if args.show or not args.urls:
        print(f"store: {store_path()}")
        print(f"ua: {store.get('ua') or '(none)'}")
        for d, c in sorted(store.get("cookies", {}).items()):
            left = c.get("expires", 0) - time.time()
            print(f"  {d:36s} expires in {left/86400:6.1f} d  {c['value'][:12]}…")
        if not args.urls:
            return
    try:
        store = refresh(args.urls, wait=args.wait)
    except ClearanceError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"stored {len(store['cookies'])} cookie(s) in {store_path()}")


if __name__ == "__main__":
    main()
