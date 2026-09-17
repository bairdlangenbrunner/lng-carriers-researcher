"""Combine the six sep-17-pass (2026-09-17) batches into one review workbook.

Read-only over the batch dirs and work/backend.csv; writes
lng_carrier_sep-17-pass_results_<YYYY-MM-DD>_<HHMM>ET.xlsx + report_data.json next to this
file. The workbook name carries the build date and US Eastern time, so every rebuild is a new
name; the previous build's file is removed (git keeps it) and build_report.py embeds the newest.
Run from the repo root: python batches/2026-09-17_1017ET_sep-17-pass_combined/build_combined.py
"""
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from copy import copy
from pathlib import Path
from zoneinfo import ZoneInfo

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from apply_batch import _detect, _discovery_full_row, _items_and_conflicts, _load_backend  # noqa: E402
from build_workbook import _join_refs, _yard_location_map_table_first  # noqa: E402
BATCHES = ROOT / "batches"
OUT_STEM = "lng_carrier_sep-17-pass_results"
BUILT = datetime.now(ZoneInfo("America/New_York"))
OUT = HERE / f"{OUT_STEM}_{BUILT:%Y-%m-%d_%H%M}ET.xlsx"

B1 = "2026-09-17_0421ET_fix_delivery_rollforward"
B2 = "2026-09-17_0458ET_fix_delivery_confirmed"
B3 = "2026-09-17_0431ET_discovery_since_jun_2026"
B4 = "2026-09-17_0511ET_data_fill_on_order"
B5 = "2026-09-17_0505ET_ref_fill_rule_f"
B6 = "2026-09-17_1114ET_shipvault_companion_refs"
# comparison only (no proposals, never applied): feeds igu_findings + one open decision
B7 = "2026-09-17_1458ET_igu_reconciliation_igu2026"
# follow-ups to B7. B8: what IGU 2026 prints, as proposals citing the report PDF (IG 5.4).
# B9: the dropped bucket -> Status scrapped (rows are never deleted) + row 61 -> FSU
B8 = "2026-09-17_1654ET_fix_igu2026_sourced"
B9 = "2026-09-17_1702ET_fix_scrapped_status"
# B10: RF 4.16 - every Name change in B1 / B2 / B8 carries the former Name into Other names
B10 = "2026-09-17_1737ET_fix_other_names_former"
# B11 / B12: Baird's evening rulings - `qc-max` is a Vessel type value; Price is always full USD
B11 = "2026-09-17_1809ET_fix_qcmax_vessel_type"
B12 = "2026-09-17_1810ET_fix_price_full_usd"
# (apply order, dir, short label, workbook, wide sheet, what)
BATCH_INFO = [
    (1, B1, "delivery roll-forward", "lng_carrier_fix.xlsx", "fix",
     "on-order rows checked against shipvault + vesselfinder / marinetraffic.org: status, delivery year, names"),
    (2, B2, "delivery confirmed by press", "lng_carrier_fix.xlsx", "fix",
     "deliveries confirmed by trade press where shipvault still says on order"),
    (3, B3, "discovery since Jun 2026", "lng_carrier_candidate_vessels.xlsx", "candidate_vessels",
     "new orders not yet in the backend (gap window 2026-05-01 to 2026-09-17)"),
    (4, B4, "data fill (on-order rows)", "lng_carrier_data_fill.xlsx", "backend_data_fill",
     "blank / unknown cells on on-order rows, plus whole-backend derivable fills"),
    (5, B5, "Rule-F ref fill", "lng_carrier_backend_ref_fill.xlsx", "backend_ref_fill",
     "data values that had no [ref] (orphans)"),
    (6, B6, "shipvault companion refs", "lng_carrier_data_fill.xlsx", "backend_data_fill",
     "existing [ref] cells citing a shipvault page that renders blank: the unit-record URL "
     "appended as a second ref (value untouched)"),
    (8, B8, "IGU 2026-sourced fix", "lng_carrier_fix.xlsx", "fix",
     "values the IGU World LNG Report 2026 prints, the report PDF as sole ref (interim rule, IG 5.4): blank Vessel / "
     "Cargo type, renames, delivery years, propulsion, load corruption on rows 451 / 499-501 / 509"),
    (9, B9, "scrapped status + FSU", "lng_carrier_fix.xlsx", "fix",
     "the 18 active rows IGU 2026 dropped -> Status scrapped (press + shipvault refs; rows are never deleted), "
     "and live row 61 Puteri Delima Satu -> Vessel type FSU (two MISC documents)"),
    (10, B10, "former names -> Other names", "lng_carrier_fix.xlsx", "fix",
     "every Name change proposed by batches 1, 2 and 8 also moves the row's former Name into Other names "
     "(appended, nothing removed; RF 4.16). Each line is decided with its Name line"),
    (11, B11, "Vessel type qc-max", "lng_carrier_fix.xlsx", "fix",
     "the 24 x 271,000 cbm QatarEnergy ships IGU 2026 types QC-max -> Vessel type qc-max (vocabulary value added "
     "2026-09-17), the report PDF as sole ref like batch 8"),
    (12, B12, "Price in full USD", "lng_carrier_fix.xlsx", "fix",
     "the 29 rows with a Price in millions + currency $m -> full US dollars + USD (unit conversion only; the "
     "existing Price [ref] is kept)"),
]

FONT = Font(name="Calibri", size=10)
FONT_B = Font(name="Calibri", size=10, bold=True)
FONT_H = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
FONT_T = Font(name="Calibri", size=12, bold=True)
FONT_LINK = Font(name="Calibri", size=10, color="0563C1", underline="single")
FONT_HOLD = Font(name="Calibri", size=10, italic=True)
FONT_DEL = Font(name="Calibri", size=10, strike=True, color="7F7F7F")
FILL_HEADER = PatternFill("solid", fgColor="1F4E78")
FILL_HELPER = PatternFill("solid", fgColor="595959")
FILL_PEACH = PatternFill("solid", fgColor="FFD9B3")
FILL_GRAY = PatternFill("solid", fgColor="EEEEEE")
CONF_FILL = {"G": PatternFill("solid", fgColor="C6EFCE"),
             "Y": PatternFill("solid", fgColor="FFEB9C"),
             "R": PatternFill("solid", fgColor="FFC7CE")}
