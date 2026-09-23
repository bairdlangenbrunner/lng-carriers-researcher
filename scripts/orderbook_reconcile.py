"""
Whole-orderbook reconciliation — CSB || backend || IGU Appendix 4 || shipvault.

Every discovery run before this one was a *gap-window catch-up*: pick a
contract-date window, sweep CSB page 1, compare. That finds the leading edge
and nothing else. A hull that slipped off page 1, or an order whose contract
date we never knew, is invisible to it at any window width.

This is the completeness form of the same question. It is NOT date-bounded: it
puts every source's orderbook next to the backend's and makes the counts
balance yard by yard. Three residues come out, and each means something
different:

  csb_unmatched      a hull on a yard's orderbook with no backend row AT ALL
                     -> a discovery candidate (needs press before it is one).
                        A hull key alone CANNOT say this: csb_fetch parses the
                        yard's orderbook list, which carries no IMO, so every
                        vessel the backend holds under a name instead of a hull
                        reads as absent. On 2026-09-23 all nine survivors did:
                        Hanwha 2593-2596 are rows 1031/1032/1034/1035, Qatar
                        9/10 are rows 888/889, Dalian G175K-5 is row 814. The
                        ship-detail page DOES print the IMO, so --resolve-imo
                        fetches the survivors' pages and re-keys on it. Never
                        call a CSB hull absent without that pass.
  csb_no_hull        a CSB orderbook slot the yard has not indexed a hull for
                     -> cluster-level only; count against the backend, never
                        matched vessel by vessel
  csb_status         a CSB hull whose backend row is not `on order`
                     -> CSB still carries it; the backend has moved it on
                        (usually delivered). Informational, not a candidate.
  igu_unmatched      an IGU orderbook IMO with no backend row
                     -> ditto; IGU 2026 is citable (cite the report PDF)
  backend_only       a backend `on order` row no source's orderbook carries
                     -> a REVERSE flag: a phantom, a duplicate, or (most often)
                        a vessel already delivered and not yet re-Statused

Hull keying is `builder_tag|hull_core()` (normalize.hull_core): the sources
write the same hull three ways ("Samsung 2808" / "Hull 2316 (SHI)" /
"Jiangnan H2709" vs "Hull 2702"), and normalize_hull() only canonicalizes the
CSB shape, so keying on it matched nothing at all.

Counts, not identities, are the point for IGU's no-IMO rows: IGU prints 46
orderbook rows with no IMO, in clusters of sister ships. Whether the backend
holds N rows where IGU holds N is answerable; which row is which is not.

Nothing here edits the backend — it writes one JSON for the batch to read.

Usage:
    python scripts/csb_fetch.py --all-yards --all-pages --lng-only   # Ring A first
    python scripts/orderbook_reconcile.py [--edition 2026]
    # -> work/orderbook_reconcile.json
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from backend_io import load_backend
from csb_fetch import ALL_YARDS, is_lng_relevant
from dedup_index import base_key, name_key
from normalize import hull_core, normalize_builder, normalize_owner
from paths import csb_dir, work_dir

# CSB yard slug -> the canonical builder tag normalize_builder() returns.
# Most slugs already are the tag; these four are the yard-site's own spelling.
SLUG_TO_TAG = {"dsic-dalian": "dsic", "mitsubishi-hi": "mitsubishi",
               "kawasaki-kobe": "kawasaki", "imabari-marugame": "imabari"}

# Capacity counts as the same vessel within this much (cbm) — IGU rounds, CSB
# quotes the design figure, the backend carries whatever the contract said.
CAPACITY_TOL = 6000


def yard_tag(slug: str) -> str:
    return SLUG_TO_TAG.get(slug, slug)


def load_csb(path=None) -> list:
    """The all-pages CSB sweep, LNG/FSRU only."""
    p = Path(path) if path else csb_dir() / "combined.json"
    if not p.exists():
        sys.exit(f"error: {p} not found — run "
                 f"`python scripts/csb_fetch.py --all-yards --all-pages --lng-only` first.")
    return [r for r in json.loads(p.read_text()) if is_lng_relevant(r.get("typecap", ""))]


def load_igu(edition: int) -> dict:
    p = work_dir() / f"igu_fleet_{edition}.json"
    if not p.exists():
        sys.exit(f"error: {p} not found — run `python scripts/igu_fleet.py <pdf>` first.")
    return json.loads(p.read_text())


def backend_rows(be) -> list:
    """Every backend row, keyed the way the sources are.

    All rows, not just `on order`: a hull CSB still lists whose backend row has
    already flipped to `active` is not a missing vessel, and counting it as one
    is how a completeness sweep manufactures phantom candidates.
    """
    cm, rows = be.colmap, []
    srm = be.sheet_row_map()
    for i, row in enumerate(be.data):
        rid = be.cell(row, cm["row_id"])
        builder = be.cell(row, cm["shipbuilder"])
        tag = normalize_builder(builder)
        hull_raw = be.cell(row, cm["hull"])
        rows.append({
            "row_id": rid, "sheet_row": srm.get(rid, be.data_start + i + 1),
            "name": be.cell(row, cm["name"]), "imo": be.cell(row, cm["imo"]),
            "status": be.cell(row, cm["status"]).strip().lower(),
            "builder": builder, "builder_tag": tag,
            "hull": hull_raw, "hull_core": hull_core(hull_raw),
            "owner": be.cell(row, cm["shipowner"]),
            "owner_tag": normalize_owner(be.cell(row, cm["shipowner"])),
            "capacity": _int(be.cell(row, cm["capacity"])),
            "delivery_year": _int(be.cell(row, cm["delivery_year"])),
        })
    return rows


def enrich_stubs(all_rows, batch_dirs) -> int:
    """Give a stub row back the attributes its batch proposed for it.

    A discovery batch's accepted vessels get pasted into the sheet columns A-E
    only -- Name and IMO, no Shipbuilder / Shipowner / Capacity / Status (sheet
    rows 1220-1231 today). Such a row is invisible to every match this script
    makes, so an orderbook that lists the vessel reads as a discovery candidate
    and the pass re-proposes what is already in the sheet. The batch that
    produced the row still holds the full `row_data`, so borrow it -- for
    matching only; nothing is written anywhere.
    """
    cands, bases = {}, defaultdict(list)
    for d in batch_dirs:
        f = Path(d) / "candidates.json"
        if not f.exists():
            continue
        for c in json.loads(f.read_text()).get("candidates", []):
            rd = c.get("row_data", {}) or {}
            if rd.get("Name"):
                cands[name_key(rd["Name"])] = (Path(d).name, rd)
                bases[base_key(name_key(rd["Name"]))].append((Path(d).name, rd))
    n = 0
    for r in all_rows:
        if r["status"] or r["builder_tag"] or r["owner_tag"]:
            continue
        nk = name_key(r["name"])
        hit = cands.get(nk)
        if not hit:
            # A one-vessel cluster carries an ordinal in the workbook
            # ("(unknown shipowner 1)") that the paste usually drops. Only
            # where exactly one candidate has that ordinal-free base.
            same = bases.get(base_key(nk), [])
            hit = same[0] if len(same) == 1 else None
        if not hit:
            continue
        batch, rd = hit
        r["builder_tag"] = normalize_builder(rd.get("Shipbuilder", ""))
        r["owner_tag"] = normalize_owner(rd.get("Shipowner", ""))
        r["owner"] = r["owner"] or rd.get("Shipowner", "")
        r["capacity"] = r["capacity"] or _int(rd.get("Capacity (cbm)", ""))
        r["delivery_year"] = r["delivery_year"] or _int(rd.get("Delivery year", ""))
        r["hull_core"] = r["hull_core"] or hull_core(rd.get("Hull number", ""))
        r["stub_from"] = batch
        n += 1
    return n


def _near_misses(c, all_rows, limit=3) -> list:
    """Backend rows one field away from a CSB residue, with the field named."""
    cap, year = _typecap_capacity(c.get("typecap", "")), _year(c.get("delivery", ""))
    owner = normalize_owner(c.get("owner", ""))
    out = []
    # an undelivered row first -- it is the one a residue is usually a form of
    for b in sorted(all_rows, key=lambda r: r["status"] not in ("on order", "")):
        if b["builder_tag"] != c["builder_tag"]:
            continue
        if owner and b["owner_tag"] and b["owner_tag"] != owner:
            continue
        near_year = year and b["delivery_year"] and abs(b["delivery_year"] - year) <= 1
        if b["status"] not in ("on order", "") and not near_year:
            continue                       # a vessel delivered years ago is not a near miss
        why = []
        if cap and b["capacity"] and abs(b["capacity"] - cap) > CAPACITY_TOL:
            why.append(f"capacity {b['capacity']} vs CSB {cap}")
        if year and b["delivery_year"] and b["delivery_year"] != year:
            why.append(f"delivery {b['delivery_year']} vs CSB {year}")
        if b["hull_core"]:
            why.append(f"row already holds hull {b['hull']}")
        if not why or len(why) > 1:
            continue                       # exact sibling, or too far to be one
        out.append({"sheet_row": b["sheet_row"], "name": b["name"],
                    "status": b["status"] or "(stub)", "owner": b["owner"],
                    "differs": why[0]})
        if len(out) >= limit:
            break
    return out


def _typecap_capacity(typecap: str):
    """The cbm figure out of CSB's "LNG Tanker, 174,000 cbm"."""
    m = re.search(r"([\d,]{4,})\s*cbm", str(typecap or ""), re.I)
    return _int(m.group(1)) if m else None


