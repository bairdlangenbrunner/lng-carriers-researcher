"""
Internal duplicate scan for the backend (Apply SOP §dedupe-sweep).

Finds pairs/clusters of backend rows that likely describe the *same physical
vessel* — the failure mode where a new order is entered twice: once as a
placeholder (blank/`Hull CMHI-282-07`/`TBN`) and again once it's identified, or
the same hull added in two passes. This is the end-of-update safety net that runs
after an apply, so a freshly-added row that shadows an existing one gets caught
before it ossifies.

It is NOT a vessel-merger — it only *flags* candidates for human review, writing
`work/dedupe_report.csv`. Sister ships in the same order (a 4-hull quartet with
distinct hull numbers -01..-04) are explicitly NOT duplicates and are filtered
out by the disqualifier tier.

Four tiers, highest-confidence first:

  Tier 1 — HARD KEYS (HIGH): same IMO, or same (builder, hull). Two rows that
           share a real IMO or a real yard hull number are the same vessel.
  Tier 2 — PLACEHOLDER↔IDENTIFIED (MED): rows sharing (builder, owner,
           capacity-bucket) where one side is an unidentified slot (no hull AND no
           IMO) and nothing hard-distinguishes the pair. A named/identified vessel
           and a placeholder slot on the same soft key, no distinguishing
           hull/IMO/ordinal and within a year of each other, are probably the same
           order slot. delivery-year is deliberately NOT in the blocking key — one
           order's sisters slip a year — but a >1-year gap disqualifies (Tier 3).
  Tier 3 — DISQUALIFIERS: applied while building Tier 2 — two rows with distinct
           non-blank hulls, distinct non-blank IMOs, clearly different capacities,
           or delivery years >1 apart are sister ships / separate orders, not
           dupes, and are never paired.
  Tier 4 — ORDINAL RECONCILIATION: a Tier-2 candidate whose rows carry *different*
           ordinal markers in Name / Original source ("8th ship" vs "9th ship",
           "Hull ...-07" vs "...-08") is downgraded to LOW — distinct sisters, the
           Knutsen 8th-vs-9th lesson. Same/no ordinals → stays MED.

Row identity: every group is reported by its **live Google Sheet tab row** as well
as its `row_id`. `row_id` is column A ("original order in sheet") — a static stamp
that drifts from the live row as rows are deleted — so it is NOT the tab row. The
report's `sheet_rows` column and the stderr lines lead with the live row; matching
is still keyed on `row_id` (the stable, offset-proof identifier across pulls).

CLI:
    python scripts/dedupe_check.py [--backend <csv>] [--rows ...] [--sheet-rows ...] [--strict]
    # writes work/dedupe_report.csv (with a sheet_rows column).
    # --rows N,...        focus by row_id (column-A "original order")
    # --sheet-rows N,...  focus by LIVE sheet tab row (what you see in the sheet)
    # --strict            exit 1 if any HIGH/MED group is found
    # (the end-of-update "did my new rows duplicate anything?" sweep)

Library:
    from dedupe_check import scan_duplicates
    from apply_batch import sheet_row_map
    srmap = sheet_row_map(backend_csv_path)
    groups = scan_duplicates(header, data, colmap, focus_rows={"1216"}, sheet_rows=srmap)
"""
import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from normalize import normalize_builder, normalize_owner, normalize_hull
from paths import backend_csv_path, work_dir
from apply_batch import _load_backend, sheet_row_map


# A name that doesn't identify a specific delivered/named vessel — a slot, not a ship.
_PLACEHOLDER_RE = re.compile(
    r"^\s*$|\b(tbn|tba|tbd|unknown|newbuild|new build|hull\b|hull no|"
    r"hull number|to be named|n/?a)\b", re.IGNORECASE)

# Ordinal / sequence markers that distinguish sister ships in the same order.
_ORDINAL_WORDS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}


def _digits(s):
    return re.sub(r"\D", "", s or "")


def _capacity_bucket(s):
    """Round a capacity to the nearest 10,000 cbm for soft grouping (None if blank)."""
    d = _digits(s)
    if not d:
        return None
    n = int(d)
    return round(n / 10000) * 10000


def _cap_int(s):
    d = _digits(s)
    return int(d) if d else None


