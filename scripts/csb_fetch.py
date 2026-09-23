"""
ChinaShipBuild yard-page fetcher and orderbook parser.

CSB is the canonical source for hull numbers under Rule A ([ref]-Fill SOP §4.4).
This script:
  1. curls a yard page with the right User-Agent (web_fetch is blocked)
  2. Parses the orderbook table from the <tr><td> structure
  3. Filters to LNG/FSRU vessels
  4. Returns a JSON-serializable list of orderbook rows

Usage:
    python csb_fetch.py samsung                    # fetch + parse one yard (page 1)
    python csb_fetch.py --all-main                 # all seven main LNGC yards
    python csb_fetch.py --all-secondary            # secondary LNGC-capable yards
    python csb_fetch.py --all-yards --all-pages    # WHOLE orderbook, every yard
    python csb_fetch.py samsung --lng-only         # filter to LNG/FSRU
    python csb_fetch.py samsung --since 2026-01    # filter by contract month

--all-pages walks each yard's orderbook to its last page instead of reading
page 1 only. Page 1 is a *window* on the orderbook -- a hull that has slipped
off it is invisible to a page-1 sweep no matter how wide the date window, which
is why a date-keyed catch-up run can never answer "what have we missed".
Paginating multiplies the request count (21 yards x up to 8 pages), so it goes
through sweep.py -- per-host pacing and a circuit breaker, never a bare loop
(CLAUDE.md, after the 2026-09-17 vesselfinder IP ban).

Output:
    <work_dir>/csb/<yard>_p<N>.html   (raw pages)
    <work_dir>/csb/<yard>.json        (parsed orderbook rows, all pages)
    <work_dir>/csb/combined.json      (every yard)
    <work_dir>/csb_orderbook_sweep.jsonl  (resumable sweep log, --all-pages)
    Prints summary to stdout.
"""
import argparse
import json
import re
import sys
import time
from html import unescape
from pathlib import Path

from fetch import FetchError, download, fetch_page
from paths import csb_dir, work_dir
from sweep import Sweeper, host_key

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

# Pagination: the orderbook's page N appends "aORDERBOOK" + this token.
# An unknown/invalid token silently serves page 1 again, which is why
# sweep_all_pages() stops on a page whose ship tokens it has already seen.
PAGE_TOKENS = {2: "4c", 3: "4X", 4: "4F", 5: "4b", 6: "4B", 7: "4C", 8: "4s"}
MAX_PAGE = max(PAGE_TOKENS)

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


def page_url(yard: str, page: int = 1) -> str:
    """The URL of a yard's orderbook page N."""
    if yard not in ALL_YARDS:
        raise ValueError(f"Unknown yard {yard!r}. Known: {sorted(ALL_YARDS)}")
    url = ALL_YARDS[yard]
    if page > 1:
        if page not in PAGE_TOKENS:
            raise ValueError(f"Page {page} pagination token not known")
        url += "aORDERBOOK" + PAGE_TOKENS[page]
    return url


def page_html_path(yard: str, page: int = 1) -> Path:
    return csb_dir() / f"{yard}_p{page}.html"


def fetch_yard_page(yard: str, page: int = 1) -> Path:
    """curl a yard page. Returns the path to the saved HTML."""
    out = page_html_path(yard, page)
    download(page_url(yard, page), out, timeout=60, min_bytes=1000)
    return out


def parse_yard_page(html_path: Path, yard: str) -> list[dict]:
    """Parse the orderbook table from a saved yard HTML page."""
    with open(html_path, encoding="utf-8", errors="replace") as f:
        return parse_orderbook_html(f.read(), yard)


def parse_orderbook_html(html: str, yard: str) -> list[dict]:
    """Parse the orderbook table out of a yard page's HTML."""
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


