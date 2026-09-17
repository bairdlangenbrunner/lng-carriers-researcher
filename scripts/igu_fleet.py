"""
IGU World LNG Report — fleet-table extractor (Appendix 3 active fleet + Appendix 4
orderbook) -> JSON, for the IGU reconciliation (docs/sops/igu_reconciliation.md).

The tables are typeset, not tagged, and the layout changes between editions:

  2025 edition   one report page per PDF page; fleet = 9 columns (no Age);
                 orderbook = 7 columns (no Vessel Type; capacity headed "(cbm)").
  2026 edition   two report pages per PDF page (a landscape spread), so ONE PDF
                 page carries TWO independent tables side by side, each with its
                 own header; fleet gained an Age column; orderbook gained a
                 Vessel Type column placed LAST. A spread can also carry an
                 unrelated table in its other half (liquefaction plants next to
                 the first fleet page).

`pdftotext -layout` interleaves the two halves of a spread line by line and gives
no column boundaries, so this works from word coordinates (pdfplumber) instead and
assumes nothing about the column set:

  1. every "IMO" header word starts a table; its header band is read into column
     labels, and each column's left edge is the x0 of its label (cells are
     left-aligned under their header in every edition so far);
  2. a table's x-extent runs to the next table on the page (or the spread's
     midline), its y-extent to the next header below it or the footer;
  3. a row starts at each word in the IMO column (IMO cells never wrap; the
     orderbook prints "Unknown" for hulls with no IMO yet — kept, with imo "");
     cells are top-aligned, so everything down to the next row's first line
     belongs to the row (wrapped owner / builder / name lines). The last row stops
     at the first line gap wider than a wrapped-line pitch;
  4. the table kind (fleet / orderbook) comes from the "Appendix N: …" title above
     the header, falling back to the column set (only the fleet has Cargo Type).

Every record is validated (IMO check digit, numeric capacity, plausible year,
no empty required cell) and the run is cross-checked against an independent
count of IMO-shaped tokens on the same pages; anything off lands in `warnings`
and the exit code is 1 under --strict. Never edits the backend.

Usage:
    python scripts/igu_fleet.py ../lng-terminals-researcher/data/IGU-World-LNG-Report-2026.pdf
    python scripts/igu_fleet.py <pdf> --output work/igu_fleet_2026.json --strict
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

from paths import work_dir

IMO_RE = re.compile(r"^\d{7}$")

# header label (lowercased, whitespace-collapsed) -> record field
FIELD_BY_LABEL = {
    "imo number": "imo",
    "name": "name",
    "shipowner": "shipowner",
    "shipbuilder": "shipbuilder",
    "capacity (cm)": "capacity",
    "capacity (cbm)": "capacity",
    "capacity": "capacity",
    "cargo type": "cargo_type",
    "vessel type": "vessel_type",
    "propulsion type": "propulsion",
    "delivery year": "delivery_year",
    "age": "age",
}
REQUIRED = {
    "fleet": ("imo", "name", "shipowner", "shipbuilder", "capacity", "cargo_type",
              "vessel_type", "propulsion", "delivery_year"),
    # the orderbook legitimately prints "Unknown" IMOs and blank propulsion cells
    # for recent orders — counted in `counts`, not warned about
    "orderbook": ("name", "shipowner", "shipbuilder", "capacity", "delivery_year"),
}

LINE_TOL = 2.5        # words within this many points of `top` are one text line
HEADER_DEPTH = 14     # a header is at most two text lines deep
COL_GAP = 6           # header words closer than this belong to one column label
FOOTER_MARGIN = 45    # page number / running footer sits in the bottom margin
WRAP_PITCH = 1.7      # last row: stop at a line gap wider than this x line height


def imo_checksum_ok(imo: str) -> bool:
    """IMO check digit: sum(d_i * (7..2)) over the first six digits, mod 10."""
    if not IMO_RE.match(imo or ""):
        return False
    return sum(int(d) * w for d, w in zip(imo[:6], range(7, 1, -1))) % 10 == int(imo[6])


def _lines(words):
    """Group words into text lines (top-to-bottom), each sorted left-to-right."""
    out = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if out and abs(w["top"] - out[-1][0]["top"]) <= LINE_TOL:
            out[-1].append(w)
        else:
            out.append([w])
    return [sorted(l, key=lambda w: w["x0"]) for l in out]


def _join(parts):
    """Join a cell's wrapped lines: 'ex-' + 'Jiangnan' -> 'ex-Jiangnan', else a space."""
    text = ""
    for p in parts:
        if text and text.endswith("-") and not text.endswith(" -"):
            text += p
        else:
            text = f"{text} {p}".strip()
    return re.sub(r"\s+", " ", text).strip()


