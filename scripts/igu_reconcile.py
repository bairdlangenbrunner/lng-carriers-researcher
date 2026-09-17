#!/usr/bin/env python3
"""IGU reconciliation — IMO-keyed intercomparison of the IGU World LNG Report
fleet (Appendix 3) and orderbook (Appendix 4) tables against the backend.

Governed by docs/sops/igu_reconciliation.md (IG rev 1). Inputs are the JSON files
`scripts/igu_fleet.py` writes; the backend is `work/backend.csv` (pull it fresh
first). Advisory only — nothing here edits the backend; findings promote through
fix / discovery batches and the Apply SOP.

Unlike GIIGNL and SFOC, IGU prints an IMO for almost every vessel, so the join is
by IMO (always a string). No fuzzy matching: IGU orderbook rows printed with an
"Unknown" IMO only get a cluster-level hint (builder + contract month against the
backend's not-in-IGU on-order rows), never a row pairing.

The backend was seeded from the PREVIOUS IGU edition, so a disagreement means one
of two different things, and every field diff says which (`kind`):

    igu_changed      IGU printed a different value last edition — new information
                     in this edition that the backend does not carry yet. Review.
    new_to_igu       the vessel was not in the previous edition; first comparison.
    backend_differs  IGU prints the same value in both editions and the backend
                     disagrees — a researcher edit since the load, usually better
                     sourced than IGU. Low priority; do not "correct" blindly.

Buckets (work/igu_reconcile.json):
    matched            IMO in both; `diffs` per field, `status_finding` where the
                       backend Status disagrees with the IGU table the vessel is in
    dropped            backend `active` rows that were in the previous IGU fleet and
                       are gone from this one -> scrapped / converted / sold?
    backend_not_in_igu every other backend row IGU does not list, by reason
    igu_only           IGU rows with no backend IMO match (name fallback -> possible
                       IMO defect; out-of-scope types flagged)
    igu_no_imo         IGU orderbook rows printed without an IMO + cluster hints
    igu_duplicates     IMOs IGU prints more than once (kept, never deduped)
    edition_diff       previous -> current: dropped / added / delivered / changed

Usage:
    python scripts/igu_reconcile.py                       # 2026 vs backend, 2025 as prev
    python scripts/igu_reconcile.py --igu work/igu_fleet_2026.json \
        --prev work/igu_fleet_2025.json --pending batches/2026-09-17_*
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend_io import contract_month, load_backend  # noqa: E402
from normalize import normalize_vessel_name  # noqa: E402
from paths import work_dir  # noqa: E402

# colmap key -> IGU record key, for the fields both sides carry
FIELDS = (
    ("name", "name"), ("shipowner", "shipowner"), ("shipbuilder", "shipbuilder"),
    ("capacity", "capacity"), ("cargo_type", "cargo_type"), ("vessel_type", "vessel_type"),
    ("propulsion", "propulsion"), ("delivery_year", "delivery_year"),
)
BACKEND_KEYS = ("row_id", "name", "imo", "hull", "status", "shipowner", "shipbuilder",
                "capacity", "vessel_type", "propulsion", "cargo_type", "delivery_year",
                "contract_date", "original_source")

# IGU rounds / restates capacities; same tolerance as the FSRU reconciliation
CAP_TOL_ABS, CAP_TOL_REL = 6000, 0.03
# docs/inclusion_criteria.md: FSUs, small/mid-scale and bunkering vessels are out of scope
OUT_OF_SCOPE_TYPES = {"fsu", "small-scale", "mid-scale", "bunkering vessel"}
SMALL_SCALE_CBM = 60000
# a builder label pairing seen on at least this many matched vessels is "the same yard"
BUILDER_PAIR_MIN = 3

_IGU_TYPOS = {"lino": "iino"}  # IGU prints IINO Kaiun as "lino"


def _int(s):
    try:
        return int(float(str(s).replace(",", "").strip()))
    except (ValueError, TypeError):
        return None


def _key(s) -> str:
    s = re.sub(r"[\s,;/&.\-]+", " ", str(s if s is not None else "").lower()).strip()
    return " ".join(_IGU_TYPOS.get(t, t) for t in s.split())


_OWNER_STOP = {"the", "and", "line", "lng", "gas", "shipping", "maritime", "corporation",
               "corp", "group", "ltd", "inc", "co", "of", "jv", "unknown", "hull", "no"}


def _owner_tokens(s) -> set:
    return {_IGU_TYPOS.get(t, t) for t in re.split(r"[\s,;/&.\-()]+", str(s or "").lower())
            if len(t) > 1 and not t.isdigit() and t not in _OWNER_STOP}


def _name_key(s) -> str:
    """Vessel name for comparison: '(ex-…)' tail dropped first (IGU nests parentheses —
    'Energy Fortitude (ex-Victor Hugo (8107))'), then punctuation-insensitive."""
    s = re.sub(r"\s*\(ex\b.*$", "", str(s or ""), flags=re.I)
    return re.sub(r"[^a-z0-9]+", "", normalize_vessel_name(s))


def _month_near(a: str, b: str) -> bool:
    """'YYYY-MM' within one month — IGU dates an order by announcement, the backend
    by the filing (Capital Gas 'Jun 2025' vs 1-Jul-2025)."""
    try:
        ya, ma, yb, mb = int(a[:4]), int(a[5:7]), int(b[:4]), int(b[5:7])
    except (ValueError, TypeError):
        return False
    return bool(ma and mb) and abs((ya * 12 + ma) - (yb * 12 + mb)) <= 1


def is_placeholder(name: str) -> bool:
    """A Name that does not identify a delivered, named vessel: 'Hull 2396',
    'Hull H1884A', 'Knutsen OAS - Hanwha - Dec 2025 - 1', 'Unknown Hull No.',
    'Samsung (Seapeak 3)', 'TBN', blank."""
    n = (name or "").strip().lower()
    if not n or n in {"tbn", "tba", "unknown", "unnamed"}:
        return True
    if n.startswith(("hull", "unknown hull")) or re.search(r"\bhull\s*(no\.?)?\s*[a-z]*\d", n):
        return True
    if re.search(r"\b(19|20)\d\d\b\s*-?\s*\d*$", n) and " - " in n.replace("- ", " - "):
        return True
    return bool(re.search(r"\([^)]*\d\)\s*$", n)) or bool(re.search(r"\d{4}-\d+$", n))


def contract_month_from_name(name: str) -> str:
    """'Knutsen OAS - Hanwha - Dec 2025 - 1' -> '2025-12' (IGU's IMO-less rows)."""
    m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(20\d\d)\b",
                  (name or "").lower())
    if not m:
        return ""
    mon = "jan feb mar apr may jun jul aug sep oct nov dec".split().index(m.group(1)) + 1
    return f"{m.group(2)}-{mon:02d}"