def sweep_all_pages(yards, *, max_page: int = MAX_PAGE, out_path=None,
                    fetch=None, sweeper=None, echo=print, **sweeper_kwargs) -> dict:
    """Walk every yard's orderbook to its last page, paced by sweep.py.

    One wave per page: page N for every yard still going, so the pacing gap
    between two requests to CSB is spent on a different yard rather than idle.
    A yard stops when a page returns no rows, repeats ship tokens already seen
    (an invalid pagination token silently re-serves page 1), the sweeper's
    breaker trips, or max_page is reached.

    Returns {yard: {"rows": [...], "pages": n, "stopped": reason}}.
    """
    yards = list(yards)
    out_path = Path(out_path) if out_path else work_dir() / "csb_orderbook_sweep.jsonl"
    base_fetch = fetch or fetch_page
    targets = {}                      # url -> (yard, page)

    def saving_fetch(url, **kw):
        """Fetch through the sweeper, keeping the HTML for the parser."""
        page = base_fetch(url, **kw)
        yard, n = targets[url]
        if str(page.status) == "200" and page.text:
            page_html_path(yard, n).write_text(page.text, encoding="utf-8")
        return page

    sw = sweeper or Sweeper(out_path, fetch=saving_fetch, echo=echo, **sweeper_kwargs)
    state = {y: {"rows": [], "pages": 0, "stopped": "", "tokens": set()} for y in yards}
    active = list(yards)

    for n in range(1, max_page + 1):
        if not active:
            break
        items = []
        for yard in active:
            url = page_url(yard, n)
            targets[url] = (yard, n)
            items.append((url, {"yard": yard, "page": n}))
        echo(f"\n-- page {n}: {len(items)} yard(s)")
        sw.run(items)

        still = []
        for yard in active:
            st = state[yard]
            host = sw.hosts.get(host_key(page_url(yard, n)))
            path = page_html_path(yard, n)
            if host is not None and host.tripped:
                st["stopped"] = host.tripped
                continue
            if not path.exists():
                st["stopped"] = f"page {n} not fetched"
                continue
            rows = parse_orderbook_html(path.read_text(encoding="utf-8", errors="replace"),
                                        yard)
            if not rows:
                st["stopped"] = f"page {n} empty"
                continue
            tokens = {r["ship_token"] for r in rows}
            if tokens <= st["tokens"]:
                # Every hull on this page was already on an earlier one: the
                # pagination token didn't advance. Not a new page.
                st["stopped"] = f"page {n} repeats page 1"
                continue
            for r in rows:
                if r["ship_token"] not in st["tokens"]:
                    st["tokens"].add(r["ship_token"])
                    st["rows"].append({**r, "page": n})
            st["pages"] = n
            if n < max_page:
                still.append(yard)
            else:
                st["stopped"] = f"max_page {max_page} reached"
        active = still

    return {y: {k: v for k, v in st.items() if k != "tokens"} for y, st in state.items()}


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
    p.add_argument("--all-yards", action="store_true",
                   help="Fetch every known yard (main + secondary)")
    p.add_argument("--all-pages", action="store_true",
                   help="Walk each yard's whole orderbook, not just page 1 "
                        "(paced through sweep.py)")
    p.add_argument("--max-page", type=int, default=MAX_PAGE,
                   help=f"Stop after this page with --all-pages (default {MAX_PAGE})")
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

    if args.all_yards:
        yards = list(ALL_YARDS)
    elif args.all_main:
        yards = list(MAIN_YARDS)
    elif args.all_secondary:
        yards = list(SECONDARY_YARDS)
    elif args.yard:
        yards = [args.yard]
    else:
        p.error("Specify a yard, --all-main, --all-secondary, --all-yards, or --list")

    out_dir = csb_dir()

    if args.all_pages:
        result = sweep_all_pages(yards, max_page=args.max_page,
                                 echo=lambda m: print(m, file=sys.stderr))
        all_rows, ok_yards = [], []
        print("", file=sys.stderr)
        for yard in yards:
            st = result[yard]
            rows = filter_rows(st["rows"], lng_only=args.lng_only, since=args.since)
            (out_dir / f"{yard}.json").write_text(json.dumps(rows, indent=2))
            print(f"  {yard:20} {len(rows):3} rows over {st['pages']} page(s)"
                  f"  [{st['stopped']}]", file=sys.stderr)
            if st["pages"]:
                ok_yards.append(yard)
            all_rows.extend(rows)
        combined = out_dir / "combined.json"
        combined.write_text(json.dumps(all_rows, indent=2))
        print(f"\n  Combined: {len(all_rows)} rows across {len(ok_yards)}/{len(yards)} "
              f"yards -> {combined}", file=sys.stderr)
        if not ok_yards:
            sys.exit("error: no yard returned an orderbook page — CSB may be down "
                     "or blocking; see the sweep log.")
        return

    all_rows = []
    ok_yards = []
    for yard in yards:
        try:
            rows = fetch_and_parse(yard, lng_only=args.lng_only, since=args.since)
        except (FetchError, RuntimeError, ValueError) as e:
            print(f"  [FAIL] {yard}: {e}", file=sys.stderr)
            continue
        out_json = out_dir / f"{yard}.json"
        out_json.write_text(json.dumps(rows, indent=2))
        print(f"  {yard:20} {len(rows):3} rows -> {out_json}", file=sys.stderr)
        all_rows.extend(rows)
        ok_yards.append(yard)
        if len(yards) > 1:
            time.sleep(0.5)  # be polite to CSB

    if len(yards) > 1:
        combined = out_dir / "combined.json"
        combined.write_text(json.dumps(all_rows, indent=2))
        print(f"\n  Combined: {len(all_rows)} rows across {len(ok_yards)} yards -> {combined}",
              file=sys.stderr)

    if not ok_yards:
        sys.exit(f"error: all {len(yards)} yard fetch(es) failed — CSB may be "
                 f"down or blocking; see [FAIL] lines above.")


if __name__ == "__main__":
    main()