WRAP = Alignment(wrap_text=True, vertical="top")
TOP = Alignment(vertical="top")


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---- backend context (live sheet row = csv line number) ---------------------
raw = list(csv.reader(open(ROOT / "work" / "backend.csv", newline="", encoding="utf-8")))
HDR = raw[1]
BACKEND = {}
for i, r in enumerate(raw[2:], start=3):
    if r and r[0]:
        BACKEND[r[0]] = {"live_row": i, **dict(zip(HDR, r))}


def ctx(row_id):
    b = BACKEND.get(str(row_id), {})
    return [b.get("live_row", ""), b.get("Name", ""), b.get("IMO number", ""),
            b.get("Status", ""), b.get("Shipbuilder", ""), b.get("Shipowner", "")]


def qa_sections(wb_path):
    """QA_review -> {section title: [row dicts]} (fix workbooks have one untitled table)."""
    ws = openpyxl.load_workbook(wb_path)["QA_review"]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    out, title, header = defaultdict(list), "", None
    for r in rows:
        vals = [v for v in r if v not in (None, "")]
        if not vals:
            continue
        if len(vals) == 1 and r[0] not in (None, "") and not str(r[0]).isdigit():
            title, header = str(r[0]), None
            continue
        if header is None:
            header = [h for h in r if h not in (None, "")]
            continue
        out[title].append(dict(zip(header, r)))
    return out


# ---- unified long table -----------------------------------------------------
proposals = []   # dict rows
PROP_COLS = ["apply order", "batch", "kind", "live sheet row", "row_id", "cluster",
             "vessel name (backend)", "IMO", "status (backend)", "shipbuilder", "shipowner",
             "column", "current backend value", "proposed value", "source URL(s)",
             "confidence", "derivable", "decision", "gate verdict", "note"]

for order, bdir, label, wbname, _sheet, _what in BATCH_INFO:
    qa = qa_sections(BATCHES / bdir / wbname)
    urls, verdicts, prev = defaultdict(list), defaultdict(list), {}
    if bdir in (B1, B2, B8, B9, B10, B11, B12):
        for q in next(iter(qa.values())):
            k = (str(q["row_id"]), q["field"])
            if q.get("url"):
                urls[k].append(q["url"])
            if q.get("verdict"):
                verdicts[k].append(str(q["verdict"]))
    elif bdir in (B4, B6):
        for q in qa["Candidate data-value fills"]:
            k = (str(q["row_id"]), q["field"])
            if q.get("new_urls"):
                urls[k].append(str(q["new_urls"]))
            prev[k] = q.get("prev_state") or ""
    elif bdir == B3:
        for q in qa["Per-candidate provenance log"]:
            if q.get("source_urls"):
                urls[(q["cluster_id"], "")].append(str(q["source_urls"]))
        cand = {c["cluster_id"]: c for c in load_json(BATCHES / bdir / "candidates.json")["candidates"]}

    for d in read_csv(BATCHES / bdir / "decisions.csv"):
        rid, col = d["row_id"], d["column"]
        if d["kind"] == "new_row":
            c = cand[d["cluster_id"]]
            rd = c.get("row_data") or c
            name = rd.get("Name", "")
            context = ["(new)", "", "", "", rd.get("Shipbuilder", ""), rd.get("Shipowner", "")]
            col_label, cur = "(new row)", ""
            val = name or c["cluster_label"]
            src = "\n".join(urls[(d["cluster_id"], "")])
            verdict = ""
        else:
            context = ctx(rid)
            col_label = col
            cur = BACKEND.get(rid, {}).get(col, "")
            if bdir == B4 and not cur:
                cur = ""
            val = d["proposed_value"]
            k = (rid, col[:-6] if col.endswith(" [ref]") else col)
            src = d["proposed_value"] if d["kind"] == "ref" else "\n".join(urls.get((rid, col), []) or urls.get(k, []))
            verdict = "\n".join(dict.fromkeys(verdicts.get((rid, col), [])))
        proposals.append(dict(zip(PROP_COLS, [
            order, label, d["kind"], context[0], rid, d["cluster_id"], context[1], context[2],
            context[3], context[4], context[5], col_label, cur, val, src, d["confidence"],
            d["derivable"], d["decision"], verdict, d["note"]])))

# ---- workbook ---------------------------------------------------------------
wb = openpyxl.Workbook()


def num(v):
    if isinstance(v, str) and v.isdigit() and len(v) < 8:
        return int(v)
    return v


def table_sheet(title, cols, rows, widths=None, wrap_cols=(), conf_col=None, fill_col=None,
                link_col=None, intro=None):
    ws = wb.create_sheet(title)
    r0 = 1
    if intro:
        ws.cell(1, 1, intro).font = FONT_B
        r0 = 3
    for j, c in enumerate(cols, 1):
        cell = ws.cell(r0, j, c)
        cell.font, cell.fill, cell.alignment = FONT_H, FILL_HEADER, WRAP
    for i, row in enumerate(rows, r0 + 1):
        for j, c in enumerate(cols, 1):
            v = row.get(c, "") if isinstance(row, dict) else row[j - 1]
            if isinstance(v, (list, dict)):
                v = "\n".join(map(str, v)) if isinstance(v, list) else json.dumps(v)
            cell = ws.cell(i, j, num(v) if c in ("live sheet row", "row_id", "apply order") else v)
            cell.font = FONT
            cell.alignment = WRAP if c in wrap_cols else TOP
        if conf_col and fill_col:
            f = CONF_FILL.get(row.get(conf_col))
            if f:
                ws.cell(i, cols.index(fill_col) + 1).fill = f
        if link_col:
            cell = ws.cell(i, cols.index(link_col) + 1)
            u = str(cell.value or "")
            if u.startswith("http") and "\n" not in u and " " not in u and len(u) < 250:
                cell.hyperlink, cell.font = u, FONT_LINK
    for j, c in enumerate(cols, 1):
        ws.column_dimensions[get_column_letter(j)].width = (widths or {}).get(c, 16)
    ws.freeze_panes = ws.cell(r0 + 1, 1)
    if rows:
        ws.auto_filter.ref = f"A{r0}:{get_column_letter(len(cols))}{r0 + len(rows)}"
    return ws