def cap_agree(a, b):
    a, b = _int(a), _int(b)
    if a is None or b is None:
        return None
    return abs(a - b) <= max(CAP_TOL_ABS, CAP_TOL_REL * max(a, b))


def backend_entries(be) -> list:
    cm, out = be.colmap, []
    for off, r in enumerate(be.data):
        e = {k: (r[cm[k]].strip() if k in cm and cm[k] < len(r) else "") for k in BACKEND_KEYS}
        e["imo"] = re.sub(r"\D", "", e["imo"])
        e["sheet_row"] = be.data_start + off + 1
        if any(e[k] for k in ("name", "imo", "shipowner", "shipbuilder")):
            out.append(e)
    return out


def load_pending(batch_dirs) -> dict:
    """row_id -> column -> [{batch, value, decision, confidence}] from decisions.csv."""
    out = defaultdict(lambda: defaultdict(list))
    for d in batch_dirs:
        p = Path(d) / "decisions.csv"
        if not p.exists():
            continue
        for r in csv.DictReader(p.open(encoding="utf-8")):
            if r.get("row_id") and r.get("column") and "[ref]" not in r["column"]:
                out[r["row_id"]][r["column"]].append({
                    "batch": Path(d).name, "value": r.get("proposed_value", ""),
                    "decision": r.get("decision", ""), "confidence": r.get("confidence", "")})
    return out


_PENDING_COL = {"name": "Name", "shipowner": "Shipowner", "shipbuilder": "Shipbuilder",
                "capacity": "Capacity", "cargo_type": "Cargo type", "vessel_type": "Vessel type",
                "propulsion": "Propulsion", "delivery_year": "Delivery year", "status": "Status"}