def find_tables(page):
    """Locate every IMO-headed table on a page.

    Returns dicts: {left, right, top, bottom, columns: [(field, label, x0)], kind,
    title}. `top` is the first y below the header band."""
    words = page.extract_words(x_tolerance=1.5, y_tolerance=2, keep_blank_chars=False)
    heads = [w for w in words if w["text"] == "IMO"]
    # a real header has "Number" beside or under it
    heads = [h for h in heads if any(
        w["text"] == "Number" and 0 <= w["top"] - h["top"] <= HEADER_DEPTH
        and -2 <= w["x0"] - h["x0"] <= 40 for w in words)]
    spread = page.width > page.height          # two report pages side by side
    mid = page.width / 2
    tables = []
    for h in heads:
        left = h["x0"] - 3
        same_row = [o["x0"] for o in heads
                    if o is not h and o["x0"] > h["x0"] + 50 and abs(o["top"] - h["top"]) < 40]
        right = min(same_row) - 5 if same_row else page.width
        if spread and h["x0"] < mid:
            right = min(right, mid)
        below = [o["top"] for o in heads
                 if o is not h and o["top"] > h["top"] + 40 and left <= o["x0"] < right]
        bottom = (min(below) - 30) if below else page.height - FOOTER_MARGIN

        band = [w for w in words if left <= w["x0"] < right
                and -1 <= w["top"] - h["top"] <= HEADER_DEPTH]
        first = sorted((w for w in band if abs(w["top"] - h["top"]) <= LINE_TOL),
                       key=lambda w: w["x0"])
        groups = []
        for w in first:
            if groups and w["x0"] - groups[-1][-1]["x1"] < COL_GAP:
                groups[-1].append(w)
            else:
                groups.append([w])
        columns = []
        for i, g in enumerate(groups):
            x0 = g[0]["x0"]
            x_next = groups[i + 1][0]["x0"] if i + 1 < len(groups) else right
            second = sorted((w for w in band if w["top"] - h["top"] > LINE_TOL
                             and x0 - 1 <= w["x0"] < x_next - 1), key=lambda w: w["x0"])
            label = " ".join(w["text"] for w in g + second)
            field = FIELD_BY_LABEL.get(re.sub(r"\s+", " ", label).strip().lower())
            columns.append((field, label, x0))

        # the "Appendix N: …" title is the nearest such line above the header,
        # in this table's half of the page
        title = ""
        for line in reversed(_lines([w for w in words if left - 5 <= w["x0"] < right
                                     and w["top"] < h["top"] - 3])):
            text = " ".join(w["text"] for w in line)
            if text.startswith("Appendix"):
                title = text
                break
        fields = {c[0] for c in columns}
        low = title.lower()
        if "orderbook" in low:
            kind = "orderbook"
        elif "fleet" in low:
            kind = "fleet"
        else:
            kind = "fleet" if "cargo_type" in fields else "orderbook"
        header_bottom = max(w["bottom"] for w in band)
        tables.append({"left": left, "right": right, "top": header_bottom + 1,
                       "bottom": bottom, "columns": columns, "kind": kind,
                       "title": title, "words": words})
    return sorted(tables, key=lambda t: (t["left"], t["top"]))


