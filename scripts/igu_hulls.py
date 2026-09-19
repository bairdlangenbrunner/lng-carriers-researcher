#!/usr/bin/env python3
"""
IGU hull numbers → backend (RF §4.17). The IGU World LNG Report prints a hull number in
parentheses after some names — `Al Sailiya (2641)`, `Rex Tillerson (1790A)`, `Kool Tiger
(HSHI-8196)`, `North Way (Hull 2583)`. Two uses, one fix batch:

  (a) by IMO — the row's `Hull number` is blank → propose `Hull NNNN (Tag)`; it holds the
      same hull untagged → restyle it with its yard tag (`preserve_ref`); it holds a
      different hull → no proposal, flagged.
  (b) by hull — a row still named only by its hull placeholder (`Hull 2541 (Hanwha)`) is
      matched to an IGU `Name (hull)` entry on hull number + builder family: propose the
      Name (and the IMO when the row has none). The IMO must not already sit on another row.

Every value cites the IGU PDF (sole-source ruling 2026-09-17, IG §5.4). Names already
proposed by an un-applied batch are not proposed twice. Run `other_names.py --batch` on
the output (RF §4.16: the placeholder goes into `Other names`) before `build_workbook.py`.

  python scripts/igu_hulls.py [--edition 2026] --out work/igu_hulls_fix.json
Advisory; never edits the backend.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend_io import load_backend                                   # noqa: E402
from normalize import normalize_builder                               # noqa: E402
from other_names import (FALLBACK_YARD_TAGS, IGU_PDF, fold, hull_only,  # noqa: E402
                         same_hull, yard_tags)
from paths import repo_root, work_dir                                 # noqa: E402

# the same yard under the labels IGU and the backend use (normalize_builder output)
FAMILY = {"hanwha-ocean": "hanwha", "samsung": "samsung", "hd hyundai": "hyundai",
          "hyundai-ulsan": "hyundai", "hyundai-samho": "hyundai", "hudong-zhonghua": "hudong",
          "jiangnan": "jiangnan", "zvezda": "zvezda"}
_PAREN = re.compile(r"^(.*?)\s*\(([^()]*\d[^()]*)\)\s*$")
_TAGGED = re.compile(r"\([^()]+\)\s*$")


def family(builder: str) -> str:
    b = normalize_builder(builder or "")
    return FAMILY.get(b, b)


def yard_conflict(backend_builder: str, igu_builder: str, raw_hull: str) -> str:
    """Why IGU's yard is not the row's yard ('' when they agree). IGU's `HD Hyundai` covers
    Ulsan and Samho; a hull printed `Hyundai Samho 8049` / `HSHI-8196` names Samho."""
    be_b = normalize_builder(backend_builder or "")
    igu_b = "hyundai-samho" if re.search(r"samho|hshi", raw_hull, re.I) else normalize_builder(igu_builder or "")
    if family(be_b) != family(igu_b):
        return f"IGU yard {igu_builder!r} ≠ the row's {backend_builder!r}"
    if igu_b != "hd hyundai" and be_b != igu_b:
        return f"IGU yard {igu_b} ({igu_builder!r} / {raw_hull!r}) ≠ the row's {backend_builder!r}"
    return ""


def igu_hull(printed: str) -> tuple[str, str, str]:
    """'Kool Tiger (HSHI-8196)' -> ('Kool Tiger', '8196', 'HSHI-8196'); ('', '', '') when the
    name carries no parenthetical hull (an `(ex-…)` name is other_names.py's business)."""
    if "(ex-" in printed.lower():
        return "", "", ""
    m = _PAREN.match(printed.strip())
    if not m:
        return "", "", ""
    raw = m.group(2).strip()
    toks = re.findall(r"[A-Z]?\d[\dA-Z]*", re.sub(r"^(hull|hshi|hhi|shi)[\s-]*", "", raw, flags=re.I).upper())
    if len(toks) != 1 or re.search(r"dalian|no\s*\d", raw, re.I):   # 'Dalian No 1 G175K-1': not a hull no.
        return "", "", ""
    return m.group(1).strip(), toks[0], raw


def pending_cells(fields=("Name", "IMO number", "Hull number"), skip=()) -> dict:
    """(row_id, field) -> [(batch, value)] over every batch's apply_patch.csv (all modes)."""
    import csv
    out = {}
    for f in sorted((repo_root() / "batches").glob("*/apply_patch.csv")):
        if f.parent.name in skip:
            continue
        with open(f, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                if r.get("column") in fields:
                    out.setdefault((str(r["key"]), r["column"]), []).append((f.parent.name, r.get("value", "")))
    return out


def build(edition: str, out_dir: str = ""):
    be = load_backend()
    rows, live, hi = be.row_by_id(), be.sheet_row_map(), be.header_index
    cell = lambda rid, col: be.cell(rows[rid], hi.get(col)).strip()
    ext = json.loads((work_dir() / f"igu_fleet_{edition}.json").read_text())
    pdf, tags, pend = IGU_PDF[edition], yard_tags(be), pending_cells(skip={out_dir})
    tag_of = lambda b: tags.get(b) or FALLBACK_YARD_TAGS.get(b) or b
    by_imo = {}
    for rid in rows:
        if cell(rid, "IMO number"):
            by_imo.setdefault(cell(rid, "IMO number"), []).append(rid)
    ref = [{"url": pdf, "soft": False}]
    corrections, flagged = {}, []

    def add(rid, c):
        corrections.setdefault(rid, {"row_id": rid, "_live_row": live.get(rid),
                                     "_name": cell(rid, "Name"), "cells": []})["cells"].append(c)

    igu = [r for r in ext.get("fleet", []) + ext.get("orderbook", []) if igu_hull(r["name"])[1]]
    placeholders = {rid for rid in rows if hull_only(cell(rid, "Name"))}
    for rec in igu:
        name, h, raw = igu_hull(rec["name"])
        imo = str(rec.get("imo") or "").strip()
        src = f"IGU {edition} prints {rec['name']!r} [{rec.get('table')} table, PDF p.{rec.get('pdf_page')}; IMO {imo}]"
        where = {"igu_name": rec["name"], "imo": imo}
        # (a) by IMO
        for rid in by_imo.get(imo, []):
            b, hull = cell(rid, "Shipbuilder"), cell(rid, "Hull number")
            why = yard_conflict(b, rec.get("shipbuilder"), raw)
            if why:
                flagged.append({**where, "live_row": live.get(rid), "reason": why + f" (row hull {hull or 'blank'})"})
                continue
            styled = f"Hull {hull_only(hull) or h} ({tag_of(b)})"
            prior = pend.get((rid, "Hull number"), [])
            if prior:
                flagged.append({**where, "live_row": live.get(rid), "reason":
                                f"Hull number already proposed by {prior[0][0]} ({prior[0][1]!r})"})
            elif not hull:
                add(rid, {"field": "Hull number", "new_value": f"Hull {h} ({tag_of(b)})", "gate_value": raw,
                          "confidence": "G", "refs": ref, "note": f"blank in backend; {src}"})
            elif not same_hull(h, hull_only(hull)):
                flagged.append({**where, "live_row": live.get(rid), "reason": f"IGU hull {h} ≠ the row's {hull!r}"})
            elif not _TAGGED.search(hull):
                add(rid, {"field": "Hull number", "new_value": styled, "preserve_ref": True, "confidence": "G",
                          "note": f"restyle {hull!r} → {styled!r}: a hull number names its yard (RF §4.17); {src}"})
        # (b) by hull: a placeholder row for the same yard
        cands = [rid for rid in placeholders
                 if same_hull(h, hull_only(cell(rid, "Name")))
                 and not yard_conflict(cell(rid, "Shipbuilder"), rec.get("shipbuilder"), raw)]
        for rid in cands:
            if imo and imo in by_imo and rid not in by_imo[imo]:
                flagged.append({**where, "live_row": live.get(rid), "reason":
                                f"hull matches placeholder {cell(rid, 'Name')!r}, but IMO {imo} is on live row "
                                f"{', '.join(str(live.get(r)) for r in by_imo[imo])} — possible duplicate"})
                continue
            prior = pend.get((rid, "Name"), [])
            if any(fold(v) == fold(name) for _, v in prior):
                flagged.append({**where, "live_row": live.get(rid), "reason": f"already proposed by {prior[0][0]}"})
                continue
            if prior:
                flagged.append({**where, "live_row": live.get(rid), "reason":
                                f"{prior[0][0]} proposes {prior[0][1]!r} for this row — check"})
                continue
            cap_b, cap_i = cell(rid, "Capacity"), rec.get("capacity")
            cap_ok = bool(cap_b and cap_i) and abs(float(cap_b) - float(cap_i)) <= max(6000, 0.03 * float(cap_i))
            conf = "G" if cap_ok or not cap_b else "Y"
            add(rid, {"field": "Name", "new_value": name, "gate_value": name, "confidence": conf, "refs": ref,
                      "note": f"placeholder {cell(rid, 'Name')!r} matched on hull {h} + builder "
                              f"({rec.get('shipbuilder')}); capacity {cap_b or '—'} vs IGU {cap_i}; {src}"})
            if imo and not cell(rid, "IMO number") and not pend.get((rid, "IMO number")):
                add(rid, {"field": "IMO number", "new_value": imo, "confidence": conf, "refs": ref,
                          "note": f"blank in backend; {src}"})
    return list(corrections.values()), flagged


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--edition", default="2026")
    ap.add_argument("--out", default=str(work_dir() / "igu_hulls_fix.json"))
    a = ap.parse_args()
    corrections, flagged = build(a.edition, Path(a.out).parent.name)
    payload = {"batch_label": f"Fix — hull numbers and hull-placeholder names from IGU {a.edition} (RF §4.17)",
               "reason": "IGU prints `Name (hull)`: blank Hull numbers are filled, untagged ones gain their yard "
                         "tag, and rows still named by their hull get the name IGU gives that hull.",
               "igu_ref": IGU_PDF[a.edition], "corrections": corrections, "flagged": flagged}
    Path(a.out).write_text(json.dumps(payload, indent=1, ensure_ascii=False))
    n = sum(len(c["cells"]) for c in corrections)
    print(f"igu_hulls: {n} cells on {len(corrections)} rows, {len(flagged)} flagged -> {a.out}")
    for f in flagged:
        print(f"  flagged live row {f['live_row']}: {f['igu_name']} — {f['reason']}")


if __name__ == "__main__":
    main()
