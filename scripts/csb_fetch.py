"""
ChinaShipBuild yard-page fetcher and orderbook parser.

CSB is the canonical source for hull numbers under Rule A ([ref]-Fill SOP §4.4).
This script:
  1. curls a yard page with the right User-Agent (web_fetch is blocked)
  2. Parses the orderbook table from the <tr><td> structure
  3. Filters to LNG/FSRU vessels
  4. Returns a JSON-serializable list of orderbook rows

Usage:
    python csb_fetch.py samsung                    # fetch + parse one yard
    python csb_fetch.py --all-main                 # all seven main LNGC yards
    python csb_fetch.py --all-secondary            # secondary LNGC-capable yards
    python csb_fetch.py samsung --lng-only         # filter to LNG/FSRU
    python csb_fetch.py samsung --since 2026-01    # filter by contract month

Output:
    <work_dir>/csb/<yard>.html     (raw page)
    <work_dir>/csb/<yard>.json     (parsed orderbook rows)
    Prints summary to stdout.
"""
import argparse
import json
import re
import subprocess
import sys
import time
from html import unescape
from pathlib import Path

from paths import csb_dir


# Stable per-yard URLs (from [ref]-Fill SOP §6.2 / Discovery SOP §3.1)
MAIN_YARDS = {
    "samsung": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcbganmkhTk8Pl4EN",
    "hanwha-ocean": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcJXanmkhTk8Pl4EN",
    "hyundai-ulsan": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbccbanmkhTk8Pl4EN",
    "hyundai-samho": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbccCanmkhTk8Pl4EN",
    "hyundai-mipo": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbccBanmkhTk8Pl4EN",
    "jiangnan": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4csFcanmkhTk8Pl4EN",
    "hudong-zhonghua": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4csFXanmkhTk8Pl4EN",
}

SECONDARY_YARDS = {
    "dsic-dalian": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4JJgJFanmkhTk8Pl4EN",
    "mitsubishi-hi": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BsXCg",
    "kawasaki-kobe": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BscJg",
    "zvezda": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcBSanmkhTk8Pl4EN",
    "jmu-tsu": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BscJF",
    "jmu-ariake": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcXb",
    "nacks": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcFcanmkhTk8Pl4EN",
    "dacks": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcJFanmkhTk8Pl4EN",
    "imabari-marugame": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbccSanmkhTk8Pl4EN",
    "cosco-yangzhou": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcgSanmkhTk8Pl4EN",
    "cosco-qidong": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcJganmkhTk8Pl4EN",
    "cosco-dalian": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcgBanmkhTk8Pl4EN",
    "cosco-zhoushan": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BsgFFanmkhTk8Pl4EN",
    "yantai-cimc": "http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcBBanmkhTk8Pl4EN",
}

ALL_YARDS = {**MAIN_YARDS, **SECONDARY_YARDS}

# Resolved lazily via paths.csb_dir() inside functions so that
# LNGCT_WORK_DIR can be set at process start.


# The parser pattern that survived the May 2026 pilot.
# Each orderbook row looks roughly like:
#   <tr>
#     <td>N</td>
#     <td><a href="ship.aspx?TOK">HULL</a></td>
#     <td>VESSEL_TYPE_AND_CAP</td>
#     <td>OWNER</td>
#     <td>YYYY - MM</td>   <- delivery
#     <td>YYYY - MM</td>   <- contract
#   </tr>
_ROW_RE = re.compile(
    r'<tr>\s*'
    r'<td[^>]*>(\d{1,3})</td>\s*'
    r'<td[^>]*><a href="(ship\.aspx\?[^"]+)">([^<]+)</a></td>\s*'
    r'<td[^>]*>([^<]*)</td>\s*'
    r'<td[^>]*>([^<]*)</td>\s*'
    r'<td[^>]*>([^<]*)</td>\s*'
    r'<td[^>]*>([^<]*)</td>'
)


