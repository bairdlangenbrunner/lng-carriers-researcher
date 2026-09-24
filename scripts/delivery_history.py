#!/usr/bin/env python3
"""Delivery history: a later Delivery year carries the former year along (RF §4.19).

Every `Delivery year` cell in a fix batch that moves the year LATER than the backend's gets
two companion cells on the same row:

  * `Previous delivery year(s)` — the existing cell + "; " + the former year (oldest first,
    never twice). An `append_ref` cell gated on the former year (`gate_value`). Ref candidates:
    the row's existing `Delivery year [ref]` URLs (the fix is about to replace them) and the
    IGU report PDF of any edition whose extraction (`work/igu_fleet_<edition>.json`) prints the
    former year for the row's IMO. An IGU landing page cannot pass §3.8c and is not asked.
    No passing ref is not a reason to drop the line — the former year is the backend's own
    published value — the `[ref]` is then blank.
  * `Delivery delayed` = `yes` (derived; the column has no `[ref]`).

Both take the confidence of their Delivery year cell and are decided together with it. A year
moved earlier, or a non-numeric year, is not a delay and gets nothing. Idempotent: the
Delivery year cell is stamped `former_year`.

    python scripts/delivery_history.py --batch batches/<dir>      # or a fix.json; patches in place
    python scripts/delivery_history.py --batch <dir> --dry-run
    python scripts/delivery_history.py --batch <dir> --no-gate    # offline: IGU refs only
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backend_io  # noqa: E402
from other_names import IGU_PDF, UNGATEABLE, _split_refs  # noqa: E402
from paths import work_dir  # noqa: E402

PREV, FLAG = "Previous delivery year(s)", "Delivery delayed"


def split_years(cell: str) -> list[str]:
    return [y.strip() for y in (cell or "").split(";") if y.strip()]


def _year(v) -> int | None:
    s = str(v or "").strip()
    return int(s) if s.isdigit() and len(s) == 4 else None


_DELIVERY_WORDS = r"(?:deliver\w*|hand(?:ed)?[ -]?over|due|scheduled|slated|complet\w+|built|build year)"


def states_delivery_year(url: str, year: str) -> tuple[bool, str]:
    """§3.8c for a bare year, stricter than `corroborates`: a page passes that on any dated
    sidebar headline, so the year must share a sentence (100 characters, no full stop) with delivery wording."""
    from url_verifier import _fetch, corroborates, visible_text
    ok, reason = corroborates(url, year)
    if not ok:
        return False, reason
    text = visible_text(_fetch(url).text)
    near = re.search(rf"{_DELIVERY_WORDS}[^.]{{0,100}}\b{year}\b|\b{year}\b[^.]{{0,100}}{_DELIVERY_WORDS}", text, re.I)
    return (True, "OK") if near else (False, f"prints {year} but not as a delivery year")


def load_backend():
    work = work_dir()
    rows = list(csv.reader(open(work / "backend.csv", encoding="utf-8")))
    cm = json.loads((work / "backend.colmap.json").read_text())
    header = rows[cm["_header_row_idx"]]
    hi = {h: i for i, h in enumerate(header)}
    missing = [c for c in (PREV, PREV + " [ref]", FLAG) if c not in hi]
    if missing:
        sys.exit(f"backend has no column(s) {missing} — pull a fresh backend (python scripts/pull_backend.py)")
    by_id = backend_io.load_backend(work / "backend.csv").row_by_id()   # legacy ids resolve too
    get = lambda r, h: r[hi[h]].strip() if len(r) > hi[h] else ""
    return by_id, get, cm


def load_igu_years() -> dict:
    """{edition: {imo: delivery_year}} from every extraction in work/ that has a citable PDF."""
    out = {}
    for ed in IGU_PDF:
        p = work_dir() / f"igu_fleet_{ed}.json"
        if not p.exists():
            continue
        g, seen = json.loads(p.read_text()), {}
        for t in ("fleet", "orderbook"):
            for x in g[t]:
                if x.get("imo"):
                    seen.setdefault(x["imo"], set()).add(x.get("delivery_year"))
        out[ed] = {imo: ys.pop() for imo, ys in seen.items() if len(ys) == 1}   # IGU's duplicate IMOs: skip
    return out


def history_cells(corr: dict, be_row, get, cm, igu: dict, gate: bool) -> tuple[list, str | None]:
    """([new cells], skip reason) for one correction."""
    dy = next((c for c in corr["cells"] if c.get("field") == "Delivery year"), None)
    if dy is None:
        return [], None
    old, new = _year(get(be_row, "Delivery year")), _year(dy.get("new_value"))
    dy["former_year"] = get(be_row, "Delivery year")            # stamped = looked at (build_workbook warns otherwise)
    if old is None or new is None:
        return [], "non-numeric year"
    if new <= old:
        return [], None                                        # earlier / unchanged: not a delay
    if any(c.get("field") == PREV for c in corr["cells"]):
        return [], None
    years = split_years(get(be_row, PREV))
    if str(old) not in years:
        years.append(str(old))

    imo, refs, log = be_row[cm["imo"]].strip(), [], []
    for url in _split_refs(get(be_row, "Delivery year [ref]")):
        if any(u in url for u in UNGATEABLE):
            log.append("IGU landing page not asked")
            continue
        if not gate:
            continue
        ok, reason = states_delivery_year(url, str(old))
        (refs if ok else log).append({"url": url, "soft": False} if ok else f"{url}: {reason}")
    for ed in sorted(igu):
        if igu[ed].get(imo) == old:
            refs.append({"url": IGU_PDF[ed], "soft": False})
            log.append(f"IGU {ed} prints {old} for IMO {imo}")

    conf = dy.get("confidence", "Y")
    note = (f"former Delivery year {old} (now proposed {new}) — decide with the Delivery year line"
            + ("; " + "; ".join(log) if log else "") + ("" if refs else "; no ref prints the former year — [ref] left blank"))
    return [{"field": PREV, "new_value": "; ".join(years), "gate_value": str(old), "append_ref": True,
             "confidence": conf, "refs": refs, "note": note},
            {"field": FLAG, "new_value": "yes", "confidence": conf, "refs": [],
             "note": f"derived: Delivery year {old} -> {new} — decide with the Delivery year line"}], None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batch", required=True, help="batch dir (its fix.json) or a fix.json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-gate", action="store_true", help="do not fetch the row's existing refs (IGU refs only)")
    a = ap.parse_args()
    path = Path(a.batch)
    path = path / "fix.json" if path.is_dir() else path
    payload = json.loads(path.read_text())
    by_id, get, cm = load_backend()
    igu = load_igu_years()

    added, skipped = [], []
    for corr in payload.get("corrections", []):
        row = by_id.get(str(corr["row_id"]))
        if row is None:
            skipped.append((corr["row_id"], "row_id not in backend"))
            continue
        cells, why = history_cells(corr, row, get, cm, igu, gate=not a.no_gate)
        if why:
            skipped.append((corr["row_id"], why))
        if cells:
            corr["cells"].extend(cells)
            added.append((corr["row_id"], cells[0]["new_value"], len(cells[0]["refs"])))
    for rid, val, n in added:
        print(f"  row_id {rid}: {PREV} = {val!r} ({n} ref{'s' * (n != 1)}), {FLAG} = yes")
    for rid, why in skipped:
        print(f"  row_id {rid}: skipped — {why}")
    print(f"{len(added)} delayed row(s), {sum(1 for _, _, n in added if not n)} with a blank ref")
    if not a.dry_run:
        path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