def builder_pairs(matches) -> Counter:
    """(IGU builder label, backend builder) co-occurrence over the IMO-matched
    vessels. IGU prints short labels ('Mitsui', 'HD Hyundai') where the backend
    carries the full yard name, so a pairing is learned, not string-compared."""
    c = Counter()
    for igu, be in matches:
        if igu.get("shipbuilder") and be["shipbuilder"]:
            c[(_key(igu["shipbuilder"]), _key(be["shipbuilder"]))] += 1
    return c


def field_differs(field, bval, ival, pairs) -> bool:
    """True when the backend and IGU genuinely disagree. Blank on either side is
    not a disagreement (blanks are data-fill's business, not a conflict)."""
    if ival in (None, "") or bval in (None, ""):
        return False
    if field == "name":
        if is_placeholder(str(ival)):
            return False  # backend is ahead of IGU (or equally unnamed)
        return _name_key(bval) != _name_key(ival)
    if field == "capacity":
        return cap_agree(bval, ival) is False
    if field == "delivery_year":
        return _int(bval) != _int(ival)
    if field == "shipowner":
        a, b = _owner_tokens(bval), _owner_tokens(ival)
        return not (a & b) if a and b else _key(bval) != _key(ival)
    if field == "shipbuilder":
        a, b = _key(ival), _key(bval)
        if a == b or a in b or b in a:
            return False
        return pairs[(a, b)] < BUILDER_PAIR_MIN
    return _key(bval) != _key(ival)


def diff_fields(igu, prev, be, pairs, pending, have_prev=True) -> list:
    """`prev` is the vessel's record in the previous edition (None if absent)."""
    diffs = []
    for bk, ik in FIELDS:
        bval, ival = be[bk], igu.get(ik)
        if not field_differs(bk, bval, ival, pairs):
            continue
        pval = prev.get(ik) if prev else None
        if not have_prev:
            kind = "no_prev_edition"
        elif prev is None:
            kind = "new_to_igu"
        elif pval in (None, "") or field_differs(bk, pval, ival, pairs) or (
                bk == "name" and _name_key(pval) != _name_key(ival)):
            kind = "igu_changed"
        else:
            kind = "backend_differs"
        pend = pending.get(be["row_id"], {}).get(_PENDING_COL[bk], [])
        diffs.append({
            "field": bk, "backend": bval, "igu": ival, "igu_prev": pval, "kind": kind,
            "pending": pend,
            "pending_agrees": any(not field_differs(bk, p["value"], ival, pairs)
                                  for p in pend if p["value"]),
        })
    return diffs


def status_finding(igu, be, pending, cutoff=None):
    """Backend Status vs the IGU table the vessel is printed in."""
    st = be["status"].lower()
    pend = pending.get(be["row_id"], {}).get("Status", [])
    if igu["table"] == "fleet" and st in ("on order", "proposed"):
        return {"finding": "delivered_per_igu", "backend": be["status"],
                "igu": f"in the active fleet table (delivered {igu.get('delivery_year')})",
                "pending": pend,
                "pending_agrees": any(p["value"].lower() == "active" for p in pend)}
    if igu["table"] == "orderbook" and st == "active":
        # IGU still had it on order at its cut-off. Fine if it delivered since; a
        # backend Delivery year at or before the cut-off year cannot also be true.
        early = (_int(be["delivery_year"]) or 9999) <= (cutoff or 0)
        return {"finding": "on_order_at_igu_cutoff", "backend": be["status"],
                "igu": f"in the orderbook table (delivery {igu.get('delivery_year')})",
                "delivery_year_conflict": early, "pending": pend,
                "pending_agrees": False}
    if igu["table"] == "orderbook" and st == "proposed":
        return {"finding": "on_order_per_igu", "backend": be["status"],
                "igu": "in the orderbook table", "pending": pend,
                "pending_agrees": any(p["value"].lower() in ("on order", "active") for p in pend)}
    return None


