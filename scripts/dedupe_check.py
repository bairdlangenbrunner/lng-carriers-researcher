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
           capacity-bucket, delivery-year) where nothing hard-distinguishes them
           (at least one lacks a hull AND an IMO, or they share them). A named
           vessel and a placeholder slot that match on every soft key but carry
           no distinguishing hull/IMO are probably the same order slot.
  Tier 3 — DISQUALIFIERS: applied while building Tier 2 — two rows with distinct
           non-blank hulls, distinct non-blank IMOs, or clearly different
           capacities are sister ships, not dupes, and are never paired.
  Tier 4 — ORDINAL RECONCILIATION: a Tier-2 candidate whose rows carry *different*
           ordinal markers in Name / Original source ("8th ship" vs "9th ship",
           "Hull ...-07" vs "...-08") is downgraded to LOW — distinct sisters, the
           Knutsen 8th-vs-9th lesson. Same/no ordinals → stays MED.

CLI:
    python scripts/dedupe_check.py [--backend <csv>] [--rows 1216,1217] [--strict]
    # writes work/dedupe_report.csv; --rows limits output to groups touching
    # those row_ids (the end-of-update "did my new rows duplicate anything?" sweep);
    # --strict exits 1 if any HIGH/MED group is found.

Library:
    from dedupe_check import scan_duplicates
    groups = scan_duplicates(header, data, colmap, focus_rows={"1216", "1217"})
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
from apply_batch import _load_backend


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


def scan_duplicates(header, data, colmap, focus_rows=None):
    """Return a list of candidate-duplicate groups.

    Each group: dict(tier, severity, row_ids, builder, owner, key, reason,
    recommendation). `focus_rows` (a set of row_id strings) limits the result to
    groups that include at least one of those rows; None = report everything.
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
        f["placeholder"] = _is_placeholder(f["name"], f["hull_raw"])
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
    by_soft = defaultdict(list)
    for f in rows:
        if f["b"] and f["o"] and f["cap_bucket"] and f["delivery_year"]:
            by_soft[f"{f['b']}|{f['o']}|{f['cap_bucket']}|{f['delivery_year']}"].append(f)

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
                # only a candidate if at least one side is an unidentified slot
                if not (a["placeholder"] or b["placeholder"]):
                    continue

                # Tier 4 — ordinal reconciliation
                oa = _ordinals(a["name"], a["hull_raw"], a["source"])
                ob = _ordinals(b["name"], b["hull_raw"], b["source"])
                distinct_ordinals = bool(oa and ob and oa.isdisjoint(ob))

                seen_pairs.add(_pair_key(ids))
                if distinct_ordinals:
                    groups.append({
                        "tier": 4, "severity": "LOW", "row_ids": ids,
                        "builder": a["builder_raw"], "owner": a["owner_raw"],
                        "key": key,
                        "reason": (f"match on builder/owner/capacity/delivery but rows carry "
                                   f"distinct ordinals {sorted(oa)} vs {sorted(ob)} — "
                                   f"likely distinct sister ships."),
                        "recommendation": "probably NOT a dup; reconcile by ordinal, then dismiss.",
                    })
                else:
                    groups.append({
                        "tier": 2, "severity": "MED", "row_ids": ids,
                        "builder": a["builder_raw"], "owner": a["owner_raw"],
                        "key": key,
                        "reason": (f"placeholder/identified pair matches builder/owner/"
                                   f"capacity~/delivery with no distinguishing hull or IMO "
                                   f"(names: {a['name']!r} / {b['name']!r})."),
                        "recommendation": "verify by source: is the placeholder the same slot as the named row?",
                    })

    if focus_rows:
        focus = {str(x) for x in focus_rows}
        groups = [g for g in groups if focus & {str(r) for r in g["row_ids"]}]

    sev_rank = {"HIGH": 0, "MED": 1, "LOW": 2}
    groups.sort(key=lambda g: (sev_rank[g["severity"]], g["tier"]))
    return groups


def write_report(groups, out_path):
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tier", "severity", "row_ids", "builder", "owner",
                    "match_key", "reason", "recommendation"])
        for g in groups:
            w.writerow([g["tier"], g["severity"], " + ".join(str(x) for x in g["row_ids"]),
                        g["builder"], g["owner"], g["key"], g["reason"],
                        g["recommendation"]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=str(backend_csv_path()))
    ap.add_argument("--rows", default="", help="comma-separated row_ids to focus on")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 if any HIGH/MED candidate is found")
    args = ap.parse_args()

    header, row_by_id, colmap = _load_backend(args.backend)
    data = list(row_by_id.values())
    focus = {x.strip() for x in args.rows.split(",") if x.strip()} or None

    groups = scan_duplicates(header, data, colmap, focus_rows=focus)

    out = work_dir() / "dedupe_report.csv"
    write_report(groups, out)

    hi = [g for g in groups if g["severity"] == "HIGH"]
    med = [g for g in groups if g["severity"] == "MED"]
    low = [g for g in groups if g["severity"] == "LOW"]
    print(f"dedupe_check: {len(hi)} HIGH, {len(med)} MED, {len(low)} LOW candidate group(s)"
          + (f" (focus rows {sorted(focus)})" if focus else ""), file=sys.stderr)
    for g in (hi + med)[:20]:
        print(f"  [{g['severity']} T{g['tier']}] rows {' + '.join(map(str, g['row_ids']))}"
              f" · {g['key']}\n      {g['reason']}", file=sys.stderr)
    print(f"  report: {out}", file=sys.stderr)

    if args.strict and (hi or med):
        sys.exit(1)


if __name__ == "__main__":
    main()