def copy_wide(src_path, src_sheet, title, keep=None, add_live_row_from=None):
    """Copy a batch's wide review sheet with its confidence fills; prepend the live sheet row."""
    src = openpyxl.load_workbook(src_path)[src_sheet]
    ws = wb.create_sheet(title)
    hdr = [c.value for c in src[1]]
    rid_idx = hdr.index(add_live_row_from) if add_live_row_from in hdr else None
    out_r = 0
    for row in src.iter_rows():
        if row[0].row > 1 and keep and not keep(row):
            continue
        out_r += 1
        if out_r == 1:
            c0 = ws.cell(1, 1, "live sheet row")
            c0.font, c0.fill, c0.alignment = FONT_H, FILL_HEADER, WRAP
        else:
            rid = str(row[rid_idx].value) if rid_idx is not None else ""
            c0 = ws.cell(out_r, 1, BACKEND.get(rid, {}).get("live_row", "(new)"))
            c0.font = FONT
        for c in row:
            n = ws.cell(out_r, c.column + 1, c.value)
            n.font = FONT_H if out_r == 1 else FONT
            if c.fill and c.fill.fill_type:
                n.fill = copy(c.fill)
            n.alignment = WRAP if out_r == 1 else TOP
            if c.comment:
                n.comment = copy(c.comment)
    ws.column_dimensions["A"].width = 10
    for letter, dim in src.column_dimensions.items():
        idx = openpyxl.utils.column_index_from_string(letter) + 1
        ws.column_dimensions[get_column_letter(idx)].width = min(dim.width or 15, 40)
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{get_column_letter(src.max_column + 1)}{out_r}"
    return out_r - 1


# all_proposals
W = {"apply order": 7, "batch": 24, "kind": 9, "live sheet row": 9, "row_id": 8, "cluster": 9,
     "vessel name (backend)": 26, "IMO": 10, "status (backend)": 11, "shipbuilder": 24,
     "shipowner": 22, "column": 22, "current backend value": 22, "proposed value": 28,
     "source URL(s)": 45, "confidence": 10, "derivable": 9, "decision": 9, "gate verdict": 24,
     "note": 70}
table_sheet("all_proposals", PROP_COLS, proposals, W, wrap_cols=("note",),
            conf_col="confidence", fill_col="proposed value", link_col="source URL(s)")
NP = len(proposals) + 1

# all changes, backend-shaped: every proposal from all the proposal batches (accept AND hold) laid
# over the backend row it edits, in apply order, using apply_batch's own item model. Columns
# A:AT are the backend's columns in the backend's order; helper columns sit to the right so
# a row's A:AT can be pasted straight over the matching backend row.
be_header, be_rows, be_colmap = _load_backend(str(ROOT / "work" / "backend.csv"))
assert be_header == HDR, "backend_io header differs from the raw header row"
HIDX = {h: i for i, h in enumerate(be_header)}
yard_map = _yard_location_map_table_first(list(be_rows.values()), be_header)
merged, cell_meta, new_full = {}, {}, []      # row_id -> row | (row_id, col) -> meta | new rows
for order, bdir, label, *_ in BATCH_INFO:
    mode, payload = _detect(BATCHES / bdir)
    items, _conf = _items_and_conflicts(mode, payload, be_header, be_colmap)
    dec = {d["id"]: d["decision"] for d in read_csv(BATCHES / bdir / "decisions.csv")}
    for it in items:
        decision = dec.get(it["id"], "hold")
        if decision == "reject":
            continue
        meta = {"batch": label, "decision": decision, "confidence": it["confidence"],
                "note": it["note"]}
        if it["kind"] == "new_row":
            full, _rd = _discovery_full_row(it, be_header, yard_map)
            new_full.append((it["cluster_id"], full[:len(be_header)], meta))
            continue
        rid = it["row_id"]
        # a held proposal never displaces a cell an earlier batch accepted (it stays on all_proposals)
        if decision == "hold" and any(cell_meta.get((rid, c), {}).get("decision") == "accept"
                                      for c in (it.get("column"), it.get("ref_column")) if c):
            print("note: held proposal left off the backend shape, an accepted cell is already there:",
                  rid, it.get("column"), f"({label})")
            continue
        if rid not in merged:
            base = list(be_rows[rid])
            merged[rid] = base + [""] * (len(be_header) - len(base))
        row = merged[rid]

        def put(col, value, _row=row, _rid=rid, _meta=meta):
            if (_rid, col) in cell_meta:
                print("note: cell proposed by two batches, later apply order wins:", _rid, col)
            cell_meta[(_rid, col)] = {**_meta, "old": _row[HIDX[col]]}
            _row[HIDX[col]] = value

        if it["kind"] == "fill" and it["column"] in HIDX and not it.get("ref_only"):
            put(it["column"], it["value"])
        if it["ref_column"] and it["ref_value"] and it["ref_column"] in HIDX:
            put(it["ref_column"], it["ref_value"] if it.get("replace_ref")
                else _join_refs(row[HIDX[it["ref_column"]]], it["ref_value"].split(", ")))

# cross-check: every cell the batches' own apply.json accepted must be in the merged rows
for _o, bdir, *_ in BATCH_INFO:
    for c in load_json(BATCHES / bdir / "apply.json")["accepted_cells"]:
        got = merged[c["row_id"]][HIDX[c["column"]]]
        assert got == c["value"], (bdir, c["row_id"], c["column"], got, c["value"])

# rows the proposed-bucket review marks for deletion ride along unchanged, struck through
row_action = {}
for p in load_json(BATCHES / B3 / "proposed_review.json")["programmes"]:
    for a in p["row_actions"]:
        if "deletion" in a["action"]:
            rid = a["row_id"]  # row_id, not live row: live rows shift when the sheet is edited
            row_action[rid] = a["action"].replace("mark for deletion", "DELETE ROW")
            merged.setdefault(rid, list(be_rows[rid]) + [""] * (len(be_header) - len(be_rows[rid])))

HELPERS = ["live sheet row", "row action", "batches", "cells changed", "cells on hold",
           "columns on hold"]
ws = wb.create_sheet("all_changes_backend_shape")
for j, h in enumerate(be_header + HELPERS, 1):
    c = ws.cell(1, j, h)
    c.font, c.alignment = FONT_H, WRAP
    c.fill = FILL_HEADER if j <= len(be_header) else FILL_HELPER