def reconcile(igu, prev, backend, pending, asof_year=None) -> dict:
    cur_recs = igu["fleet"] + igu["orderbook"]
    cutoff = asof_year or _int(re.sub(r"\D", "", str(igu.get("asof", "")))[-4:])
    cur, dups = {}, defaultdict(list)
    for r in cur_recs:
        if r["imo"]:
            dups[r["imo"]].append(r)
            cur.setdefault(r["imo"], r)  # first print wins for the join; all kept in dups
    prev_by = {}
    for r in (prev["fleet"] + prev["orderbook"]) if prev else []:
        if r["imo"]:
            prev_by.setdefault(r["imo"], r)

    by_imo = defaultdict(list)
    for e in backend:
        if e["imo"]:
            by_imo[e["imo"]].append(e)

    pairs = builder_pairs([(cur[i], e) for i, es in by_imo.items() if i in cur for e in es]
                          + [(prev_by[i], e) for i, es in by_imo.items() if i in prev_by for e in es])

    matched, igu_only = [], []
    name_index = defaultdict(list)
    for e in backend:
        name_index[normalize_vessel_name(e["name"])].append(e)

    for imo, r in cur.items():
        if imo in by_imo:
            for e in by_imo[imo]:
                matched.append({
                    "igu": r, "backend": e, "in_prev": imo in prev_by if prev else None,
                    "diffs": diff_fields(r, prev_by.get(imo), e, pairs, pending,
                                         have_prev=bool(prev)),
                    "status_finding": status_finding(r, e, pending, cutoff),
                })
            continue
        # no IMO match — name fallback catches a wrong / missing IMO in the backend
        names = {normalize_vessel_name(r["name"])}
        m = re.search(r"\(ex-?\s*([^)]+)\)", r["name"] or "")
        if m:
            names.add(normalize_vessel_name(m.group(1)))
        hits = [e for n in names if n and not is_placeholder(r["name"]) for e in name_index.get(n, [])]
        vt = (r.get("vessel_type") or "").lower()
        out_scope = vt in OUT_OF_SCOPE_TYPES or (_int(r.get("capacity")) or 10**9) < SMALL_SCALE_CBM
        igu_only.append({
            "igu": r, "in_prev": imo in prev_by if prev else None,
            "name_match": [{"sheet_row": e["sheet_row"], "name": e["name"], "imo": e["imo"],
                            "status": e["status"]} for e in hits],
            "out_of_scope": out_scope,
            "reason": ("possible IMO defect — same name in the backend under another IMO" if hits
                       else f"out of scope ({r.get('vessel_type') or 'small capacity'})" if out_scope
                       else "candidate — in IGU, not in the backend"),
        })

    # backend rows IGU does not list
    dropped, not_in_igu = [], []
    for e in backend:
        if e["imo"] and e["imo"] in cur:
            continue
        st = e["status"].lower()
        p = prev_by.get(e["imo"]) if e["imo"] else None
        if st == "active" and p and p["table"] == "fleet":
            dropped.append({"backend": e, "igu_prev": p,
                            "pending": pending.get(e["row_id"], {})})
            continue
        cy = _int(contract_month(e["contract_date"])[:4])
        if not e["imo"]:
            reason = "no IMO in the backend (cannot join)"
        elif p:
            reason = f"in the previous IGU {p['table']} table, gone from this edition"
        elif st in ("on order", "proposed") and cy and cutoff and cy > cutoff:
            reason = f"contract signed after the IGU cut-off (end-{cutoff})"
        elif st in ("on order", "proposed"):
            reason = "on order / proposed and never listed by IGU"
        else:
            reason = "active and never listed by IGU (SFOC / Clarkson / discovery row?)"
        not_in_igu.append({"backend": e, "reason": reason, "in_prev": bool(p)})

    # IMO-less IGU orderbook rows: cluster hint only
    clusters = defaultdict(list)
    for r in cur_recs:
        if not r["imo"]:
            clusters[(r["shipowner"], r["shipbuilder"], contract_month_from_name(r["name"]),
                      r.get("delivery_year"))].append(r)
    unjoined = [x["backend"] for x in not_in_igu if x["backend"]["status"].lower() != "active"]
    igu_no_imo = []
    for (owner, builder, cmonth, year), rs in sorted(clusters.items(), key=lambda kv: str(kv[0])):
        # owner tokens also from the IGU placeholder name ('Bonny Gas Transport - HZ - …'
        # under owner 'BGT LTD'); hull numbers from 'Hull 8340'
        toks = _owner_tokens(owner) | {t for r in rs for t in _owner_tokens(
            re.sub(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", " ",
                   r["name"].lower()))}
        hulls = {h for r in rs for h in re.findall(r"\d{4,}", r["name"])
                 if not re.fullmatch(r"20\d\d", h)}
        cands = []
        for e in unjoined:
            hull_hit = any(h in e["hull"] or h in e["name"] for h in hulls)
            if not hull_hit:
                if not (toks & (_owner_tokens(e["shipowner"]) | _owner_tokens(e["name"]))):
                    continue
                bk, ik = _key(e["shipbuilder"]), _key(builder)
                if not (ik in bk or bk in ik or pairs[(ik, bk)] >= BUILDER_PAIR_MIN
                        or set(ik.split()) & set(bk.split()) - {"heavy", "industries", "shipbuilding", "hd"}):
                    continue
            e = dict(e, hull_hit=hull_hit,
                     month_hit=bool(cmonth) and _month_near(contract_month(e["contract_date"]), cmonth))
            cands.append(e)
        # a dated / hull-numbered cluster keeps only the rows that agree, when any do
        strong = [e for e in cands if e["hull_hit"] or e["month_hit"]]
        cands = strong or cands
        igu_no_imo.append({
            "shipowner": owner, "shipbuilder": builder, "contract_month": cmonth,
            "delivery_year": year, "igu_rows": rs, "igu_count": len(rs),
            "backend_hint_rows": [{"sheet_row": e["sheet_row"], "name": e["name"],
                                   "imo": e["imo"], "status": e["status"],
                                   "contract_date": e["contract_date"],
                                   "contract_month_agrees": e["month_hit"],
                                   "hull_number_agrees": e["hull_hit"],
                                   "delivery_year": e["delivery_year"]} for e in cands],
            "backend_hint_count": len(cands),
            "hint_strength": "strong" if strong else "weak" if cands else "none",
        })

    # edition diff
    edition = {}
    if prev:
        pf = {r["imo"] for r in prev["fleet"] if r["imo"]}
        po = {r["imo"] for r in prev["orderbook"] if r["imo"]}
        cf = {r["imo"] for r in igu["fleet"] if r["imo"]}
        co = {r["imo"] for r in igu["orderbook"] if r["imo"]}
        in_be = lambda i: [e["sheet_row"] for e in by_imo.get(i, [])]  # noqa: E731
        edition = {
            "fleet_dropped": [dict(prev_by[i], backend_rows=in_be(i)) for i in sorted(pf - cf - co)],
            "orderbook_dropped": [dict(prev_by[i], backend_rows=in_be(i))
                                  for i in sorted(po - cf - co - pf)],
            "delivered": sorted((po - pf) & cf),
            "fleet_added_direct": sorted(cf - pf - po),
            "orderbook_added": sorted(co - po - pf),
        }

    n_status = Counter(m["status_finding"]["finding"] for m in matched if m["status_finding"])
    diff_kinds = Counter((d["field"], d["kind"]) for m in matched for d in m["diffs"])
    return {
        "source_pdf": igu.get("source_pdf"), "edition": igu.get("edition"), "asof": igu.get("asof"),
        "prev_edition": prev.get("edition") if prev else None,
        "igu_counts": igu.get("counts"),
        "backend_counts": dict(Counter(e["status"].lower() for e in backend)),
        "summary": {
            "matched": len(matched),
            "matched_with_diffs": sum(1 for m in matched if m["diffs"]),
            "diffs_igu_changed": sum(1 for m in matched for d in m["diffs"] if d["kind"] == "igu_changed"),
            "diffs_new_to_igu": sum(1 for m in matched for d in m["diffs"] if d["kind"] == "new_to_igu"),
            "diffs_backend_differs": sum(1 for m in matched for d in m["diffs"]
                                         if d["kind"] == "backend_differs"),
            "diffs_by_field_kind": {f"{f}|{k}": n for (f, k), n in sorted(diff_kinds.items())},
            "status_findings": dict(n_status),
            "status_findings_not_pending": sum(1 for m in matched if m["status_finding"]
                                               and not m["status_finding"]["pending_agrees"]),
            "delivery_year_conflicts": sum(1 for m in matched if (m["status_finding"] or {})
                                           .get("delivery_year_conflict")),
            "dropped": len(dropped),
            "backend_not_in_igu": len(not_in_igu),
            "backend_not_in_igu_by_reason": dict(Counter(x["reason"] for x in not_in_igu)),
            "igu_only": len(igu_only),
            "igu_only_candidates": sum(1 for x in igu_only if not x["name_match"] and not x["out_of_scope"]),
            "igu_only_imo_defect": sum(1 for x in igu_only if x["name_match"]),
            "igu_only_out_of_scope": sum(1 for x in igu_only if x["out_of_scope"] and not x["name_match"]),
            "igu_no_imo_rows": sum(c["igu_count"] for c in igu_no_imo),
            "igu_no_imo_clusters": len(igu_no_imo),
            "igu_duplicates": sum(1 for v in dups.values() if len(v) > 1),
        },
        "matched": matched, "dropped": dropped, "backend_not_in_igu": not_in_igu,
        "igu_only": igu_only, "igu_no_imo": igu_no_imo,
        "igu_duplicates": [{"imo": i, "rows": v,
                            "backend_rows": [e["sheet_row"] for e in by_imo.get(i, [])]}
                           for i, v in sorted(dups.items()) if len(v) > 1],
        "edition_diff": edition,
    }


