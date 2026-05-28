"""
URL verification harness for the LNG Carrier Tracker [ref]-fill workflow.

Per [ref]-Fill SOP §3.8 / Rule D §4.11: every URL cited in a [ref] cell MUST be
verified to (1) return HTTP 200, AND (2) contain the entities it's cited for,
AND (3) not be a soft-error page (200 with "404"/"429"/etc. in the title).

Two modes:
  - strict=True: raises CitationError on failure (use in build scripts where
    a broken URL is a hard error)
  - strict=False: returns (False, reason) — caller drops the URL from the
    citation bundle silently (use for best-effort propagation)

A per-process cache prevents re-fetching the same URL multiple times in one
build. The cache is in-memory only — clear between builds.

CLI usage:
    python url_verifier.py <url> <expected1> [<expected2> ...]
    # exits 0 if URL passes, 1 if not

Library usage:
    from url_verifier import verify_url, verify_and_format
    ok, reason = verify_url("https://...", ["Owner Name", "Yard Name", "174,000"])
    # or
    url_or_none = verify_and_format(url, expected)  # None if failed
"""
import os
import re
import subprocess
import sys
import tempfile


class CitationError(Exception):
    pass


# Per-process cache so the same URL isn't re-fetched within a build
_CACHE: dict[str, tuple[str, str]] = {}

_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Soft-error signals: HTTP 200 but title indicates an error template
_SOFT_ERROR_TITLES = (
    "404", "429", "503",
    "not found", "page not found",
    "too many requests",
    "access denied", "forbidden",
    "temporarily unavailable",
    "just a moment",  # Cloudflare interstitial
    "attention required",  # Cloudflare block
)


def _fetch(url: str, timeout: int = 30, ua: str = _DEFAULT_UA) -> tuple[str, str]:
    """Fetch URL, return (status_code, body_text). Cached per URL per process."""
    if url in _CACHE:
        return _CACHE[url]

    # Use a per-process scratch file under the OS temp dir, not a fixed
    # /tmp path. Avoids collisions if multiple verifier processes run.
    tmp = os.path.join(tempfile.gettempdir(), f"lngct_verify_{os.getpid()}.html")
    result = subprocess.run(
        ["curl", "-sL", "-A", ua, "-o", tmp,
         "-w", "%{http_code}", "--max-time", str(timeout), url],
        capture_output=True, text=True, timeout=timeout + 5,
    )
    status = result.stdout.strip() or "000"
    try:
        with open(tmp, "rb") as f:
            body = f.read()
        text = body.decode("utf-8", errors="replace")
    except Exception:
        text = ""

    _CACHE[url] = (status, text)
    return status, text


def verify_url(url: str, expected: list[str], strict: bool = False,
               require_all: bool = True) -> tuple[bool, str]:
    """
    Verify URL passes three checks:
      1. HTTP 200
      2. Not a soft-error page (title doesn't contain error indicators)
      3. Body contains the strings in `expected` (case-insensitive)

    Args:
        url: the URL to verify
        expected: list of substrings that must appear in the page body.
                  Examples for cluster coherence (Rule E): [owner, yard, hull-count]
                  Examples for value presence (Rule F): [owner, yard, "174,000"]
        strict: if True, raise CitationError on failure instead of returning False
        require_all: if True (default), every expected substring must be present.
                     If False, at least one must be present (rarely correct — Rule F
                     basically always wants require_all=True).

    Returns:
        (ok: bool, reason: str)
    """
    status, text = _fetch(url)

    if status != "200":
        reason = f"HTTP {status}"
        if strict:
            raise CitationError(f"URL failed verification ({reason}): {url}")
        return False, reason

    # Soft-error detection
    title_match = re.search(r"<title[^>]*>([^<]+)</title>", text, re.IGNORECASE)
    if title_match:
        title = title_match.group(1).lower()
        for bad in _SOFT_ERROR_TITLES:
            if bad in title:
                reason = f"soft-error page (title: {title_match.group(1).strip()!r})"
                if strict:
                    raise CitationError(f"URL failed verification ({reason}): {url}")
                return False, reason

    # Content check
    text_lower = text.lower()
    found = [s for s in expected if s.lower() in text_lower]
    missing = [s for s in expected if s.lower() not in text_lower]

    if require_all and missing:
        reason = f"missing expected content: {missing}"
        if strict:
            raise CitationError(f"URL failed verification ({reason}): {url}")
        return False, reason
    if not require_all and not found:
        reason = f"none of expected content found: {expected}"
        if strict:
            raise CitationError(f"URL failed verification ({reason}): {url}")
        return False, reason

    return True, "OK"


def verify_and_format(url: str, expected: list[str]) -> str | None:
    """
    Verify a URL. If it passes, return the URL.
    If it fails, return None and log the reason to stderr.

    Use in build scripts so failed URLs are silently dropped from citations
    rather than written into the xlsx.
    """
    ok, reason = verify_url(url, expected, strict=False)
    if ok:
        return url
    print(f"  [CITATION DROPPED] {url}\n    reason: {reason}", file=sys.stderr)
    return None


def clear_cache() -> None:
    """Clear the in-memory cache. Call between builds."""
    _CACHE.clear()


def main():
    if len(sys.argv) < 2:
        print("Usage: python url_verifier.py <url> [<expected1> <expected2> ...]")
        sys.exit(2)
    url = sys.argv[1]
    expected = sys.argv[2:]
    ok, reason = verify_url(url, expected, strict=False, require_all=True)
    print(f"  URL: {url}")
    print(f"  Expected: {expected}")
    print(f"  Result: {'PASS' if ok else 'FAIL'}  ({reason})")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