def shape_cell(i, j, value, meta, struck=False):
    c = ws.cell(i, j, num(value))
    c.alignment = TOP
    c.font = FONT_DEL if struck else FONT
    if meta:
        ref_touched = be_header[j - 1].endswith("[ref]") and meta.get("old")
        c.fill = FILL_PEACH if ref_touched else CONF_FILL.get(meta["confidence"], CONF_FILL["R"])
        if meta["decision"] != "accept":
            c.font = FONT_HOLD
        text = f"{meta['batch']} | {meta['decision']} | {meta['confidence']}"
        if "old" in meta:
            text += f"\nwas: {meta['old'] or '(blank)'}"
        if meta["note"]:
            text += f"\n{meta['note']}"
        c.comment = Comment(text[:1500], "sep-17-pass", width=420, height=140)
    elif value not in ("", None):
        c.fill = FILL_GRAY


n_shape = {"rows": 0, "new": len(new_full), "cells": len(cell_meta), "hold": 0, "delete": len(row_action)}
i = 1
for rid in sorted(merged, key=lambda k: BACKEND[k]["live_row"]):
    i += 1
    metas = {col: m for (r_, col), m in cell_meta.items() if r_ == rid}
    for j, h in enumerate(be_header, 1):
        shape_cell(i, j, merged[rid][j - 1], metas.get(h), struck=rid in row_action)
    held = [h for h in be_header if h in metas and metas[h]["decision"] != "accept"]
    n_shape["rows"] += bool(metas)
    n_shape["hold"] += len(held)
    extra = [BACKEND[rid]["live_row"], row_action.get(rid, "edit existing row"),
             "; ".join(dict.fromkeys(m["batch"] for m in metas.values())), len(metas), len(held),
             ", ".join(held)]
    for j, v in enumerate(extra, len(be_header) + 1):
        ws.cell(i, j, v).font = FONT
for cid, full, meta in new_full:
    i += 1
    for j, v in enumerate(full, 1):
        shape_cell(i, j, v, {**meta, "note": ""} if v else None)
    filled = sum(1 for v in full if v)
    on_hold = meta["decision"] != "accept"
    n_shape["cells"] += filled
    n_shape["hold"] += filled if on_hold else 0
    extra = ["(new)", f"ADD NEW ROW (cluster {cid})", meta["batch"], filled, filled if on_hold else 0,
             "(whole row)" if on_hold else ""]
    for j, v in enumerate(extra, len(be_header) + 1):
        ws.cell(i, j, v).font = FONT
for j, h in enumerate(be_header + HELPERS, 1):
    ws.column_dimensions[get_column_letter(j)].width = \
        {"row action": 34, "batches": 40, "columns on hold": 50}.get(h, 30 if h.endswith("[ref]") else 16)
ws.freeze_panes = "E2"
ws.auto_filter.ref = f"A1:{get_column_letter(len(be_header) + len(HELPERS))}{i}"

# open decisions (from docs/plans/2026-09-17_sep-17-pass_summary.md)
DECISIONS = [
    ("Proposed bucket", "1204-1216; 1183; 1184-1200",
     "DONE 2026-09-17 (Baird, in the sheet): the three Woodside placeholders that duplicated the Seapeak on-order "
     "rows (now live 1162-1164) were deleted, their names moved to Other names; never-delete covers vessels leaving "
     "service, not duplicates. "
     "Other Woodside rows (1204-1216), Equinor 4 (1183) and the 17 Mozambique LNG slots (1184-1200) stay proposed; "
     "Mozambique confirmation deadline was pushed to Sep 2026, so re-check next month. Also the Mozambique "
     "owner/yard split flagged in the discovery batch.", "proposed_bucket"),
    ("Likely duplicates", "1083/1085; 1203/1086", "Hanwha Philly pairs flagged by the dedupe sweep and an agent.", ""),
    ("Vessel type / Cargo type rule", "10 Rule-F orphans",
     "'conventional' is a tracker classification, never page wording, so the hard gate cannot ref it. Decide: let a "
     "capacity-derived type stand on the Capacity ref, or leave unreffed.", "documented_blanks"),
    ("Price convention", "whole backend",
     "DECIDED 2026-09-17: Price is always full US dollars + USD. Batch 12 converts the 29 rows that carry 250 + $m. "
     "The 48 order-total Prices in batch 4 are accepted. Shipvault contract prices were not used (single-source, "
     "unverifiable).", "b12_price_usd_rows"),
    ("'Greenenergy ...' names", "", "Look wrong against both shipvault and AIS ('Greenergy').", ""),
    ("Manual-review rows", "54 + 24",
     "Mostly ships AIS-live while shipvault says on order; plus the sanctioned Zvezda / Arctic LNG 2 hulls "
     "(status untouched).", "manual_review"),
    ("Backend flags from discovery", "1165/1166; 1159",
     "BW LNG capacity (177,000), row 1159 price, COSCO hulls.", "flags_conflicts"),
    ("Possible mis-citations / value conflicts", "1179-1182 and others",
     "Found by the data-fill agents; full list in the data-fill batch notes.md.", "flags_conflicts"),
    ("MISC hulls H2019A-H2023A", "", "On shipvault with no citable press: next discovery run.", "shipvault_unmatched"),
    ("IGU 2026 intercomparison", "787, 790, 752 ...; 814, 797 ...; 929; 451, 499-501, 509",
     "DECIDED 2026-09-17: 'scrapped' is now a Status value and rows are never deleted, so all 18 rows IGU dropped "
     "(scrapped steam tonnage) move to 'scrapped' in batch 9 (on all_proposals), and row 61 Puteri Delima Satu "
     "moves to Vessel type FSU. Still open from the comparison: 13 active rows whose Delivery year should be 2026, "
     "7 active rows still on order, row 929 delivered, load corruption on rows 451 / 499-501 / 509, about 20 "
     "renames and one vessel to add. None of those is a proposal yet: each accepted item needs a verified ref and "
     "a follow-up fix batch.",
     "igu_findings"),
]
table_sheet("open_decisions", ["#", "decision", "live sheet rows", "detail", "see sheet"],
            [[i, *d] for i, d in enumerate(DECISIONS, 1)],
            {"#": 5, "decision": 32, "live sheet rows": 24, "detail": 100, "see sheet": 20},
            wrap_cols=("detail",))

# wide sheets, one per batch
n_wide = {}
n_wide[3] = copy_wide(BATCHES / B3 / "lng_carrier_candidate_vessels.xlsx", "candidate_vessels",
                      "b3_new_vessels", add_live_row_from="original order in sheet")
