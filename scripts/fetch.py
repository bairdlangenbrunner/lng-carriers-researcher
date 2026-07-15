"""
Shared curl wrapper for every network-touching script.

All fetching in this repo shells out to the `curl` binary rather than a Python
HTTP library — a deliberate choice: several sources (Google Sheets export,
ChinaShipBuild, marinetraffic.org) block or degrade non-browser clients, and
curl with a browser User-Agent has been the reliable path since the May 2026
pilot. The cost is a system dependency that pip can't declare, so this module
checks for curl up front and fails with an actionable message instead of a
raw FileNotFoundError.

Library usage:
    from fetch import download, fetch_text, CHROME_UA, FetchError

    download(url, out_path, timeout=60)          # save body to a file
    status, body = fetch_text(url, timeout=30)   # ("200", "<html>...")
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# One canonical browser UA for the whole repo. pull_backend/csb_fetch used a
# bare "Mozilla/5.0" and url_verifier/imo_tracker a full Chrome string; the
# full string works everywhere the bare one did.
CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_CURL_INSTALL_HINT = (
    "curl not found on PATH. Install it and re-run:\n"
    "  macOS:         xcode-select --install  (or `brew install curl`)\n"
    "  Debian/Ubuntu: sudo apt install curl\n"
    "  Windows:       ships with Windows 10+; otherwise winget install curl"
)


class FetchError(RuntimeError):
    pass


def require_curl() -> None:
    """Raise FetchError with install instructions if curl is missing."""
    if shutil.which("curl") is None:
        raise FetchError(_CURL_INSTALL_HINT)


def download(url: str, out_path: str | Path, *, timeout: int = 60,
             ua: str = CHROME_UA, min_bytes: int | None = None) -> Path:
    """
    curl `url` to `out_path`. Raises FetchError if curl fails or (when
    min_bytes is set) the body is suspiciously small — e.g. a Google Sheet
    that's no longer public, or a CSB error page.
    """
    require_curl()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["curl", "-sL", "-A", ua, "--max-time", str(timeout),
         url, "-o", str(out_path)],
        capture_output=True, text=True, timeout=timeout + 10,
    )
    if result.returncode != 0:
        raise FetchError(f"curl failed for {url}: {result.stderr.strip()}")
    if min_bytes is not None:
        size = out_path.stat().st_size
        if size < min_bytes:
            raise FetchError(
                f"{url} returned a suspiciously small body ({size} bytes; "
                f"expected >= {min_bytes}) — check the URL is still valid "
                f"and publicly accessible."
            )
    return out_path


def fetch_text(url: str, *, timeout: int = 30,
               ua: str = CHROME_UA) -> tuple[str, str]:
    """
    Fetch `url`, return (http_status, body_text). HTTP errors are reported in
    the status string ("404", "000" when curl couldn't connect), never raised —
    callers like the §3.8 gate turn them into (False, reason). Only a missing
    curl binary raises (FetchError).

    The body lands in a private temp file that is always cleaned up.
    """
    require_curl()
    fd, tmp = tempfile.mkstemp(prefix="lngct_fetch_", suffix=".html")
    os.close(fd)
    try:
        result = subprocess.run(
            ["curl", "-sL", "-A", ua, "-o", tmp,
             "-w", "%{http_code}", "--max-time", str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 10,
        )
        status = result.stdout.strip() or "000"
        if result.returncode != 0:
            # Surface the failure instead of silently treating it as an
            # empty page (the old behavior masked DNS/TLS errors).
            print(f"  [fetch] curl error for {url}: {result.stderr.strip()}",
                  file=sys.stderr)
        try:
            text = Path(tmp).read_bytes().decode("utf-8", errors="replace")
        except OSError as e:
            print(f"  [fetch] could not read body for {url}: {e}", file=sys.stderr)
            text = ""
        return status, text
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def page_title(body: str) -> str:
    """Extract the <title> text of an HTML body ("" if none)."""
    m = re.search(r"<title[^>]*>([^<]+)</title>", body, re.IGNORECASE)
    return m.group(1).strip() if m else ""
