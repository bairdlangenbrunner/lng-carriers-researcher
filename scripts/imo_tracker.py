"""
The §6a.8 IMO → vessel-tracker fallback for Hull / Name / IMO [refs].

Two indexes, tried in order (both cover the pre-delivery 1XXXXXX IMO range —
those are real IMOs, not Clarkson placeholders):

  1. shipvault.com — primary since 2026-09-16. The site is an Angular SPA
     over an open backend (no auth, no Cloudflare):
       GET https://shipvaultapi-gjb8c.ondigitalocean.app/api/units/shipsearch/{IMO}?page=1&pageSize=50
           (headers: tx=<tenant id>, Origin: https://www.shipvault.com)
           -> JSON-encoded string holding [{id, parentname, name, status, imo, owner, ...}]
       GET https://shipvaultapi-gjb8c.ondigitalocean.app/api/units/{id}
           -> [{unitid, name, imo, yard, yardsite, yardno, owner, status, ordered,
                built, month, cap1, ctype1, newprice, ...}]
     The citable page is https://www.shipvault.com/ships/{id}; the verifier's
     shipvault adapter checks it against the same unit record.

  2. marinetraffic.org — the May 2026 pilot route, kept as the secondary:
       https://www.marinetraffic.org/marine-traffic-imo-number-search?imo={IMO}
     resolves to the per-vessel page
       https://www.marinetraffic.org/ship-owner-manager-ism-data/{YARD-LABEL}-{HULL}/{IMO}/1
     Cloudflare's JS challenge is cleared by fetch.py (real-Chrome clearance
     cookie, see cf_clearance.py) — the first call in a session may open a
     Chrome window for a few seconds.

Usage:
    python scripts/imo_tracker.py 1157109
    python scripts/imo_tracker.py 1157109 --verify-yard HD-HYUNDAI-SAMHO
    python scripts/imo_tracker.py 1157109 --no-marinetraffic   # shipvault only
"""
import argparse
import json
import re
import sys
import time

from fetch import fetch_page, fetch_text, page_title

SHIPVAULT_API = "https://shipvaultapi-gjb8c.ondigitalocean.app/api/units"
SHIPVAULT_HEADERS = {"tx": "06fa22ce-fd30-44e9-a7d3-2147d4b72d26",
                     "Origin": "https://www.shipvault.com", "Accept": "application/json"}
SHIPVAULT_PAGE = "https://www.shipvault.com/ships/{id}"


def _json(text: str):
    try:
        d = json.loads(text)
    except (ValueError, TypeError):
        return None
    if isinstance(d, str):
        try:
            d = json.loads(d)
        except (ValueError, TypeError):
            return None
    return d


def shipvault_search(imo: int | str) -> list[dict]:
    """shipvault hits for an IMO (exact-IMO matches only), each with the citable `url`."""
    imo_str = str(imo).strip()
    p = fetch_page(f"{SHIPVAULT_API}/shipsearch/{imo_str}?page=1&pageSize=50",
                   headers=SHIPVAULT_HEADERS)
    data = _json(p.text) if p.status == "200" else None
    if not isinstance(data, list):
        return []
    hits = []
    for h in data:
        if not isinstance(h, dict) or str(h.get("imo") or "") != imo_str:
            continue
        hits.append({**h, "url": SHIPVAULT_PAGE.format(id=h.get("id"))})
    return hits


def shipvault_unit(unit_id: int | str) -> dict | None:
    """Full shipvault unit record (yard, yardno, owner, status, built...)."""
    p = fetch_page(f"{SHIPVAULT_API}/{unit_id}", headers=SHIPVAULT_HEADERS)
    data = _json(p.text) if p.status == "200" else None
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    return None