def review_imos(rec) -> list:
    """IMOs worth a tracker lead: dropped rows, status findings no pending batch already
    covers, IGU-only candidates, active backend rows IGU never listed, and vessels that
    left the IGU orderbook without being delivered."""
    imos = [x["backend"]["imo"] for x in rec["dropped"]]
    imos += [m["backend"]["imo"] for m in rec["matched"]
             if m["status_finding"] and not m["status_finding"]["pending_agrees"]]
    imos += [x["igu"]["imo"] for x in rec["igu_only"] if not x["out_of_scope"]]
    imos += [x["backend"]["imo"] for x in rec["backend_not_in_igu"]
             if x["reason"].startswith("active") and x["backend"]["imo"]]
    imos += [r["imo"] for r in (rec.get("edition_diff") or {}).get("orderbook_dropped", [])]
    return list(dict.fromkeys(i for i in imos if i))


def fetch_leads(imos, path: Path, delay=6.0, jitter=2.0) -> None:
    """Paced, resumable shipvault lookup (open API via imo_tracker) -> `path`. One host, so
    it is paced like sweep.py (6 s ± 2 s) and stops after 3 consecutive failures."""
    import random
    import time
    from imo_tracker import shipvault_search, shipvault_unit
    out = json.loads(path.read_text()) if path.exists() else []
    done = {r["imo"] for r in out if r.get("unit")}
    todo = [i for i in imos if i not in done]
    fails = 0
    for n, imo in enumerate(todo, start=1):
        try:
            hits = shipvault_search(imo)
            unit = shipvault_unit(hits[0]["id"]) if hits else None
            fails = 0 if hits else fails + 1
        except Exception as e:  # noqa: BLE001 — a lead lookup must never kill the run
            hits, unit = [], None
            fails += 1
            print(f"  lead {imo}: {e}", file=sys.stderr)
        out = [r for r in out if r["imo"] != imo] + [{"imo": imo, "hits": hits[:3], "unit": unit}]
        path.write_text(json.dumps(out, indent=1, default=str))
        print(f"  lead {n}/{len(todo)} {imo}: {(unit or {}).get('name')} | "
              f"{(unit or {}).get('status')}", file=sys.stderr)
        if fails >= 3:
            print("  3 consecutive lead failures — stopping (re-run resumes)", file=sys.stderr)
            break
        if n < len(todo):
            time.sleep(delay + random.uniform(-jitter, jitter))