def _year(ym: str):
    """The year out of CSB's "2029-06" / "2029"."""
    m = re.match(r"(\d{4})", str(ym or "").strip())
    return int(m.group(1)) if m else None


def _int(v):
    try:
        return int(float(str(v).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


_SHIP_IMO_RE = re.compile(r"IMO:\s*([0-9]{6,8})")


def _parse_ship_imo(html: str) -> str:
    """The IMO a CSB ship-detail page prints, or ''.

    Anchored after "Ship's Name" so a stray number elsewhere on the page (the
    site's footer, a related-vessel link) can never be read as this ship's.
    """
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or ""))
    i = text.find("Ship's Name")
    if i < 0:
        return ""
    m = _SHIP_IMO_RE.search(text[i:i + 600])
    return m.group(1) if m else ""


def resolve_ship_imos(records, *, cache_path=None, delay=6.0) -> dict:
    """{ship_url: imo} for each record, fetched through sweep.py and cached.

    chinashipbuild is one host, so this goes through Sweeper (per-host pacing +
    circuit breaker) rather than a bare loop -- the 2026-09-17 rule. The cache
    makes a re-run free; a page that yields no IMO is cached as "" so it is not
    re-fetched every pass.
    """
    from sweep import Sweeper

    cache_path = Path(cache_path or (work_dir() / "csb_ship_imo.json"))
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    todo = [r["ship_url"] for r in records
            if r.get("ship_url") and r["ship_url"] not in cache]
    if todo:
        def _fetch(url, **kw):
            from fetch import fetch_page
            page = fetch_page(url, **kw)
            cache[url] = _parse_ship_imo(page.text or "")
            return page

        Sweeper(work_dir() / "csb_ship_imo_sweep.jsonl", fetch=_fetch,
                delay=delay, jitter=2.0).run(todo)
        cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True))
    return {u: i for u, i in cache.items() if i}