def read_table(tbl):
    """Rows of one table: list of {field: text}."""
    cols = tbl["columns"]
    imo_x = next(x for f, _, x in cols if f == "imo")
    body = [w for w in tbl["words"] if tbl["left"] <= w["x0"] < tbl["right"]
            and tbl["top"] <= w["top"] < tbl["bottom"]]
    lines = _lines(body)
    # IMO cells never wrap, so ANY word in the IMO column opens a row — including the
    # "Unknown" the orderbook prints for hulls with no IMO assigned yet
    starts = [i for i, l in enumerate(lines) if abs(l[0]["x0"] - imo_x) < 4]
    if not starts:
        return []
    heights = [w["bottom"] - w["top"] for w in body] or [8]
    pitch = WRAP_PITCH * (sorted(heights)[len(heights) // 2])
    rows = []
    for n, s in enumerate(starts):
        if n + 1 < len(starts):
            block = lines[s:starts[n + 1]]
        else:                       # last row: wrapped lines only, stop at a gap
            block = [lines[s]]
            for l in lines[s + 1:]:
                if l[0]["top"] - block[-1][0]["top"] > pitch:
                    break
                block.append(l)
        cells = {f: [] for f, _, _ in cols if f}
        edges = [x for _, _, x in cols] + [tbl["right"]]
        for line in block:
            per_col = {}
            for w in line:
                # a word belongs to the last column whose left edge it reaches
                k = max((i for i, x in enumerate(edges[:-1]) if w["x0"] >= x - 2), default=0)
                per_col.setdefault(k, []).append(w["text"])
            for k, toks in per_col.items():
                f = cols[k][0]
                if f:
                    cells[f].append(" ".join(toks))
        rows.append({f: _join(parts) for f, parts in cells.items()})
    return rows


def _to_int(s):
    s = (s or "").replace(",", "").replace(" ", "")
    return int(s) if s.isdigit() else None


def extract(pdf_path):
    import pdfplumber  # local import: only this script needs it

    fleet, orderbook, warnings, per_page = [], [], [], []
    asof = None
    with pdfplumber.open(str(pdf_path)) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            tables = find_tables(page)
            if not tables:
                continue
            n_page = 0
            for t in tables:
                m = re.search(r"end-(\d{4})", t["title"])
                if m and asof is None:
                    asof = int(m.group(1))
                unknown = [lab for f, lab, _ in t["columns"] if f is None]
                if unknown:
                    warnings.append(f"p{pno}: unrecognised header label(s) {unknown} — "
                                    "add to FIELD_BY_LABEL")
                for r in read_table(t):
                    imo_raw = r.get("imo", "")
                    rec = {
                        "imo": imo_raw if IMO_RE.match(imo_raw) else "",
                        "imo_raw": imo_raw,
                        "name": r.get("name", ""),
                        "shipowner": r.get("shipowner", ""),
                        "shipbuilder": r.get("shipbuilder", ""),
                        "capacity": _to_int(r.get("capacity")),
                        "cargo_type": r.get("cargo_type", ""),
                        "vessel_type": r.get("vessel_type", ""),
                        "propulsion": r.get("propulsion", ""),
                        "delivery_year": _to_int(r.get("delivery_year")),
                        "age": _to_int(r.get("age")),
                        "table": t["kind"],
                        "pdf_page": pno,
                    }
                    for f in REQUIRED[t["kind"]]:
                        if rec.get(f) in ("", None):
                            warnings.append(f"p{pno} IMO {rec['imo']} ({rec['name']}): empty {f} "
                                            f"(raw {r.get(f)!r})")
                    if not rec["imo"] and t["kind"] == "fleet":
                        warnings.append(f"p{pno} ({rec['name']}): no IMO (raw {imo_raw!r})")
                    if rec["imo"] and not imo_checksum_ok(rec["imo"]):
                        rec["imo_checksum_ok"] = False
                        warnings.append(f"p{pno} IMO {rec['imo']} ({rec['name']}): "
                                        "fails the IMO check digit (as printed in the report)")
                    y = rec["delivery_year"]
                    if y is not None and not 1960 <= y <= 2040:
                        warnings.append(f"p{pno} IMO {rec['imo']}: implausible delivery year {y}")
                    (fleet if t["kind"] == "fleet" else orderbook).append(rec)
                    n_page += 1
            # independent count: 7-digit tokens sitting in an IMO column of this page
            words = tables[0]["words"]
            xs = [next(x for f, _, x in t["columns"] if f == "imo") for t in tables]
            n_tok = sum(1 for w in words if IMO_RE.match(w["text"])
                        and any(abs(w["x0"] - x) < 4 for x in xs))
            n_imo_rows = sum(1 for r in (fleet + orderbook)[-n_page:] if r["imo"]) if n_page else 0
            per_page.append({"pdf_page": pno, "rows": n_page, "imo_tokens": n_tok,
                             "tables": [f"{t['kind']}:{len(t['columns'])}col" for t in tables]})
            if n_tok != n_imo_rows:
                warnings.append(f"p{pno}: {n_tok} IMO tokens on the page but "
                                f"{n_imo_rows} rows with an IMO read")

    for label, recs in (("fleet", fleet), ("orderbook", orderbook)):
        dup = [i for i, c in Counter(r["imo"] for r in recs if r["imo"]).items() if c > 1]
        if dup:
            warnings.append(f"{label}: IMO listed more than once: {sorted(dup)}")
    both = sorted(({r["imo"] for r in fleet} & {r["imo"] for r in orderbook}) - {""})
    if both:
        warnings.append(f"IMO in both the fleet and the orderbook table: {both}")
    return {
        "source_pdf": Path(pdf_path).name,
        "edition": (asof + 1) if asof else None,
        "asof": f"end-{asof}" if asof else None,
        "counts": {"fleet": len(fleet), "orderbook": len(orderbook),
                   "orderbook_no_imo": sum(1 for r in orderbook if not r["imo"]),
                   "orderbook_blank_propulsion": sum(1 for r in orderbook if not r["propulsion"])},
        "pages": per_page,
        "warnings": warnings,
        "fleet": fleet,
        "orderbook": orderbook,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("pdf")
    ap.add_argument("--output", help="default: work/igu_fleet_<edition>.json")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any warning")
    args = ap.parse_args(argv)

    out = extract(args.pdf)
    path = Path(args.output) if args.output else work_dir() / f"igu_fleet_{out['edition']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"IGU {out['edition']} edition ({out['asof']}): fleet {out['counts']['fleet']}, "
          f"orderbook {out['counts']['orderbook']} ({out['counts']['orderbook_no_imo']} without "
          f"an IMO, {out['counts']['orderbook_blank_propulsion']} blank propulsion) -> {path}",
          file=sys.stderr)
    layouts = Counter(tuple(p["tables"]) for p in out["pages"])
    for lay, n in layouts.most_common():
        print(f"  {n:3d} page(s): {', '.join(lay)}", file=sys.stderr)
    for w in out["warnings"]:
        print(f"  WARNING {w}", file=sys.stderr)
    return 1 if (args.strict and out["warnings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