n_wide[1] = copy_wide(BATCHES / B1 / "lng_carrier_fix.xlsx", "fix", "b1_rollforward_rows",
                      add_live_row_from="original order in sheet")
n_wide[2] = copy_wide(BATCHES / B2 / "lng_carrier_fix.xlsx", "fix", "b2_confirmed_rows",
                      add_live_row_from="original order in sheet")
n_wide[4] = copy_wide(BATCHES / B4 / "lng_carrier_data_fill.xlsx", "backend_data_fill",
                      "b4_data_fill_rows", keep=lambda row: str(row[3].value) not in ("0", "None", ""),
                      add_live_row_from="row_id")
n_wide[5] = copy_wide(BATCHES / B5 / "lng_carrier_backend_ref_fill.xlsx", "backend_ref_fill",
                      "b5_ref_fill_rows", add_live_row_from="original order in sheet")
n_wide[6] = copy_wide(BATCHES / B6 / "lng_carrier_data_fill.xlsx", "backend_data_fill",
                      "b6_shipvault_companions", add_live_row_from="row_id")
n_wide[8] = copy_wide(BATCHES / B8 / "lng_carrier_fix.xlsx", "fix", "b8_igu_sourced_rows",
                      add_live_row_from="original order in sheet")
n_wide[9] = copy_wide(BATCHES / B9 / "lng_carrier_fix.xlsx", "fix", "b9_scrapped_rows",
                      add_live_row_from="original order in sheet")
n_wide[10] = copy_wide(BATCHES / B10 / "lng_carrier_fix.xlsx", "fix", "b10_former_names_rows",
                       add_live_row_from="original order in sheet")
n_wide[11] = copy_wide(BATCHES / B11 / "lng_carrier_fix.xlsx", "fix", "b11_qcmax_rows",
                       add_live_row_from="original order in sheet")
n_wide[12] = copy_wide(BATCHES / B12 / "lng_carrier_fix.xlsx", "fix", "b12_price_usd_rows",
                       add_live_row_from="original order in sheet")

# flags + conflicts
flags = []
for f in load_json(BATCHES / B3 / "candidates.json")["backend_status_flags"]:
    flags.append({"batch": "discovery since Jun 2026", "live sheet rows": f.get("rows", ""),
                  "row_id": "", "column / flag": f.get("flag", ""), "backend value": "",
                  "proposed value": "", "sources": "", "detail": f.get("note", ""), "decision": ""})
for c in read_csv(BATCHES / B4 / "conflicts.csv"):
    ids = [x for x in c["row_id"].split("/") if x]
    live = "/".join(str(BACKEND.get(x, {}).get("live_row", "?")) for x in ids)
    flags.append({"batch": "data fill (on-order rows)", "live sheet rows": live, "row_id": c["row_id"],
                  "column / flag": c["column"], "backend value": c["backend_value"],
                  "proposed value": c["proposed_value"], "sources": c["sources"],
                  "detail": c["recommendation"], "decision": c["decision"]})
FC = ["batch", "live sheet rows", "row_id", "column / flag", "backend value", "proposed value",
      "sources", "detail", "decision"]
table_sheet("flags_conflicts", FC, flags,
            {"batch": 24, "live sheet rows": 16, "row_id": 16, "column / flag": 28, "backend value": 22,
             "proposed value": 22, "sources": 40, "detail": 100, "decision": 9}, wrap_cols=("detail",))

# manual review
manual = []
confirmed = {m["row_id"]: m for m in load_json(BATCHES / B2 / "manual_review.json")}
for m in load_json(BATCHES / B1 / "manual_review.json"):
    c = confirmed.get(m["row_id"], {})
    b = BACKEND.get(str(m["row_id"]), {})
    manual.append({"live sheet row": b.get("live_row", m["live_row"]), "row_id": m["row_id"], "IMO": m["imo"],
                   "vessel name (backend)": b.get("Name", ""), "shipbuilder": b.get("Shipbuilder", ""),
                   "why flagged (roll-forward)": m["why"],
                   "press follow-up verdict": c.get("verdict", "(not followed up)"),
                   "name found": c.get("name", ""), "follow-up note": c.get("note", "")})
for rid, c in confirmed.items():
    if rid not in {m["row_id"] for m in manual}:
        b = BACKEND.get(str(rid), {})
        manual.append({"live sheet row": b.get("live_row", c["live_row"]), "row_id": rid, "IMO": c["imo"],
                       "vessel name (backend)": b.get("Name", ""), "shipbuilder": b.get("Shipbuilder", ""),
                       "why flagged (roll-forward)": "", "press follow-up verdict": c.get("verdict", ""),
                       "name found": c.get("name", ""), "follow-up note": c.get("note", "")})
MC = ["live sheet row", "row_id", "IMO", "vessel name (backend)", "shipbuilder",
      "why flagged (roll-forward)", "press follow-up verdict", "name found", "follow-up note"]
table_sheet("manual_review", MC, manual,
            {"live sheet row": 9, "row_id": 8, "IMO": 10, "vessel name (backend)": 26, "shipbuilder": 24,
             "why flagged (roll-forward)": 60, "press follow-up verdict": 20, "name found": 20,
             "follow-up note": 100}, wrap_cols=("why flagged (roll-forward)", "follow-up note"))

# batch 8's own manual list: IGU values it would not turn into a proposal (vocabulary / stylization picks)
igu_manual = []
for m in load_json(BATCHES / B8 / "manual_review.json"):
    b = BACKEND.get(str(m["row_id"]), {})
    igu_manual.append({"live sheet row": b.get("live_row", m["live_row"]), "row_id": m["row_id"],
                       "vessel name (backend)": b.get("Name", m.get("name", "")), "column": m["field"],
                       "backend value": m.get("backend", b.get(m["field"], "")), "IGU 2026": m.get("igu", ""),
                       "IGU 2025": m.get("igu_prev", ""), "why not proposed": m["why"]})
igu_manual.sort(key=lambda r: int(r["live sheet row"]))
IMC = ["live sheet row", "row_id", "vessel name (backend)", "column", "backend value", "IGU 2026", "IGU 2025",
       "why not proposed"]