def reconcile(csb_rows, all_rows, igu, edition, ship_imo=None) -> dict:
    """Balance the three orderbooks against the backend. Never edits anything.

    `ship_imo` maps a CSB ship_url to the IMO its detail page prints (see
    resolve_ship_imos). Pure: pass {} and the fourth pass is a no-op.
    """
    ship_imo = ship_imo or {}
    igu_ob = list(igu.get("orderbook", []))
    be_rows = [r for r in all_rows if r["status"] == "on order"]
    by_imo = {r["imo"]: r for r in all_rows if r["imo"]}
    by_hull = defaultdict(list)
    for r in all_rows:
        if r["builder_tag"] and r["hull_core"]:
            by_hull[f"{r['builder_tag']}|{r['hull_core']}"].append(r)

    # Identity is the SHEET ROW, not the column-A row_id: a stub row (columns
    # A-E pasted by hand) has no row_id at all, so keying on it collapses every
    # stub onto one identity and the first match claims all of them.
    matched_rows = set()      # sheet row of every backend row some source reached

    # A hull number can also be sitting in the NAME of a row that has no hull
    # cell -- a discovery batch's "Hull H2706" pasted as a stub (columns A-E
    # only, so no Shipbuilder to key on either). Digits required, so an ordinary
    # vessel name never becomes a hull key.
    by_name_hull = defaultdict(list)
    for r in all_rows:
        if r["hull_core"]:
            continue
        core = hull_core(r["name"])
        if core and any(ch.isdigit() for ch in core):
            by_name_hull[core].append(r)

    # --- CSB -> backend, by builder + hull core ------------------------------
    csb_unmatched, csb_no_hull, csb_status = [], [], []
    csb_hull_to_add, csb_stub = [], []
    claimed = set()           # backend row_ids already spoken for by a CSB hull
    for c in csb_rows:
        tag = yard_tag(c["yard"])
        core = hull_core(c["hull"]) if c.get("hull_assigned") else ""
        if not core:
            # CSB shows the yard's own name until it indexes a hull number.
            csb_no_hull.append({**c, "builder_tag": tag})
            continue
        hits = by_hull.get(f"{tag}|{core}", []) or by_name_hull.get(core, [])
        if hits:
            matched_rows.update(h["sheet_row"] for h in hits)
            claimed.update(h["sheet_row"] for h in hits)
            rec = {**c, "builder_tag": tag, "hull_core": core,
                   "backend": [{"sheet_row": h["sheet_row"], "name": h["name"],
                                "status": h["status"] or "(stub)"} for h in hits]}
            if all(not h["status"] for h in hits):
                csb_stub.append(rec)              # already in the sheet, awaiting its columns
            elif not any(h["status"] == "on order" for h in hits):
                csb_status.append(rec)
            continue
        csb_unmatched.append({**c, "builder_tag": tag, "hull_core": core,
                              "why": "hull not in backend"})

    # --- second pass: does a HULL-LESS backend row describe the same vessel? --
    # A placeholder row ("Hudong-Zhonghua (MISC 1)") is the same order CSB lists
    # under a hull number. That is not a missing vessel -- it is a Hull number
    # this pass can propose for an existing row. Owner + capacity + delivery
    # year must all agree, and each backend row is claimed at most once.
    still_absent = []
    for c in csb_unmatched:
        cap = _typecap_capacity(c.get("typecap", ""))
        year = _year(c.get("delivery", ""))
        owner = normalize_owner(c.get("owner", ""))
        sibs = [b for b in all_rows
                if b["sheet_row"] not in claimed and not b["hull_core"]
                and b["builder_tag"] == c["builder_tag"]
                and (b["owner_tag"] == owner
                     or not b["owner_tag"] or "unknown" in b["owner_tag"])
                and (cap is None or b["capacity"] is None
                     or abs(b["capacity"] - cap) <= CAPACITY_TOL)
                and (year is None or b["delivery_year"] == year)]
        if not sibs:
            still_absent.append(c)
            continue
        b = sibs[0]
        claimed.add(b["sheet_row"])
        matched_rows.add(b["sheet_row"])
        csb_hull_to_add.append({**c, "backend": {"sheet_row": b["sheet_row"], "name": b["name"],
                                                 "status": b["status"], "owner": b["owner"],
                                                 "capacity": b["capacity"],
                                                 "delivery_year": b["delivery_year"]}})
    # --- fourth pass: the ship-detail page's IMO -----------------------------
    # The yard orderbook list has no IMO column; the ship page does. A hull we
    # cannot match is very often a vessel the backend holds under its NAME,
    # with the hull cell still blank -- matching it here turns a false
    # "missing vessel" into a true "Hull number to propose".
    if ship_imo:
        rest = []
        for c in still_absent:
            imo = ship_imo.get(c.get("ship_url") or "")
            b = by_imo.get(imo) if imo else None
            if not b:
                if imo:
                    c["ship_page_imo"] = imo      # absent, and now we know its IMO
                rest.append(c)
                continue
            claimed.add(b["sheet_row"])
            matched_rows.add(b["sheet_row"])
            base = {**c, "ship_page_imo": imo, "matched_by": "ship-page imo"}
            if b["status"] == "on order":
                csb_hull_to_add.append({**base, "backend": {
                    "sheet_row": b["sheet_row"], "name": b["name"],
                    "status": b["status"], "owner": b["owner"],
                    "capacity": b["capacity"], "delivery_year": b["delivery_year"]}})
            else:
                # csb_status carries a LIST of backend rows, like the first pass.
                csb_status.append({**base, "backend": [{
                    "sheet_row": b["sheet_row"], "name": b["name"],
                    "status": b["status"] or "(stub)"}]})
        still_absent = rest

    # --- third pass: annotate, never match -----------------------------------
    # A residue is far more useful saying WHY it stayed one. Same yard, same
    # owner, one field apart is the shape of a vessel we hold under a different
    # capacity or delivery year -- research it before proposing it as new.
    for c in still_absent:
        c["near"] = _near_misses(c, all_rows)
    csb_unmatched = still_absent

    # --- IGU -> backend, by IMO ---------------------------------------------
    igu_unmatched, igu_no_imo, igu_status = [], [], []
    for r in igu_ob:
        if not r.get("imo"):
            igu_no_imo.append(r)
            continue
        hit = by_imo.get(r["imo"])
        if not hit:
            igu_unmatched.append(r)
            continue
        matched_rows.add(hit["sheet_row"])
        if hit["status"] != "on order":
            igu_status.append({**r, "backend": {"sheet_row": hit["sheet_row"],
                                                "name": hit["name"],
                                                "status": hit["status"]}})

    # --- IGU's no-IMO rows: a COUNT comparison, cluster by cluster -----------
    clusters = defaultdict(list)
    for r in igu_no_imo:
        clusters[(normalize_owner(r.get("shipowner", "")),
                  normalize_builder(r.get("shipbuilder", "")),
                  r.get("delivery_year"), r.get("capacity"))].append(r)
    cluster_report = []
    for (owner, builder, year, cap), rows in sorted(clusters.items(), key=lambda kv: str(kv[0])):
        siblings = [b for b in be_rows
                    if b["owner_tag"] == owner and b["builder_tag"] == builder
                    and (year is None or b["delivery_year"] == year)
                    and (cap is None or b["capacity"] is None
                         or abs(b["capacity"] - cap) <= CAPACITY_TOL)]
        cluster_report.append({
            "owner": owner, "builder": builder, "delivery_year": year, "capacity": cap,
            "igu_count": len(rows), "backend_count": len(siblings),
            "delta": len(rows) - len(siblings),
            "igu_names": [r.get("name", "") for r in rows],
            "backend_sheet_rows": [b["sheet_row"] for b in siblings],
        })
        matched_rows.update(b["sheet_row"] for b in siblings)

    # --- the reverse direction: `on order` rows no orderbook carries ---------
    backend_only = [b for b in be_rows if b["sheet_row"] not in matched_rows]

    # --- per-yard balance ----------------------------------------------------
    yards = sorted({yard_tag(s) for s in ALL_YARDS} |
                   {b["builder_tag"] for b in be_rows if b["builder_tag"]})
    per_yard = []
    for tag in yards:
        igu_here = [r for r in igu_ob
                    if normalize_builder(r.get("shipbuilder", "")) == tag]
        per_yard.append({
            "yard": tag,
            "csb": sum(1 for c in csb_rows if yard_tag(c["yard"]) == tag),
            "backend_on_order": sum(1 for b in be_rows if b["builder_tag"] == tag),
            "igu_orderbook": len(igu_here),
            "csb_unmatched": sum(1 for c in csb_unmatched if c["builder_tag"] == tag),
            "csb_hull_to_add": sum(1 for c in csb_hull_to_add if c["builder_tag"] == tag),
            "csb_stub": sum(1 for c in csb_stub if c["builder_tag"] == tag),
            "csb_no_hull": sum(1 for c in csb_no_hull if c["builder_tag"] == tag),
            "csb_status": sum(1 for c in csb_status if c["builder_tag"] == tag),
            "igu_unmatched": sum(1 for r in igu_unmatched
                                 if normalize_builder(r.get("shipbuilder", "")) == tag),
            "backend_only": sum(1 for b in backend_only if b["builder_tag"] == tag),
        })

    return {
        "generated": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {"csb_rows": len(csb_rows), "backend_rows": len(all_rows),
                    "stub_rows": sum(1 for r in all_rows if r.get("stub_from")),
                    "backend_on_order": len(be_rows),
                    "igu_edition": edition, "igu_orderbook": len(igu_ob),
                    "igu_orderbook_no_imo": len(igu_no_imo)},
        "per_yard": per_yard,
        "csb_unmatched": csb_unmatched,
        "csb_hull_to_add": csb_hull_to_add,
        "csb_stub": csb_stub,
        "csb_no_hull": csb_no_hull,
        "csb_status": csb_status,
        "igu_unmatched": igu_unmatched,
        "igu_status": igu_status,
        "igu_no_imo_clusters": cluster_report,
        "backend_only": backend_only,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edition", type=int, default=2026)
    ap.add_argument("--csb", help="override the CSB combined.json path")
    ap.add_argument("--out", help="override the output path")
    ap.add_argument("--stubs-from", nargs="*", default=[], metavar="BATCH_DIR",
                    help="discovery batch dirs whose candidates were pasted into the "
                         "sheet as stub rows (columns A-E only)")
    ap.add_argument("--resolve-imo", action="store_true",
                    help="fetch each unmatched CSB hull's ship-detail page and re-key "
                         "on the IMO it prints (the orderbook list has no IMO column). "
                         "Without this, every vessel the backend holds under a name "
                         "rather than a hull reads as a missing vessel.")
    ap.add_argument("--imo-delay", type=float, default=6.0,
                    help="per-request delay for --resolve-imo (default 6s)")
    args = ap.parse_args()

    csb_rows = load_csb(args.csb)
    be = load_backend()
    all_rows = backend_rows(be)
    if args.stubs_from:
        n = enrich_stubs(all_rows, args.stubs_from)
        print(f"  Stub rows matched back to their batch: {n}", file=sys.stderr)
    igu = load_igu(args.edition)
    result = reconcile(csb_rows, all_rows, igu, args.edition)
    if args.resolve_imo and result["csb_unmatched"]:
        print(f"  Resolving IMOs for {len(result['csb_unmatched'])} unmatched CSB hulls",
              file=sys.stderr)
        ship_imo = resolve_ship_imos(result["csb_unmatched"], delay=args.imo_delay)
        result = reconcile(csb_rows, all_rows, igu, args.edition, ship_imo=ship_imo)

    out = Path(args.out) if args.out else work_dir() / "orderbook_reconcile.json"
    out.write_text(json.dumps(result, indent=2))

    s = result["sources"]
    print(f"  CSB hulls (LNG/FSRU, all pages): {s['csb_rows']}", file=sys.stderr)
    print(f"  Backend `on order` rows:         {s['backend_on_order']}", file=sys.stderr)
    print(f"  IGU {s['igu_edition']} orderbook:            {s['igu_orderbook']} "
          f"({s['igu_orderbook_no_imo']} with no IMO)", file=sys.stderr)
    print(f"\n  {'yard':<22}{'CSB':>5}{'bkend':>7}{'IGU':>5}"
          f"{'csb?':>6}{'hull+':>6}{'stub':>5}{'nohull':>7}{'deliv':>6}{'igu?':>6}{'only':>6}", file=sys.stderr)
    for y in result["per_yard"]:
        if not (y["csb"] or y["backend_on_order"] or y["igu_orderbook"]):
            continue
        print(f"  {y['yard']:<22}{y['csb']:>5}{y['backend_on_order']:>7}"
              f"{y['igu_orderbook']:>5}{y['csb_unmatched']:>6}{y['csb_hull_to_add']:>6}"
              f"{y['csb_stub']:>5}{y['csb_no_hull']:>7}"
              f"{y['csb_status']:>6}{y['igu_unmatched']:>6}{y['backend_only']:>6}",
              file=sys.stderr)
    print(f"\n  Residues: {len(result['csb_unmatched'])} CSB hulls in no backend row, "
          f"{len(result['csb_no_hull'])} CSB slots with no hull yet, "
          f"{len(result['igu_unmatched'])} IGU-by-IMO, "
          f"{len(result['backend_only'])} backend-only", file=sys.stderr)
    print(f"  CSB hulls already in the sheet as a stub row: {len(result['csb_stub'])}",
          file=sys.stderr)
    print(f"  Hull numbers proposable for an existing hull-less row: "
          f"{len(result['csb_hull_to_add'])}", file=sys.stderr)
    print(f"  Status findings: {len(result['csb_status'])} CSB / "
          f"{len(result['igu_status'])} IGU hulls whose backend row is not `on order`",
          file=sys.stderr)
    off = [c for c in result["igu_no_imo_clusters"] if c["delta"]]
    print(f"  IGU no-IMO clusters: {len(result['igu_no_imo_clusters'])} "
          f"({len(off)} where the counts disagree)", file=sys.stderr)
    for c in off:
        print(f"    {c['owner']:<18} x {c['builder']:<16} {c['delivery_year']} "
              f"{c['capacity']}: IGU {c['igu_count']} vs backend {c['backend_count']}",
              file=sys.stderr)
    print(f"\n  Saved to {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