def fetch_yard_page(yard: str, page: int = 1) -> Path:
    """curl a yard page. Returns the path to the saved HTML."""
    if yard not in ALL_YARDS:
        raise ValueError(f"Unknown yard {yard!r}. Known: {sorted(ALL_YARDS)}")
    out_dir = csb_dir()

    url = ALL_YARDS[yard]
    if page > 1:
        # Pagination: append aORDERBOOK4c (p2), aORDERBOOK4X (p3), 4F (p4), ...
        page_tokens = {2: "4c", 3: "4X", 4: "4F", 5: "4b", 6: "4B", 7: "4C", 8: "4s"}
        if page not in page_tokens:
            raise ValueError(f"Page {page} pagination token not known")
        url = url + "aORDERBOOK" + page_tokens[page]

    out = out_dir / f"{yard}_p{page}.html"
    result = subprocess.run(
        ["curl", "-sL", "-A", "Mozilla/5.0", "--max-time", "60",
         url, "-o", str(out)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"curl failed for {yard}: {result.stderr}")

    size = out.stat().st_size
    if size < 1000:
        raise RuntimeError(f"{yard} p{page} suspiciously small ({size} bytes)")
    return out


def parse_yard_page(html_path: Path, yard: str) -> list[dict]:
    """Parse the orderbook table from a yard HTML page."""
    with open(html_path, encoding="utf-8", errors="replace") as f:
        html = f.read()

    rows = []
    for m in _ROW_RE.finditer(html):
        row_num, ship_url, hull, typecap, owner, delivery, contract = m.groups()
        hull_text = unescape(hull).strip()
        # CSB displays the yard name (e.g. "Samsung HI") instead of an actual
        # hull number when the contract is very recent and CSB hasn't yet
        # assigned/indexed the hull. Real hulls always have a digit;
        # yard-name placeholders don't.
        hull_assigned = bool(re.search(r"\d", hull_text))
        rows.append({
            "yard": yard,
            "row_num": int(row_num),
            "ship_url": "http://www.chinashipbuild.com/" + ship_url,
            "ship_token": ship_url.replace("ship.aspx?", ""),
            "hull": hull_text,
            "hull_assigned": hull_assigned,
            "typecap": unescape(typecap).strip(),
            "owner": unescape(owner).strip(),
            "delivery": delivery.strip().replace(" ", ""),  # "2028-05"
            "contract": contract.strip().replace(" ", ""),  # "2026-02"
        })
    return rows


def is_lng_relevant(typecap: str) -> bool:
    """Return True if the vessel type is LNG carrier or FSRU (in-scope)."""
    t = typecap.lower()
    # Exclude small/mid-scale and bunkering per project scope
    if "bunker" in t:
        return False
    # In-scope: "LNG Tanker" and "FSRU"
    return ("lng tanker" in t or "fsru" in t)


def filter_rows(rows: list[dict], lng_only: bool = False,
                since: str | None = None) -> list[dict]:
    """Apply LNG/FSRU and contract-month filters."""
    out = rows
    if lng_only:
        out = [r for r in out if is_lng_relevant(r["typecap"])]
    if since:
        # since is "YYYY-MM"; keep rows with contract >= since (string compare works)
        out = [r for r in out if r["contract"] >= since]
    return out


def fetch_and_parse(yard: str, lng_only: bool = False,
                    since: str | None = None) -> list[dict]:
    """Fetch p1 of a yard and return parsed (optionally filtered) rows."""
    html_path = fetch_yard_page(yard, page=1)
    rows = parse_yard_page(html_path, yard)
    return filter_rows(rows, lng_only=lng_only, since=since)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("yard", nargs="?", help="Yard slug, or omit with --all-main / --all-secondary")
    p.add_argument("--all-main", action="store_true",
                   help="Fetch all seven main LNGC yards")
    p.add_argument("--all-secondary", action="store_true",
                   help="Fetch all secondary LNGC-capable yards")
    p.add_argument("--lng-only", action="store_true",
                   help="Filter to LNG/FSRU vessel types only")
    p.add_argument("--since", help="Filter to contract month >= YYYY-MM")
    p.add_argument("--list", action="store_true", help="List known yard slugs and exit")
    args = p.parse_args()

    if args.list:
        print("MAIN_YARDS:")
        for k in MAIN_YARDS:
            print(f"  {k}")
        print("\nSECONDARY_YARDS:")
        for k in SECONDARY_YARDS:
            print(f"  {k}")
        return

    if args.all_main:
        yards = list(MAIN_YARDS)
    elif args.all_secondary:
        yards = list(SECONDARY_YARDS)
    elif args.yard:
        yards = [args.yard]
    else:
        p.error("Specify a yard, --all-main, --all-secondary, or --list")

    all_rows = []
    out_dir = csb_dir()
    for yard in yards:
        try:
            rows = fetch_and_parse(yard, lng_only=args.lng_only, since=args.since)
        except Exception as e:
            print(f"  [FAIL] {yard}: {e}", file=sys.stderr)
            continue
        out_json = out_dir / f"{yard}.json"
        out_json.write_text(json.dumps(rows, indent=2))
        print(f"  {yard:20} {len(rows):3} rows -> {out_json}")
        all_rows.extend(rows)
        if len(yards) > 1:
            time.sleep(0.5)  # be polite to CSB

    if len(yards) > 1:
        combined = out_dir / "combined.json"
        combined.write_text(json.dumps(all_rows, indent=2))
        print(f"\n  Combined: {len(all_rows)} rows across {len(yards)} yards -> {combined}")


if __name__ == "__main__":
    main()