table_sheet("b8_igu_manual_review", IMC, igu_manual,
            {"live sheet row": 9, "row_id": 8, "vessel name (backend)": 26, "column": 18, "backend value": 28,
             "IGU 2026": 28, "IGU 2025": 28, "why not proposed": 100}, wrap_cols=("why not proposed",))

# proposed bucket
pr = load_json(BATCHES / B3 / "proposed_review.json")
prow = []
for p in pr["programmes"]:
    ev = "\n".join(f"{e.get('date', '')}: {e.get('url', '')}" for e in p.get("evidence", []))
    for a in p["row_actions"]:
        b = BACKEND.get(a["row_id"], {})  # a row deleted from the sheet since the review has no live row
        prow.append({"programme": p["programme"], "programme verdict": p["verdict"],
                     "live sheet row": b.get("live_row", "(deleted)"),
                     "vessel name (backend)": b.get("Name", a.get("name", "")),
                     "action": a["action"], "note": a.get("note", ""), "programme evidence": ev})
table_sheet("proposed_bucket",
            ["programme", "programme verdict", "live sheet row", "vessel name (backend)", "action", "note",
             "programme evidence"], prow,
            {"programme": 18, "programme verdict": 18, "live sheet row": 9, "vessel name (backend)": 28,
             "action": 34, "note": 90, "programme evidence": 60}, wrap_cols=("note", "programme evidence"))

# shipvault orderbook entries with no backend match
sv = load_json(BATCHES / B3 / "shipvault_orderbook_unmatched.json")
SVC = ["name", "imo", "status", "owner", "yard", "yardno", "gt", "built", "month", "ordered", "url"]
table_sheet("shipvault_unmatched", SVC, sv, {"name": 24, "owner": 24, "yard": 36, "url": 42},
            link_col="url",
            intro="shipvault on-order LNG units with no backend match and no citable press yet "
                  "(single-source: leads for the next discovery run, not candidates)")

# IGU 2026 intercomparison (comparison only; leads, not proposals)
igu = load_json(BATCHES / B7 / "igu_reconcile.json")
IGU_LABEL = {"name": "Name", "shipowner": "Shipowner", "shipbuilder": "Shipbuilder", "capacity": "Capacity",
             "cargo_type": "Cargo type", "vessel_type": "Vessel type", "propulsion": "Propulsion type",
             "delivery_year": "Delivery year"}


def _igu_lead(imo):
    ld = igu.get("leads", {}).get(str(imo)) or {}
    bits = [ld.get("name"), ld.get("status"),
            f"fate {ld['fate_date']}" if ld.get("fate_date") else "",
            f"delivered {ld['delivered']}" if ld.get("delivered") else ""]
    return " | ".join(b for b in bits if b), ld.get("url", "")


def _igu_pending(item):
    pend = item.get("pending") or []
    if isinstance(pend, dict):  # dropped rows: {field: [proposals]}
        pend = [dict(p, value=f"{f} -> {p['value']}") for f, ps in pend.items() for p in ps]
    return "; ".join(f"{p['batch'].split('ET_', 1)[-1]}: {p['value']} ({p['decision']})" for p in pend)


def _igu_row(be, finding, field, bval, ival, prev, kind, item, note=""):
    lead, url = _igu_lead(be.get("imo"))
    return {"finding": finding, "live sheet row": be.get("sheet_row", ""), "row_id": be.get("row_id", ""),
            "IMO": be.get("imo", ""), "vessel name (backend)": be.get("name", ""), "field": field,
            "backend value": bval, "IGU 2026": ival, "IGU 2025": prev, "kind": kind,
            "already in a pending batch": _igu_pending(item),
            "pending agrees": "yes" if item.get("pending_agrees") else "",
            "shipvault lead (not a ref)": lead, "note": note, "lead url": url}


igu_rows = []
# batch 9 was built from this comparison, so igu_reconcile.json (written before it) cannot know it
b9_status = {p["row_id"]: p for p in proposals if p["apply order"] == 9 and p["column"] == "Status"}
for x in igu["dropped"]:
    row = _igu_row(x["backend"], "dropped from IGU", "Status", x["backend"]["status"], "not listed",
                   "in the fleet table", "", x, "scrapped; the row stays (rows are never deleted)")
    p9 = b9_status.get(str(x["backend"].get("row_id")))
    if p9:
        row["already in a pending batch"] = f"fix_scrapped_status: Status -> {p9['proposed value']} ({p9['decision']})"
        row["pending agrees"] = "yes"
    igu_rows.append(row)
for x in igu["matched"]:
    sf = x.get("status_finding")
    if sf:
        igu_rows.append(_igu_row(x["backend"], sf["finding"], "Status", sf["backend"], sf["igu"], "", "", sf,
                                 "backend Delivery year is at or before the IGU cut-off year"
                                 if sf.get("delivery_year_conflict") else ""))
# same for batch 8 (what IGU prints, as proposals): mark the diffs it already covers
b8_cell = {(p["row_id"], p["column"]): p for p in proposals if p["apply order"] == 8}
for x in igu["matched"]:
    for df in x["diffs"]:
        label = IGU_LABEL.get(df["field"], df["field"])
        row = _igu_row(x["backend"], "field diff", label,
                       df["backend"], df["igu"], df.get("igu_prev", ""), df["kind"], df)
        p8 = b8_cell.get((str(x["backend"].get("row_id")), label))
        if p8:
            mine = f"fix_igu2026_sourced: {p8['proposed value']} ({p8['decision']})"
            row["already in a pending batch"] = "; ".join(b for b in (row["already in a pending batch"], mine) if b)
        igu_rows.append(row)
for x in igu["igu_only"]:
    g = x["igu"]
    lead, url = _igu_lead(g["imo"])
    igu_rows.append({"finding": "in IGU, not in the backend", "IMO": g["imo"], "vessel name (backend)": "",
                     "field": "(whole vessel)", "IGU 2026": f"{g['name']} | {g['shipowner']} | {g['shipbuilder']} | "
                     f"{g['capacity']} cbm | {g['vessel_type']} | {g['delivery_year']}",
                     "shipvault lead (not a ref)": lead, "lead url": url,
                     "note": x.get("reason") or "candidate to add (next discovery batch)"})
IGC = ["finding", "live sheet row", "row_id", "IMO", "vessel name (backend)", "field", "backend value", "IGU 2026",
       "IGU 2025", "kind", "already in a pending batch", "pending agrees", "shipvault lead (not a ref)", "note",
       "lead url"]
