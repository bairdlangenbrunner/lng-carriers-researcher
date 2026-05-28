"""
The §6a.8 IMO → marine-vessel-tracker fallback for Hull / Name / IMO [refs].

Confirmed pattern (from May 2026 pilot, rows 1148-1155):
  Given an IMO, marinetraffic.org has a per-vessel page at:
    https://www.marinetraffic.org/ship-owner-manager-ism-data/{YARD-LABEL}-{HULL}/{IMO}/1

  The IMO search endpoint resolves an IMO to its canonical per-vessel URL:
    https://www.marinetraffic.org/marine-traffic-imo-number-search?imo={IMO}

  The search response contains <a href="..."> links that include the
  yard-hull label, which is what we want to cite.

Caveats:
  - marinetraffic.org is Cloudflare-protected; aggressive scraping triggers
    soft-403s. A 0.5-1s sleep between requests is usually enough.
  - The 1XXXXXX IMO range (newbuilds pre-delivery) IS real and IS indexed.
    Don't treat these as Clarkson placeholders.

Usage:
    python imo_tracker.py 1157109
    # Prints the canonical URL and page title

    python imo_tracker.py 1157109 --verify-yard HD-HYUNDAI-SAMHO
    # Also checks that the page yard label matches the expected yard
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
import time


_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def fetch(url: str, timeout: int = 30) -> tuple[str, str, str]:
    """Returns (status, body, title)."""
    tmp = os.path.join(tempfile.gettempdir(), f"lngct_imo_{os.getpid()}.html")
    result = subprocess.run(
        ["curl", "-sL", "-A", _UA, "-o", tmp,
         "-w", "%{http_code}", "--max-time", str(timeout), url],
        capture_output=True, text=True, timeout=timeout + 5,
    )
    status = result.stdout.strip() or "000"
    try:
        with open(tmp, encoding="utf-8", errors="replace") as f:
            body = f.read()
    except Exception:
        body = ""
    title = ""
    m = re.search(r"<title[^>]*>([^<]+)</title>", body, re.IGNORECASE)
    if m:
        title = m.group(1).strip()
    return status, body, title


def lookup_imo(imo: int | str) -> dict:
    """
    Resolve an IMO to its canonical marinetraffic.org per-vessel URL.

    Returns a dict with:
      imo, search_url, search_status, canonical_urls (list),
      best_url (first canonical URL containing the IMO),
      best_title (page title of best_url), best_status
    """
    imo_str = str(imo)
    search_url = f"https://www.marinetraffic.org/marine-traffic-imo-number-search?imo={imo_str}"
    search_status, search_body, _ = fetch(search_url)

    result = {
        "imo": imo_str,
        "search_url": search_url,
        "search_status": search_status,
        "canonical_urls": [],
        "best_url": None,
        "best_title": "",
        "best_status": "",
    }

    if search_status != "200":
        return result

    # Extract canonical per-vessel links
    links = re.findall(
        r'href="(https?://www\.marinetraffic\.org/'
        r'(?:ship-owner-manager-ism-data|vessels)/[^"]+)"',
        search_body,
    )
    # Dedupe, keep only links containing the IMO
    seen, uniq = set(), []
    for l in links:
        if imo_str in l and l not in seen:
            seen.add(l)
            uniq.append(l)
    result["canonical_urls"] = uniq

    if not uniq:
        return result

    # Verify the first canonical URL
    time.sleep(0.5)
    best = uniq[0]
    best_status, best_body, best_title = fetch(best)
    result["best_url"] = best
    result["best_status"] = best_status
    result["best_title"] = best_title
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("imo", help="IMO number to look up")
    p.add_argument("--verify-yard",
                   help="Expected yard label (e.g. SAMSUNG, HD-HYUNDAI-SAMHO) — "
                        "checked against the resolved page title")
    args = p.parse_args()

    r = lookup_imo(args.imo)
    print(f"  IMO: {r['imo']}")
    print(f"  search URL: {r['search_url']}  ({r['search_status']})")
    print(f"  canonical URLs found: {len(r['canonical_urls'])}")
    for u in r["canonical_urls"][:5]:
        print(f"    {u}")
    if r["best_url"]:
        print(f"\n  best URL: {r['best_url']}")
        print(f"  best status: {r['best_status']}")
        print(f"  best title: {r['best_title']!r}")
        if args.verify_yard:
            ok = args.verify_yard.upper() in r["best_title"].upper().replace(" ", "-")
            print(f"  yard match ({args.verify_yard}): {'PASS' if ok else 'FAIL'}")
            sys.exit(0 if ok else 1)
    else:
        print(f"\n  No canonical URL found — IMO not indexed by marinetraffic.org")
        sys.exit(1)


if __name__ == "__main__":
    main()