def marinetraffic_org(imo: int | str) -> dict:
    """The marinetraffic.org route: search page -> canonical per-vessel URL -> title."""
    imo_str = str(imo).strip()
    search_url = f"https://www.marinetraffic.org/marine-traffic-imo-number-search?imo={imo_str}"
    status, body = fetch_text(search_url)
    out = {"search_url": search_url, "search_status": status, "canonical_urls": [],
           "best_url": None, "best_status": "", "best_title": ""}
    if status != "200":
        return out
    links = re.findall(
        r'href="(https?://www\.marinetraffic\.org/'
        r'(?:ship-owner-manager-ism-data|vessels)/[^"]+)"', body)
    seen, uniq = set(), []
    for link in links:
        if imo_str in link and link not in seen:
            seen.add(link)
            uniq.append(link)
    # the search endpoint often answers with the vessel page itself
    canon = re.search(r'<link rel="canonical" href="([^"]+)"', body)
    if canon and imo_str in canon.group(1) and canon.group(1) not in seen:
        uniq.insert(0, canon.group(1))
    out["canonical_urls"] = uniq
    if not uniq:
        return out
    best = uniq[0]
    if canon and best == canon.group(1):
        out.update(best_url=best, best_status=status, best_title=page_title(body))
        return out
    time.sleep(0.5)
    st, bd = fetch_text(best)
    out.update(best_url=best, best_status=st, best_title=page_title(bd))
    return out


def lookup_imo(imo: int | str, marinetraffic: bool = True) -> dict:
    """
    Resolve an IMO to citable tracker URLs.

    Returns {imo, shipvault: [hits], shipvault_unit: record|None, best_url,
             best_title, marinetraffic_org: {...}|None}. best_url is the
    shipvault page when shipvault knows the IMO, else the marinetraffic.org
    per-vessel page, else None.
    """
    imo_str = str(imo).strip()
    result = {"imo": imo_str, "shipvault": [], "shipvault_unit": None,
              "best_url": None, "best_title": "", "marinetraffic_org": None}
    hits = shipvault_search(imo_str)
    result["shipvault"] = hits
    if hits:
        unit = shipvault_unit(hits[0]["id"])
        result["shipvault_unit"] = unit
        result["best_url"] = hits[0]["url"]
        name = (unit or hits[0]).get("name") or ""
        yard = (unit or {}).get("yard") or ""
        result["best_title"] = f"{yard} {name}".strip() if yard else name
    if marinetraffic:
        mt = marinetraffic_org(imo_str)
        result["marinetraffic_org"] = mt
        if not result["best_url"] and mt["best_url"] and mt["best_status"] == "200":
            result["best_url"] = mt["best_url"]
            result["best_title"] = mt["best_title"]
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("imo", help="IMO number to look up")
    p.add_argument("--verify-yard",
                   help="Expected yard label (e.g. SAMSUNG, HD-HYUNDAI-SAMHO) — "
                        "checked against the resolved yard / page title")
    p.add_argument("--no-marinetraffic", action="store_true",
                   help="shipvault only (skip the marinetraffic.org route)")
    args = p.parse_args()

    r = lookup_imo(args.imo, marinetraffic=not args.no_marinetraffic)
    print(f"  IMO: {r['imo']}")
    print(f"  shipvault hits: {len(r['shipvault'])}")
    for h in r["shipvault"][:5]:
        print(f"    {h['url']}  {h.get('name')!r} owner={h.get('owner')!r} "
              f"status={h.get('status')!r} built={h.get('built')}")
    u = r["shipvault_unit"]
    if u:
        print(f"    yard={u.get('yard')!r} site={u.get('yardsite')!r} yardno={u.get('yardno')!r} "
              f"ordered={str(u.get('ordered') or '')[:10]} delivery={u.get('built')}-{u.get('month')} "
              f"cap={u.get('cap1')} {u.get('ctype1') or ''}")
    mt = r["marinetraffic_org"]
    if mt:
        print(f"  marinetraffic.org search: {mt['search_url']}  ({mt['search_status']})")
        for c in mt["canonical_urls"][:3]:
            print(f"    {c}")
        if mt["best_url"]:
            print(f"    -> {mt['best_status']} {mt['best_title']!r}")
    if r["best_url"]:
        print(f"\n  best URL: {r['best_url']}")
        print(f"  best title: {r['best_title']!r}")
        if args.verify_yard:
            hay = r["best_title"].upper().replace(" ", "-")
            if u and u.get("yard"):
                hay += " " + str(u["yard"]).upper().replace(" ", "-")
            ok = args.verify_yard.upper() in hay
            print(f"  yard match ({args.verify_yard}): {'PASS' if ok else 'FAIL'}")
            sys.exit(0 if ok else 1)
    else:
        print("\n  No tracker URL found — IMO not indexed by shipvault or marinetraffic.org")
        sys.exit(1)


if __name__ == "__main__":
    main()