table_sheet("igu_findings", IGC, igu_rows,
            {"finding": 24, "live sheet row": 9, "row_id": 8, "IMO": 10, "vessel name (backend)": 28, "field": 16,
             "backend value": 24, "IGU 2026": 30, "IGU 2025": 22, "kind": 16, "already in a pending batch": 40,
             "pending agrees": 9, "shipvault lead (not a ref)": 44, "note": 44, "lead url": 38},
            wrap_cols=("already in a pending batch", "note"), link_col="lead url",
            intro="Backend vs the IGU World LNG Report 2026 (fleet at end-2025), IMO-keyed, with the 2025 edition as "
                  "the baseline. Comparison only: nothing here is a proposal, and the shipvault column is a lead, "
                  "never a ref. kind: igu_changed = IGU moved since 2025 (review); backend_differs = the backend "
                  "was edited since the load (do not revert blindly). Full workbook: batches/" + B7)

# documented blanks + Rule-F negatives
qa4 = qa_sections(BATCHES / B4 / "lng_carrier_data_fill.xlsx")
blanks = []
for n in load_json(BATCHES / B5 / "unfilled_negative_results.json"):
    b = BACKEND.get(str(n["row_id"]), {})
    blanks.append({"batch": "Rule-F ref fill", "live sheet row": b.get("live_row", n["live_row"]),
                   "row_id": n["row_id"], "vessel name (backend)": b.get("Name", ""), "field": n["field"],
                   "backend value": n.get("value", ""),
                   "note": "value present, no citable ref found that states it (negative result)"})
for q in qa4["Documented blanks (researched, not found)"]:
    b = BACKEND.get(str(q["row_id"]), {})
    blanks.append({"batch": "data fill (on-order rows)", "live sheet row": b.get("live_row", ""),
                   "row_id": q["row_id"], "vessel name (backend)": b.get("Name", ""), "field": q["field"],
                   "backend value": b.get(q["field"], ""), "note": q.get("note") or ""})
table_sheet("documented_blanks",
            ["batch", "live sheet row", "row_id", "vessel name (backend)", "field", "backend value", "note"],
            blanks, {"batch": 24, "live sheet row": 9, "row_id": 8, "vessel name (backend)": 28, "field": 24,
                     "backend value": 18, "note": 110}, wrap_cols=("note",))

# URL verification logs
ulog = []
for v in load_json(BATCHES / B3 / "candidates.json")["verification_log"]:
    ulog.append({"batch": "discovery since Jun 2026", "url": v["url"], "result": v.get("status", ""),
                 "checked for": v.get("checked_for", ""), "note": v.get("note", "")})
for v in pr["verification_log"]:
    ulog.append({"batch": "discovery (proposed bucket)", "url": v["url"], "result": v.get("status", ""),
                 "checked for": v.get("checked_for", ""), "note": v.get("note", "")})
for v in qa4["URL verification log"]:
    ulog.append({"batch": "data fill (on-order rows)", "url": v["url"],
                 "result": v.get("result") or v.get("status") or "", "checked for": "",
                 "note": " ".join(str(v.get(k)) for k in ("soft_error", "content_match") if v.get(k))})
for q in qa_sections(BATCHES / B5 / "lng_carrier_backend_ref_fill.xlsx")["Per-cell citation log"]:
    ulog.append({"batch": "Rule-F ref fill", "url": q["url"],
                 "result": "PASS" if ": OK" in str(q["note"]) else "FAIL",
                 "checked for": f"row_id {q['row_id']} {q['field']}", "note": q["note"]})
table_sheet("url_verification", ["batch", "url", "result", "checked for", "note"], ulog,
            {"batch": 26, "url": 70, "result": 10, "checked for": 34, "note": 80}, link_col="url")

# ---- README (first sheet) ---------------------------------------------------
ws = wb["Sheet"]
ws.title = "README"
wb.move_sheet("README", -(len(wb.sheetnames) - 1))
r = 1
ws.cell(r, 1, "LNG carrier tracker: sep-17-pass research update, 2026-09-17 (all results)").font = FONT_T
r += 2
for line in [
    "Backend pulled 2026-09-17 ~01:15 ET: 1,220 rows (822 active / 364 on order / 34 proposed). Re-pulled "
    "10:15 ET: unchanged, so none of this has been applied yet.",
    "Nothing here has been written to the Google Sheet. Every line is a candidate for human review. Each batch "
    "folder under batches/2026-09-17_* carries the apply artifacts (decisions.csv, apply_rows.csv, apply_patch.csv).",
    "Row numbers are LIVE SHEET ROWS on the backend tab as of the 10:15 ET pull; row_id is column A "
    "('original order in sheet'), which is what the apply artifacts key on.",
]:
    ws.cell(r, 1, line).font = FONT
    r += 1
r += 1
ws.cell(r, 1, "Batches, in the order to apply them").font = FONT_B
r += 1
heads = ["apply order", "batch", "what", "proposals", "accept (default)", "hold (needs a look)",
         "green (high)", "yellow (medium)", "rows in wide sheet", "wide sheet", "batch folder"]
for j, h in enumerate(heads, 1):
    c = ws.cell(r, j, h)
    c.font, c.fill, c.alignment = FONT_H, FILL_HEADER, WRAP
first = r + 1
wide_name = {1: "b1_rollforward_rows", 2: "b2_confirmed_rows", 3: "b3_new_vessels",
             4: "b4_data_fill_rows", 5: "b5_ref_fill_rows", 6: "b6_shipvault_companions",
             8: "b8_igu_sourced_rows", 9: "b9_scrapped_rows",
             10: "b10_former_names_rows", 11: "b11_qcmax_rows", 12: "b12_price_usd_rows"}
for order, bdir, label, _w, _s, what in BATCH_INFO:
    r += 1
    mine = [p for p in proposals if p["apply order"] == order]
    vals = [order, label, what, len(mine),
            sum(p["decision"] == "accept" for p in mine), sum(p["decision"] == "hold" for p in mine),
            sum(p["confidence"] == "G" for p in mine), sum(p["confidence"] == "Y" for p in mine),
            n_wide[order], wide_name[order], bdir]
    for j, v in enumerate(vals, 1):
        c = ws.cell(r, j, v)
        c.font, c.alignment = FONT, WRAP
