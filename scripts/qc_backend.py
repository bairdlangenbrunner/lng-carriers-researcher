"""
QC sanity check for the backend CSV — catch column-offset / misplaced-value corruption.

The backend is a human-edited Google Sheet; a copy/paste with a column offset can
silently drop a value into the wrong column (e.g. the Capacity-units token `cbm`
landing in `Yard location longitude`, or the propulsion token `ME-GA` in
`Operator/charterer`). Nothing else in the toolchain looks at cell *content* —
recalc.py checks formulas, pull_backend.py checks headers. This does the per-cell
content checks.

Run after pull_backend.py (reads work/backend.csv + work/backend.colmap.json):

    python scripts/qc_backend.py                 # advisory: report + warn, exit 0
    python scripts/qc_backend.py --strict         # exit 1 if any HIGH/MED finding
    python scripts/qc_backend.py --rows 1216-1217 # scope to a row-id range

Writes work/qc_report.csv (row_id, column, value, check, severity, message).
Known-legit oddities can be silenced in refdata/qc_allowlist.csv
(columns: row_id, column, reason; a blank `column` silences a row-level finding).

Checks:
  - misplaced-vocab : a controlled-vocab token (cbm / ME-GA / membrane / …) sitting
                      in a column it doesn't belong to                         [HIGH]
  - bad-ref         : a [ref] cell that isn't a URL                            [HIGH]
  - url-in-value    : a non-[ref] value column holding a URL                   [HIGH]
  - bad-shape       : lat/lon out of range, Capacity/IMO non-numeric, Delivery
                      year not a year, Contract date unparseable, off-vocab
                      units/currency                                       [HIGH/MED]
  - orphan-ref      : a [ref] populated with its data value blank (Rule F)     [MED]
  - lookup-mismatch : yard/owner country disagreeing with the facts tables     [MED]
  - missing-pair    : Capacity without units / Price without currency          [LOW]
  - column-offset   : a row with >=3 cell findings — the offset signature       [HIGH]
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from paths import backend_csv_path, work_dir
from normalize import normalize_builder, normalize_owner
from lookups import (CONTROLLED_VOCAB, AMBIGUOUS, refdata_dir,
                     load_builder_facts, load_owner_facts)
from derive_fills import parse_date

HIGH, MED, LOW = "HIGH", "MED", "LOW"
URL_RE = re.compile(r"https?://", re.I)

YARD_COORD_COLS = ["Yard location latitude", "Yard location longitude",
                   "Yard location plus code", "Yard location accuracy"]


def _num(v):
    try:
        return float(v.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def looks_url(s):
    return bool(URL_RE.search(s or ""))


def _looks_misplaced_data(s):
    """True if `s` looks like a structured DATA value (so it's corruption when it
    lands in a [ref] cell). Deliberately tight, so human-entered provenance tokens
    ('clarkson', 'inferred', a marine-tracker page title) are NOT flagged."""
    s = s.strip()
    if s.lower() in VOCAB_OWNER:                       # a controlled-vocab token
        return True
    if re.fullmatch(r"\d{4}", s) and 1900 <= int(s) <= 2100:   # a bare year
        return True
    if parse_date(s):                                  # a date
        return True
    if re.fullmatch(r"[\d,]{3,}", s):                  # a bare number (capacity/imo/price)
        return True
    return False


# --- per-column shape checks (run only on non-blank cells) ---------------------
def _lat(v):
    f = _num(v)
    if f is None:
        return "not numeric (latitude expected)"
    if not -90 <= f <= 90:
        return f"latitude out of range [-90,90]: {f}"


def _lon(v):
    f = _num(v)
    if f is None:
        return "not numeric (longitude expected)"
    if not -180 <= f <= 180:
        return f"longitude out of range [-180,180]: {f}"


def _year(v):
    s = v.strip()
    years = re.findall(r"\d{4}", s)
    # accept a single year or a "YYYY-YYYY" delivery-window range (both used in backend)
    if re.fullmatch(r"\d{4}(\s*[-/]\s*\d{4})?", s) and years \
            and all(1900 <= int(y) <= 2100 for y in years):
        return
    return "not a 4-digit year or year range"


_MONTH = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"


def _date(v):
    s = v.strip()
    if parse_date(s):
        return
    # parse_date only knows 3-letter months; also accept full month names,
    # month-year, and bare-year partials that appear in the backend.
    if re.fullmatch(rf"\d{{1,2}}[-\s]{_MONTH}[-\s]\d{{4}}", s, re.I):
        return
    if re.fullmatch(rf"{_MONTH}[-\s.,]*\d{{4}}", s, re.I):
        return
    if re.fullmatch(r"\d{4}([-/]\d{1,2})?", s):
        return
    return "not a recognizable date"


def _intish(label):
    def f(v):
        if _num(v) is None:
            return f"not numeric ({label} expected)"
    return f


def _in(label, allowed):
    def f(v):
        if v.strip() not in allowed:
            return f"{label} {v!r} not in {sorted(allowed)}"
    return f


SHAPE_CHECKS = {
    "Yard location latitude": (_lat, HIGH),
    "Yard location longitude": (_lon, HIGH),
    "Capacity": (_intish("Capacity"), MED),
    "IMO number": (_intish("IMO number"), MED),
    "Delivery year": (_year, MED),
    "Contract date": (_date, MED),
    "Capacity units": (_in("Capacity units", CONTROLLED_VOCAB["Capacity units"]), MED),
    "Price currency": (_in("Price currency", CONTROLLED_VOCAB["Price currency"]), MED),
}

# Reverse vocab index: token (lowercased) -> the column(s) it legitimately belongs to.
VOCAB_OWNER = defaultdict(set)
for _col, _vals in CONTROLLED_VOCAB.items():
    for _v in _vals:
        VOCAB_OWNER[_v.lower()].add(_col)


def is_ref(h):
    return h.strip().endswith("[ref]")


def load_allowlist():
    """{(row_id, column)} to silence; column '' silences a row-level finding."""
    path = refdata_dir() / "qc_allowlist.csv"
    out = set()
    if path.exists():
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                out.add(((row.get("row_id") or "").strip(),
                         (row.get("column") or "").strip()))
    return out


def scan(header, data, rid_idx, row_filter=None):
    """Yield findings: dict(row_id, column, value, check, severity, message)."""
    H = {h: i for i, h in enumerate(header) if h.strip()}  # named columns only
    builder_facts = load_builder_facts()
    owner_facts = load_owner_facts()
    findings = []
    builders_missing, owners_missing = set(), set()

    def cell(r, h):
        i = H.get(h)
        return r[i].strip() if i is not None and len(r) > i else ""

    for r in data:
        rid = r[rid_idx].strip() if len(r) > rid_idx else ""
        if row_filter and not row_filter(rid):
            continue
        row_hits = set()  # distinct columns with a cell-level finding (offset signal)

        def add(col, val, check, sev, msg):
            findings.append({"row_id": rid, "column": col, "value": val,
                             "check": check, "severity": sev, "message": msg})
            row_hits.add(col)

        for h, i in H.items():  # named columns only (empty headers skipped)
            v = r[i].strip() if len(r) > i else ""
            if not v:
                continue
            if is_ref(h):
                # A [ref] normally holds URL(s), but non-URL provenance tokens
                # ('clarkson', 'inferred', tracker page titles) are legitimate.
                # Only flag when a part looks like a misplaced DATA value.
                bad = [p for p in v.split(", ")
                       if p.strip() and not looks_url(p) and _looks_misplaced_data(p)]
                if bad:
                    add(h, v, "misplaced-in-ref", HIGH,
                        f"[ref] holds structured data {bad[0]!r} (likely a misplaced value)")
                continue
            # non-ref value column:
            low = v.lower()
            if low in VOCAB_OWNER and h not in VOCAB_OWNER[low]:
                add(h, v, "misplaced-vocab", HIGH,
                    f"{v!r} is a controlled value for {sorted(VOCAB_OWNER[low])}, not {h!r}")
            if looks_url(v):
                add(h, v, "url-in-value", HIGH, f"non-[ref] column {h!r} holds a URL")
            if h in SHAPE_CHECKS:
                fn, sev = SHAPE_CHECKS[h]
                msg = fn(v)
                if msg:
                    add(h, v, "bad-shape", sev, msg)

        # Rule F: a populated [ref] whose data value is blank
        for h, i in H.items():
            if not is_ref(h):
                continue
            ref_val = r[i].strip() if len(r) > i else ""
            if not ref_val:
                continue
            base = h[:-len(" [ref]")].strip()
            if base == "Yard location lat/lon":
                has_val = any(cell(r, c) for c in YARD_COORD_COLS)
            elif base in H:
                has_val = bool(cell(r, base))
            else:
                continue
            if not has_val:
                add(h, ref_val, "orphan-ref", MED,
                    f"[ref] populated but {base!r} is blank (Rule F)")

        # missing pairs
        if cell(r, "Capacity") and not cell(r, "Capacity units"):
            add("Capacity units", "", "missing-pair", LOW, "Capacity present without units")
        if cell(r, "Price") and not cell(r, "Price currency"):
            add("Price currency", "", "missing-pair", LOW, "Price present without currency")

        # lookup-table disagreement + coverage gaps
        btag = normalize_builder(cell(r, "Shipbuilder"))
        if btag:
            if btag in builder_facts:
                tv = builder_facts[btag].get("Shipbuilder yard country/area", "")
                cur = cell(r, "Shipbuilder yard country/area")
                if tv and tv != AMBIGUOUS and cur and cur != tv:
                    add("Shipbuilder yard country/area", cur, "lookup-mismatch", MED,
                        f"yard country {cur!r} disagrees with shipbuilder_facts ({tv!r})")
            else:
                builders_missing.add(btag)
        otag = normalize_owner(cell(r, "Shipowner"))
        if otag:
            if otag in owner_facts:
                tv = owner_facts[otag].get("Shipowner country/area", "")
                cur = cell(r, "Shipowner country/area")
                if tv and tv != AMBIGUOUS and cur and cur != tv:
                    add("Shipowner country/area", cur, "lookup-mismatch", MED,
                        f"owner country {cur!r} disagrees with shipowner_facts ({tv!r})")
            else:
                owners_missing.add(otag)

        # column-offset signature: many cell findings in one row
        if len(row_hits) >= 3:
            findings.append({"row_id": rid, "column": "", "value": "",
                             "check": "column-offset", "severity": HIGH,
                             "message": f"{len(row_hits)} cells fail placement/shape checks "
                                        f"in one row — likely a column offset"})

    return findings, builders_missing, owners_missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=str(backend_csv_path()))
    ap.add_argument("--rows", help="Limit to a row-id range, e.g. 1216-1217")
    ap.add_argument("--strict", action="store_true",
                    help="Exit 1 if any non-allowlisted HIGH/MED finding remains")
    ap.add_argument("--out", default=str(work_dir() / "qc_report.csv"))
    args = ap.parse_args()

    rows = list(csv.reader(open(args.backend, encoding="utf-8")))
    colmap = json.loads(Path(args.backend).with_suffix(".colmap.json").read_text())
    header = rows[colmap["_header_row_idx"]]
    data = rows[colmap.get("_data_starts_at", colmap["_header_row_idx"] + 1):]
    rid_idx = colmap["row_id"]

    row_filter = None
    if args.rows:
        lo, hi = (int(x) for x in args.rows.split("-"))
        row_filter = lambda rid: rid.isdigit() and lo <= int(rid) <= hi

    findings, builders_missing, owners_missing = scan(header, data, rid_idx, row_filter)

    allow = load_allowlist()
    kept = [f for f in findings if (f["row_id"], f["column"]) not in allow]
    silenced = len(findings) - len(kept)

    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["row_id", "column", "value", "check", "severity", "message"])
        for fi in kept:
            w.writerow([fi["row_id"], fi["column"], fi["value"][:120],
                        fi["check"], fi["severity"], fi["message"]])

    sev_counts = Counter(f["severity"] for f in kept)
    chk_counts = Counter(f["check"] for f in kept)
    print(f"QC scan: {len(kept)} finding(s) across "
          f"{len({f['row_id'] for f in kept})} row(s)"
          + (f"  ({silenced} allowlisted)" if silenced else ""), file=sys.stderr)
    if kept:
        print(f"  by severity: {dict(sev_counts)}", file=sys.stderr)
        print(f"  by check:    {dict(chk_counts)}", file=sys.stderr)
        offset_rows = sorted({f["row_id"] for f in kept if f["check"] == "column-offset"},
                             key=lambda s: int(s) if s.isdigit() else 0)
        if offset_rows:
            print(f"  LIKELY COLUMN OFFSET in rows: {', '.join(offset_rows)}", file=sys.stderr)
        print(f"  full report: {args.out}", file=sys.stderr)
    def _coverage(label, missing, fname):
        if not missing:
            return
        shown = sorted(missing)[:12]
        more = f" … +{len(missing) - 12} more" if len(missing) > 12 else ""
        print(f"  [coverage] {len(missing)} {label} tag(s) not in {fname}: "
              f"{', '.join(shown)}{more}", file=sys.stderr)

    _coverage("builder", builders_missing, "shipbuilder_facts.csv")
    _coverage("owner", owners_missing, "shipowner_facts.csv")

    if args.strict and any(f["severity"] in (HIGH, MED) for f in kept):
        sys.exit(1)


if __name__ == "__main__":
    main()