def _year(s):
    m = re.search(r"(19|20)\d{2}", s or "")
    return m.group(0) if m else None


def _is_placeholder(name, hull):
    """A row is a placeholder if its Name doesn't identify a specific vessel."""
    n = (name or "").strip()
    if not n:
        return True
    if _PLACEHOLDER_RE.search(n):
        return True
    # Name is literally the hull designation -> placeholder
    if hull and n.strip().lower() == hull.strip().lower():
        return True
    return False


def _ordinals(*texts):
    """Extract ordinal/sequence markers from name/source text for Tier-4 reconcile."""
    found = set()
    for t in texts:
        if not t:
            continue
        tl = t.lower()
        for w, n in _ORDINAL_WORDS.items():
            if re.search(rf"\b{w}\b", tl):
                found.add(n)
        # "8th", "9th ship", "unit 3", "vessel no. 2", trailing hull suffix "-07"
        for m in re.finditer(r"\b(\d{1,2})(?:st|nd|rd|th)\b", tl):
            found.add(int(m.group(1)))
        for m in re.finditer(r"\b(?:ship|vessel|unit|hull|no\.?)\s*[-#]?\s*(\d{1,2})\b", tl):
            found.add(int(m.group(1)))
        for m in re.finditer(r"-(\d{2})\b", t):  # CMHI-282-07 style suffix
            found.add(int(m.group(1)))
        # trailing 1-2 digit marker: "... Capital Clean ECC 1)", "(Seapeak 2)",
        # "TMS Cardiff Gas 3)" — the sister-ship ordinal at the end of a Name. The
        # (?<!\d) guard keeps it from grabbing the tail of a longer number — a hull
        # ("...Geoje 2775" -> not 75) or a trailing year ("...May 2026" -> not 26).
        for m in re.finditer(r"(?<!\d)(\d{1,2})\s*\)?\s*$", t):
            found.add(int(m.group(1)))
    return found


def _row_fields(row, colmap):
    def g(key):
        i = colmap.get(key)
        return row[i] if i is not None and len(row) > i else ""
    return {
        "row_id": g("row_id"),
        "builder_raw": g("shipbuilder"), "owner_raw": g("shipowner"),
        "hull_raw": g("hull"), "imo": _digits(g("imo")),
        "name": g("name"), "capacity": g("capacity"),
        "delivery_year": _year(g("delivery_year")),
        "contract": g("contract_date"), "source": g("original_source"),
    }