r += 1
ws.cell(r, 2, "total").font = FONT_B
for j in range(4, 9):
    L = get_column_letter(j)
    ws.cell(r, j, sum(ws.cell(k, j).value for k in range(first, r))).font = FONT_B
r += 1
ws.cell(r, 1, "Counts are of the lines on all_proposals (default decisions, before any review edits). Apply 1-2 before 4 (they rename rows 4 also touches; "
              "artifacts are keyed by row_id, so order is about readability, not safety). There is no apply order 7: "
              "batch 7 is the IGU comparison (igu_findings), which is never applied. Batches 8 and 9 both touch row 61 "
              "Vessel type: 9 (FSU, sourced) supersedes 8's held 'conventional' ref. Batch 10 rides on the Name lines of "
              "1, 2 and 8: accept, hold or reject each Other names line together with its Name line.").font = FONT
r += 2
ws.cell(r, 1, "Sheets").font = FONT_B
for name, desc in [
    ("open_decisions", f"the {len(DECISIONS)} judgment calls waiting on a human"),
    ("all_proposals", "EVERY proposed change from all nine proposal batches, one line per cell (or per new vessel): current "
                      "backend value, proposed value, source URL, confidence, default decision, note. Filter here first."),
    ("all_changes_backend_shape",
     f"ALL of the above merged into the backend's own structure: columns A:AT are the backend columns in backend "
     f"order, one full row per vessel, sorted by live sheet row ({n_shape['rows']} edited rows, {n_shape['new']} new "
     f"rows at the bottom, {n_shape['delete']} rows marked for deletion and struck through; {n_shape['cells']} "
     f"changed cells, {n_shape['hold']} of them on hold). Accepts AND holds are laid in: a changed cell is filled "
     "by confidence (peach where an existing [ref] was rewritten or appended to), a hold is in italics, and each "
     "changed cell's comment gives batch, decision, the old value and the note. Helper columns AU:AZ (live sheet "
     "row, row action, holds) sit to the right so A:AT pastes straight over the backend row. flags_conflicts are "
     "not laid in (never auto-applied)."),
    ("b3_new_vessels", "discovery: 12 new vessels in 5 clusters, full backend-shaped rows"),
    ("b1_rollforward_rows / b2_confirmed_rows / b8_igu_sourced_rows / b9_scrapped_rows / b10_former_names_rows / "
     "b11_qcmax_rows / b12_price_usd_rows",
     "fix batches: full corrected backend rows (paste-ready shape)"),
    ("b4_data_fill_rows", "data fill: the 477 backend rows that received at least one proposal (the other 743 "
                          "in-scope rows were unchanged and are left out)"),
    ("b5_ref_fill_rows", "Rule-F: rows with a proposed [ref] for an already-filled value"),
    ("flags_conflicts", "places research disagrees with a non-blank backend value, or flags a backend problem; "
                        "never auto-applied"),
    ("manual_review", "on-order rows the roll-forward could not settle, with the press follow-up verdict"),
    ("b8_igu_manual_review", "IGU 2026 values batch 8 left to a human: vocabulary and name-stylization picks"),
    ("proposed_bucket", "row-by-row review of the 34 'proposed' rows (Mozambique LNG, Woodside, Equinor)"),
    ("shipvault_unmatched", "shipvault orderbook units with no backend match and no citable press"),
    ("igu_findings", "seventh batch, comparison only: the backend against the IGU World LNG Report 2026 - rows IGU "
                     "dropped (scrapped; now proposed as Status scrapped by batch 9), Status disagreements, field diffs, one "
                     "vessel to add. Leads, not proposals"),
    ("documented_blanks", "cells researched and NOT filled, with why (so nobody repeats the search)"),
    ("url_verification", "the verification-gate log for every URL considered"),
]:
    r += 1
    ws.cell(r, 1, name).font = FONT_B
    ws.cell(r, 3, desc).font = FONT
r += 2
ws.cell(r, 1, "Color key (same in every workbook the tracker tooling builds)").font = FONT_B
for fill, text in [
    ("C6EFCE", "Green: proposed value, HIGH confidence (2+ independent sources, or one primary/regulatory source "
               "carrying the value verbatim)"),
    ("FFEB9C", "Yellow: proposed value, MEDIUM confidence (entity-level corroboration; some detail implied or contested)"),
    ("FFC7CE", "Red: proposed value, LOW confidence; review before accepting"),
    ("FFD9B3", "Peach: the cell's existing backend [ref] is involved (preserved-and-appended in data fill; "
               "rewritten in ref fill / fix); compare before pasting"),
    ("EEEEEE", "Gray: pre-existing backend value, untouched (context only)"),
]:
    r += 1
    ws.cell(r, 1, "").fill = PatternFill("solid", fgColor=fill)
    ws.cell(r, 3, text).font = FONT
r += 2
ws.cell(r, 1, "Caveats").font = FONT_B
for line in [
    "Every cited URL passed the value-to-ref corroboration gate (the live page contains the cell's value). "
    "shipvault is treated as single-source (yellow) and never used for owners: it had IMO typos and wrong owner tags.",
    "Coverage is thinner than a normal run: the web-search budget ran out mid-way, vesselfinder blocked our IP "
    "part-way (cited nowhere; all 176 IMOs it missed were re-checked on marinetraffic.org), and TradeWinds/Upstream paywalls block many contract dates and prices.",
    "Data-fill research covered on-order rows only; blanks on active rows were not researched. The citation "
    "rot-sweep (fixing existing dead refs) is paused and not part of this file.",
]:
    r += 1
    ws.cell(r, 1, line).font = FONT
for L, w in zip("ABCDEFGHIJK", [12, 28, 60, 11, 11, 12, 11, 11, 11, 22, 48]):
    ws.column_dimensions[L].width = w

wb.save(OUT)
for old in HERE.glob(f"{OUT_STEM}*.xlsx"):  # one current workbook per dir; git keeps the rest
    if old != OUT:
        old.unlink()
print("wrote", OUT, "| proposals:", len(proposals), "| sheets:", wb.sheetnames)

# ---- data for the report page ----------------------------------------------
report = {"igu_findings": len(igu_rows), "proposals": proposals, "flags": flags, "manual": manual, "proposed_bucket": prow,
          "n_wide": n_wide, "blanks": len(blanks), "urls": len(ulog), "backend_shape": n_shape}
(HERE / "report_data.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
