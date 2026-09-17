"""Combine the six sep-17-pass (2026-09-17) batches into one review workbook.

Read-only over the batch dirs and work/backend.csv; writes
lng_carrier_sep-17-pass_results.xlsx + report_data.json next to this file.
Run from the repo root: python batches/2026-09-17_1017ET_sep-17-pass_combined/build_combined.py
"""
import csv
import json
import sys
from collections import defaultdict
from copy import copy
from pathlib import Path

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
OUT = HERE / "lng_carrier_sep-17-pass_results.xlsx"

B1 = "2026-09-17_0421ET_fix_delivery_rollforward"
B2 = "2026-09-17_0458ET_fix_delivery_confirmed"
B3 = "2026-09-17_0431ET_discovery_since_jun_2026"
B4 = "2026-09-17_0511ET_data_fill_on_order"
B5 = "2026-09-17_0505ET_ref_fill_rule_f"
B6 = "2026-09-17_1114ET_shipvault_companion_refs"
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
    if bdir in (B1, B2):
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

# all changes, backend-shaped: every proposal from all six batches (accept AND hold) laid
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
            rid = next(k for k, v in BACKEND.items() if str(v["live_row"]) == str(a["live_row"]))
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
    ("Proposed bucket", "1204-1206; 1186; 1187-1203",
     "Woodside placeholders on live rows 1204-1206 duplicate the Seapeak on-order rows 1165-1167: delete. "
     "Other Woodside rows, Equinor 4 (1186) and the 17 Mozambique LNG slots (1187-1203) stay proposed; "
     "Mozambique confirmation deadline was pushed to Sep 2026, so re-check next month. Also the Mozambique "
     "owner/yard split flagged in the discovery batch.", "proposed_bucket"),
    ("Likely duplicates", "1083/1085; 1132/1086", "Hanwha Philly pairs flagged by the dedupe sweep and an agent.", ""),
    ("Vessel type / Cargo type rule", "10 Rule-F orphans",
     "'conventional' is a tracker classification, never page wording, so the hard gate cannot ref it. Decide: let a "
     "capacity-derived type stand on the Capacity ref, or leave unreffed.", "documented_blanks"),
    ("Price convention", "whole backend",
     "Backend mixes 250 + $m with 250000000 + USD. New fills use full USD. Shipvault contract prices were not used "
     "(single-source, unverifiable).", ""),
    ("'Greenenergy ...' names", "", "Look wrong against both shipvault and AIS ('Greenergy').", ""),
    ("Manual-review rows", "52 + 24",
     "Mostly ships AIS-live while shipvault says on order; plus the sanctioned Zvezda / Arctic LNG 2 hulls "
     "(status untouched).", "manual_review"),
    ("Backend flags from discovery", "1168/1169; 1162",
     "BW LNG capacity (177,000), row 1162 price, COSCO hulls.", "flags_conflicts"),
    ("Possible mis-citations / value conflicts", "1182-1185 and others",
     "Found by the data-fill agents; full list in the data-fill batch notes.md.", "flags_conflicts"),
    ("MISC hulls H2019A-H2023A", "", "On shipvault with no citable press: next discovery run.", "shipvault_unmatched"),
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

# proposed bucket
pr = load_json(BATCHES / B3 / "proposed_review.json")
prow = []
for p in pr["programmes"]:
    ev = "\n".join(f"{e.get('date', '')}: {e.get('url', '')}" for e in p.get("evidence", []))
    for a in p["row_actions"]:
        b = next((v for v in BACKEND.values() if str(v["live_row"]) == str(a["live_row"])), {})
        prow.append({"programme": p["programme"], "programme verdict": p["verdict"],
                     "live sheet row": a["live_row"], "vessel name (backend)": b.get("Name", ""),
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
             4: "b4_data_fill_rows", 5: "b5_ref_fill_rows", 6: "b6_shipvault_companions"}
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
              "artifacts are keyed by row_id, so order is about readability, not safety).").font = FONT
r += 2
ws.cell(r, 1, "Sheets").font = FONT_B
for name, desc in [
    ("open_decisions", "the nine judgment calls waiting on a human"),
    ("all_proposals", "EVERY proposed change from all six batches, one line per cell (or per new vessel): current "
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
    ("b1_rollforward_rows / b2_confirmed_rows", "fix batches: full corrected backend rows (paste-ready shape)"),
    ("b4_data_fill_rows", "data fill: the 477 backend rows that received at least one proposal (the other 743 "
                          "in-scope rows were unchanged and are left out)"),
    ("b5_ref_fill_rows", "Rule-F: rows with a proposed [ref] for an already-filled value"),
    ("flags_conflicts", "places research disagrees with a non-blank backend value, or flags a backend problem; "
                        "never auto-applied"),
    ("manual_review", "on-order rows the roll-forward could not settle, with the press follow-up verdict"),
    ("proposed_bucket", "row-by-row review of the 34 'proposed' rows (Mozambique LNG, Woodside, Equinor)"),
    ("shipvault_unmatched", "shipvault orderbook units with no backend match and no citable press"),
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
    "part-way (cited nowhere; 95 of the 176 IMOs it missed were re-checked on marinetraffic.org), and TradeWinds/Upstream paywalls block many contract dates and prices.",
    "Data-fill research covered on-order rows only; blanks on active rows were not researched. The citation "
    "rot-sweep (fixing existing dead refs) is paused and not part of this file.",
]:
    r += 1
    ws.cell(r, 1, line).font = FONT
for L, w in zip("ABCDEFGHIJK", [12, 28, 60, 11, 11, 12, 11, 11, 11, 22, 48]):
    ws.column_dimensions[L].width = w

wb.save(OUT)
print("wrote", OUT, "| proposals:", len(proposals), "| sheets:", wb.sheetnames)

# ---- data for the report page ----------------------------------------------
report = {"proposals": proposals, "flags": flags, "manual": manual, "proposed_bucket": prow,
          "n_wide": n_wide, "blanks": len(blanks), "urls": len(ulog), "backend_shape": n_shape}
(HERE / "report_data.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