def scan_duplicates(header, data, colmap, focus_rows=None, sheet_rows=None):
    """Return a list of candidate-duplicate groups.

    Each group: dict(tier, severity, row_ids, sheet_rows, builder, owner, key,
    reason, recommendation). `row_ids` are column-A "original order in sheet"
    stamps; `sheet_rows` are the live tab rows resolved via `sheet_rows` (a
    {row_id: sheet_row} map) — always report the live rows to humans. `focus_rows`
    (a set of row_id strings) limits the result to groups that include at least
    one of those rows; None = report everything.
    """
    rows = []
    for r in data:
        f = _row_fields(r, colmap)
        if not f["row_id"]:
            continue
        f["b"] = normalize_builder(f["builder_raw"])
        f["o"] = normalize_owner(f["owner_raw"])
        f["h"] = normalize_hull(f["b"], f["hull_raw"])
        f["cap_i"] = _cap_int(f["capacity"])
        f["cap_bucket"] = _capacity_bucket(f["capacity"])
        # An unidentified slot has NO hard identifier — no normalized hull AND no
        # IMO. A real hull or IMO means the vessel is identified, regardless of how
        # its Name reads: "Hull 2656 (SHI)" (hull col + IMO 9992103) is a fully
        # identified ship, not a placeholder, so it must NOT shadow-match the
        # genuinely blank "Samsung HI Geoje (Seapeak 1)" slots (no hull, no IMO).
        # The name-based _is_placeholder test is subsumed by this: a "TBN"/blank
        # name with no hull/IMO is still caught here.
        f["placeholder"] = not f["h"] and not f["imo"]
        rows.append(f)

    groups = []
    seen_pairs = set()  # de-dup the same row pair across tiers (Tier 1 wins)

    def _pair_key(ids):
        return tuple(sorted(ids))

    # --- Tier 1: hard keys -------------------------------------------------
    # Same IMO
    by_imo = defaultdict(list)
    for f in rows:
        if f["imo"] and len(f["imo"]) >= 6:
            by_imo[f["imo"]].append(f)
    for imo, fs in by_imo.items():
        if len(fs) > 1:
            ids = [f["row_id"] for f in fs]
            seen_pairs.add(_pair_key(ids))
            groups.append({
                "tier": 1, "severity": "HIGH", "row_ids": ids,
                "builder": fs[0]["builder_raw"], "owner": fs[0]["owner_raw"],
                "key": f"IMO {imo}",
                "reason": f"{len(fs)} rows share IMO {imo} — same physical vessel.",
                "recommendation": "merge: keep the most complete row, retire the other(s).",
            })

    # Same (builder, hull)
    by_hull = defaultdict(list)
    for f in rows:
        if f["b"] and f["h"]:
            by_hull[f"{f['b']}|{f['h']}"].append(f)
    for key, fs in by_hull.items():
        if len(fs) > 1:
            ids = [f["row_id"] for f in fs]
            if _pair_key(ids) in seen_pairs:
                continue
            seen_pairs.add(_pair_key(ids))
            groups.append({
                "tier": 1, "severity": "HIGH", "row_ids": ids,
                "builder": fs[0]["builder_raw"], "owner": fs[0]["owner_raw"],
                "key": f"builder|hull = {key}",
                "reason": f"{len(fs)} rows share builder+hull {key} — same yard slot.",
                "recommendation": "merge: keep the most complete row, retire the other(s).",
            })

    # --- Tier 2 (+3 disqualifiers, +4 ordinals): soft-key placeholder match -
    # Block on (builder, owner, capacity-bucket) only. delivery_year is NOT in the
    # key: sister ships in one order routinely deliver across consecutive years, so
    # an exact-year key would split a single order and hide dupes (the Capital ECC
    # 1/2/3 case: ECC 1 was 2028, ECC 2/3 were 2029, same order). Year drift is
    # instead a *disqualifier* below, with a >2-year tolerance.
    by_soft = defaultdict(list)
    for f in rows:
        if f["b"] and f["o"] and f["cap_bucket"]:
            by_soft[f"{f['b']}|{f['o']}|{f['cap_bucket']}"].append(f)

    for key, fs in by_soft.items():
        if len(fs) < 2:
            continue
        for i in range(len(fs)):
            for j in range(i + 1, len(fs)):
                a, b = fs[i], fs[j]
                ids = [a["row_id"], b["row_id"]]
                if _pair_key(ids) in seen_pairs:
                    continue
                # Tier 3 disqualifiers — distinct hard keys => sister ships
                if a["h"] and b["h"] and a["h"] != b["h"]:
                    continue
                if a["imo"] and b["imo"] and a["imo"] != b["imo"]:
                    continue
                if a["cap_i"] and b["cap_i"] and abs(a["cap_i"] - b["cap_i"]) > 8000:
                    continue
                # delivery years >1 apart => different build program, not a dup.
                # A single order's sisters slip a year at most in this dataset; a
                # placeholder 2 years off a known hull (e.g. Seapeak 2029 slot vs
                # the identified Hull 2656/2027) is a separate order, not the same slot.
                if (a["delivery_year"] and b["delivery_year"]
                        and abs(int(a["delivery_year"]) - int(b["delivery_year"])) > 1):
                    continue
                # only a candidate if at least one side is an unidentified slot
                if not (a["placeholder"] or b["placeholder"]):
                    continue

                # Tier 4 — ordinal reconciliation
                oa = _ordinals(a["name"], a["hull_raw"], a["source"])
                ob = _ordinals(b["name"], b["hull_raw"], b["source"])
                distinct_ordinals = bool(oa and ob and oa.isdisjoint(ob))
                yr = ""
                if a["delivery_year"] and b["delivery_year"] and a["delivery_year"] != b["delivery_year"]:
                    yr = f"; delivery {a['delivery_year']} vs {b['delivery_year']}"

                seen_pairs.add(_pair_key(ids))
                if distinct_ordinals:
                    groups.append({
                        "tier": 4, "severity": "LOW", "row_ids": ids,
                        "builder": a["builder_raw"], "owner": a["owner_raw"],
                        "key": key,
                        "reason": (f"match on builder/owner/capacity but rows carry distinct "
                                   f"ordinals {sorted(oa)} vs {sorted(ob)}{yr} — "
                                   f"likely distinct sister ships."),
                        "recommendation": "probably NOT a dup; reconcile by ordinal, then dismiss.",
                    })
                else:
                    groups.append({
                        "tier": 2, "severity": "MED", "row_ids": ids,
                        "builder": a["builder_raw"], "owner": a["owner_raw"],
                        "key": key,
                        "reason": (f"placeholder/identified pair matches builder/owner/"
                                   f"capacity~ with no distinguishing hull or IMO{yr} "
                                   f"(names: {a['name']!r} / {b['name']!r})."),
                        "recommendation": "verify by source: is the placeholder the same slot as the named row?",
                    })

    if focus_rows:
        focus = {str(x) for x in focus_rows}
        groups = [g for g in groups if focus & {str(r) for r in g["row_ids"]}]

    # Resolve live sheet rows for every group (row_id is the column-A stamp, not
    # the tab row) — always present the live rows to humans.
    for g in groups:
        g["sheet_rows"] = ([sheet_rows.get(str(r)) for r in g["row_ids"]]
                           if sheet_rows else [None] * len(g["row_ids"]))

    sev_rank = {"HIGH": 0, "MED": 1, "LOW": 2}
    groups.sort(key=lambda g: (sev_rank[g["severity"]], g["tier"]))
    return groups