def load_leads(path: Path) -> dict:
    """Compact per-IMO lead from the shipvault unit record. A lead, never a [ref]."""
    if not path.exists():
        return {}
    leads = {}
    for r in json.loads(path.read_text()):
        u, hit = r.get("unit") or {}, (r.get("hits") or [{}])[0]
        if not u:
            continue
        leads[r["imo"]] = {
            "name": " ".join(x for x in (u.get("unit"), u.get("name")) if x),
            "status": u.get("status") or "",
            "owner": u.get("owner") or "",
            "fate_date": (u.get("fatedate") or "")[:10],
            "delivered": (u.get("delivered") or "")[:10],
            "url": hit.get("url") or (f"https://www.shipvault.com/ships/{u['unitid']}"
                                      if u.get("unitid") else ""),
        }
    return leads


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--igu", help="current-edition JSON from igu_fleet.py "
                                  "(default: newest work/igu_fleet_*.json)")
    ap.add_argument("--prev", help="previous-edition JSON (default: the next-newest one; "
                                   "'none' to skip the edition comparison)")
    ap.add_argument("--backend", help="backend CSV (default work/backend.csv)")
    ap.add_argument("--pending", nargs="*", default=[],
                    help="batch dirs whose decisions.csv proposals should be cross-referenced")
    ap.add_argument("--output", help="default work/igu_reconcile.json")
    ap.add_argument("--leads", help="shipvault lead cache (default work/igu_review_shipvault.json); "
                                    "attached to the output when it exists")
    ap.add_argument("--fetch-leads", action="store_true",
                    help="paced shipvault lookup of the review-bucket IMOs into --leads first "
                         "(resumable; ~6 s per IMO)")
    args = ap.parse_args(argv)

    found = sorted(work_dir().glob("igu_fleet_*.json"))
    igu_path = Path(args.igu) if args.igu else (found[-1] if found else None)
    if not igu_path or not igu_path.exists():
        sys.exit("no IGU fleet JSON — run scripts/igu_fleet.py <report.pdf> first")
    if args.prev == "none":
        prev_path = None
    else:
        older = [p for p in found if p != igu_path and p.name < igu_path.name]
        prev_path = Path(args.prev) if args.prev else (older[-1] if older else None)

    igu = json.loads(igu_path.read_text())
    prev = json.loads(prev_path.read_text()) if prev_path else None
    be = load_backend(args.backend)
    rec = reconcile(igu, prev, backend_entries(be), load_pending(args.pending))
    rec["pending_batches"] = [Path(d).name for d in args.pending]
    leads_path = Path(args.leads) if args.leads else work_dir() / "igu_review_shipvault.json"
    if args.fetch_leads:
        fetch_leads(review_imos(rec), leads_path)
    rec["leads"] = load_leads(leads_path)
    # Rows are never deleted: a scrapped vessel moves to Status `scrapped` (IG §5.2). The
    # Dec 2025 first-release line is kept as context only (scrapped before / after release).
    for x in rec["dropped"]:
        fate = rec["leads"].get(x["backend"]["imo"], {}).get("fate_date", "")
        x["fate_vs_inclusion"] = ("" if not fate else
                                  "before Dec 2025 — scrapped before the first release" if fate < "2025-12-01" else
                                  "Dec 2025 or later — scrapped since the first release")

    out = Path(args.output) if args.output else work_dir() / "igu_reconcile.json"
    out.write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    s = rec["summary"]
    print(f"IGU {rec['edition']} ({rec['asof']}) vs backend — prev edition: {rec['prev_edition']}",
          file=sys.stderr)
    print(f"  matched {s['matched']} ({s['matched_with_diffs']} with diffs: "
          f"{s['diffs_igu_changed']} igu_changed, {s['diffs_new_to_igu']} new_to_igu, "
          f"{s['diffs_backend_differs']} backend_differs)", file=sys.stderr)
    print(f"  status findings {s['status_findings']} "
          f"({s['status_findings_not_pending']} not already proposed)", file=sys.stderr)
    print(f"  dropped from IGU {s['dropped']} | backend not in IGU {s['backend_not_in_igu']} | "
          f"IGU only {s['igu_only']} (candidates {s['igu_only_candidates']}, IMO defect "
          f"{s['igu_only_imo_defect']}, out of scope {s['igu_only_out_of_scope']}) | "
          f"IGU no-IMO {s['igu_no_imo_rows']} rows / {s['igu_no_imo_clusters']} clusters | "
          f"IGU duplicate IMOs {s['igu_duplicates']}", file=sys.stderr)
    print(f"  -> {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