def _fmt_rows(g):
    """'sheet 1087 (id 1092) + sheet 1083 (id 263)' — lead with the live tab row."""
    parts = []
    for rid, sr in zip(g["row_ids"], g.get("sheet_rows") or [None] * len(g["row_ids"])):
        parts.append(f"sheet {sr} (id {rid})" if sr else f"id {rid}")
    return " + ".join(parts)


def write_report(groups, out_path):
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tier", "severity", "sheet_rows", "row_ids", "builder", "owner",
                    "match_key", "reason", "recommendation"])
        for g in groups:
            sr = " + ".join(str(x) if x is not None else "?"
                            for x in (g.get("sheet_rows") or []))
            w.writerow([g["tier"], g["severity"], sr,
                        " + ".join(str(x) for x in g["row_ids"]),
                        g["builder"], g["owner"], g["key"], g["reason"],
                        g["recommendation"]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=str(backend_csv_path()))
    ap.add_argument("--rows", default="",
                    help="comma-separated row_ids (column-A 'original order') to focus on")
    ap.add_argument("--sheet-rows", default="",
                    help="comma-separated LIVE sheet tab rows to focus on")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 if any HIGH/MED candidate is found")
    args = ap.parse_args()

    header, row_by_id, colmap = _load_backend(args.backend)
    data = list(row_by_id.values())
    srmap = sheet_row_map(args.backend, colmap)

    focus = {x.strip() for x in args.rows.split(",") if x.strip()}
    if args.sheet_rows:  # translate live sheet rows -> row_id for matching
        want = {x.strip() for x in args.sheet_rows.split(",") if x.strip()}
        inv = {str(sr): rid for rid, sr in srmap.items()}
        focus |= {inv[s] for s in want if s in inv}
    focus = focus or None

    groups = scan_duplicates(header, data, colmap, focus_rows=focus, sheet_rows=srmap)

    out = work_dir() / "dedupe_report.csv"
    write_report(groups, out)

    hi = [g for g in groups if g["severity"] == "HIGH"]
    med = [g for g in groups if g["severity"] == "MED"]
    low = [g for g in groups if g["severity"] == "LOW"]
    print(f"dedupe_check: {len(hi)} HIGH, {len(med)} MED, {len(low)} LOW candidate group(s)"
          + (f" (focus row_ids {sorted(focus)})" if focus else ""), file=sys.stderr)
    for g in (hi + med)[:20]:
        print(f"  [{g['severity']} T{g['tier']}] {_fmt_rows(g)}"
              f" · {g['key']}\n      {g['reason']}", file=sys.stderr)
    print(f"  report: {out}", file=sys.stderr)

    if args.strict and (hi or med):
        sys.exit(1)


if __name__ == "__main__":
    main()
