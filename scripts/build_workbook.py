"""
Build the rolling output xlsx for either [ref]-fill or discovery workflows.

Per [ref]-Fill SOP §2 and Discovery SOP §5, output structure:

  ref_fill mode -> <out>/lng_carrier_backend_ref_fill.xlsx
    Sheets: README, backend_ref_fill, QA_review

  discovery mode -> <out>/lng_carrier_candidate_vessels.xlsx
    Sheets: README, candidate_vessels, QA_review, backend_status_flags

The --out argument is the DIRECTORY the xlsx is written into; the filename is
fixed by mode. Normally this is the batch directory under batches/, e.g.
batches/2026-05-27_ref_fill_rows_1148-1167/.

Color conventions ([ref]-Fill SOP §2.2 / Discovery SOP §5.2):
  Green   = high confidence (multi-source or primary/regulatory + value verbatim)
  Yellow  = medium confidence (entity-level or contested)
  Red     = low confidence / review needed
  Peach   = override of pre-existing backend value (ref_fill only)
  Gray    = pre-existing backend value, untouched (ref_fill only)
  (No fill) = blank cell — see QA_review for why

This script provides scaffolding only — the citation/candidate data must be
supplied via a JSON input. The JSON schema is documented in the docstrings
below.

Usage:
    python build_workbook.py --mode ref_fill --rows 1170-1190 \\
        --citations citations.json \\
        --out ../batches/2026-05-27_ref_fill_rows_1170-1190/
    python build_workbook.py --mode discovery \\
        --candidates candidates.json \\
        --out ../batches/2026-05-27_discovery/

citations.json schema (ref_fill mode):
    {
      "batch_label": "Batch 3 — rows 1170-1190",
      "cells": [
        {
          "row_id": "1170",
          "field": "hull_ref",       # canonical column key from colmap
          "url": "https://...",
          "confidence": "G",          # G/Y/R/peach
          "note": "CSB Samsung yard page contains 'Samsung 2783'"
        },
        ...
      ],
      "qa_log": [
        {"row_id":"1170", "field":"hull_ref", "action":"filled", "confidence":"G",
         "url":"https://...", "note":"..."},
        ...
      ],
      "data_conflicts": [...],          # optional
      "candidate_data_fills": [...],    # optional, paired data + ref proposals
      "defects_corrected": [...],       # optional
      "verification_log": [...]         # optional
    }

candidates.json schema (discovery mode):
    {
      "gap_window": "2026-01-01 onward",
      "yards_swept": [...],
      "candidates": [
        {
          "cluster_id": "C1",
          "cluster_label": "MISC FSRU at Samsung HI",
          "confidence": "G",
          "discovery_notes": "...",
          "row_data": {            # cells keyed by canonical column name
            "shipowner": "MISC Berhad",
            "shipowner_ref": "https://...",
            "shipbuilder": "Samsung Heavy Industries",
            ...
          }
        },
        ...
      ],
      "backend_status_flags": [...],
      "verification_log": [...],
      "methodology_audit": {...}
    }
"""
import argparse
import csv
import json
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from paths import backend_csv_path


# Color conventions
FILL_GREEN = PatternFill("solid", fgColor="C6EFCE")    # high confidence
FILL_YELLOW = PatternFill("solid", fgColor="FFEB9C")   # medium
FILL_RED = PatternFill("solid", fgColor="FFC7CE")      # low
FILL_PEACH = PatternFill("solid", fgColor="FFD9B3")    # override
FILL_GRAY = PatternFill("solid", fgColor="EEEEEE")     # pre-existing
FILL_HEADER = PatternFill("solid", fgColor="1F4E78")   # header background

CONFIDENCE_FILLS = {
    "G": FILL_GREEN, "green": FILL_GREEN,
    "Y": FILL_YELLOW, "yellow": FILL_YELLOW,
    "R": FILL_RED, "red": FILL_RED,
    "peach": FILL_PEACH, "P": FILL_PEACH,
}

HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
HEADER_ALIGN = Alignment(horizontal="left", vertical="center", wrap_text=True)
WRAP_ALIGN = Alignment(horizontal="left", vertical="top", wrap_text=True)
THIN_BORDER = Border(
    left=Side(style="thin", color="CCCCCC"),
    right=Side(style="thin", color="CCCCCC"),
    top=Side(style="thin", color="CCCCCC"),
    bottom=Side(style="thin", color="CCCCCC"),
)


def _apply_header_style(ws, row_idx: int = 1):
    """Apply header styling to a row."""
    for cell in ws[row_idx]:
        cell.font = HEADER_FONT
        cell.fill = FILL_HEADER
        cell.alignment = HEADER_ALIGN
        cell.border = THIN_BORDER


def _resolve_out_path(out_arg: str | None, default_filename: str) -> Path:
    """
    Resolve --out to a concrete file path.

    Semantics:
      - If --out ends in .xlsx, treat it as a file path (backward compat).
      - If --out is a directory (existing or not), append default_filename.
      - If --out is None, default to <repo_root>/batches/_latest/<default_filename>
        and warn — the canonical pattern is to pass an explicit batch directory.
    """
    if out_arg is None:
        from paths import repo_root
        default = repo_root() / "batches" / "_latest" / default_filename
        print(f"  [warn] --out not specified; defaulting to {default}. "
              f"Pass --out <batches/...> for proper batch tracking.",
              file=sys.stderr)
        return default
    p = Path(out_arg)
    if p.suffix.lower() == ".xlsx":
        return p
    return p / default_filename


def _set_widths(ws, widths: dict):
    """widths: {column_letter: width}"""
    for col, w in widths.items():
        ws.column_dimensions[col].width = w


def build_readme(wb: Workbook, title: str, body_lines: list[str]):
    ws = wb.active
    ws.title = "README"
    ws["A1"] = title
    ws["A1"].font = Font(name="Calibri", size=14, bold=True)
    for i, line in enumerate(body_lines, start=3):
        ws.cell(row=i, column=1, value=line).alignment = WRAP_ALIGN
    ws.column_dimensions["A"].width = 120


def build_ref_fill(args):
    """Build the [ref]-fill mode workbook."""
    citations_path = Path(args.citations)
    citations = json.loads(citations_path.read_text())

    # Load backend
    with open(args.backend, encoding="utf-8") as f:
        backend_rows = list(csv.reader(f))
    colmap = json.loads(Path(args.backend).with_suffix(".colmap.json").read_text())
    header = backend_rows[colmap["_header_row_idx"]]
    data_start = colmap["_data_starts_at"]
    data = backend_rows[data_start:]

    # Parse row range
    if args.rows:
        lo, hi = args.rows.split("-")
        lo, hi = int(lo), int(hi)
    else:
        # Infer from citations
        row_ids = [int(c["row_id"]) for c in citations.get("cells", [])
                   if c["row_id"].isdigit()]
        lo, hi = (min(row_ids), max(row_ids)) if row_ids else (1, len(data))

    # Filter to batch rows. row_id is at column colmap["row_id"].
    ci_row = colmap["row_id"]
    batch = [r for r in data if ci_row is not None and len(r) > ci_row
             and r[ci_row].isdigit() and lo <= int(r[ci_row]) <= hi]

    wb = Workbook()

    # README
    build_readme(wb, citations.get("batch_label", f"[ref]-fill batch rows {lo}-{hi}"), [
        f"Batch rows: {lo}-{hi}  ({len(batch)} rows in scope)",
        f"Citation cells: {len(citations.get('cells', []))}",
        f"QA log entries: {len(citations.get('qa_log', []))}",
        f"Data conflicts flagged: {len(citations.get('data_conflicts', []))}",
        f"Candidate data fills: {len(citations.get('candidate_data_fills', []))}",
        f"Defects corrected: {len(citations.get('defects_corrected', []))}",
        "",
        "Color coding:",
        "  Green  = high confidence (multi-source or primary/regulatory + value verbatim)",
        "  Yellow = medium confidence (entity-level or contested)",
        "  Red    = low confidence / review needed",
        "  Peach  = override of pre-existing backend [ref]",
        "  Gray   = pre-existing backend value, untouched",
        "",
        "See QA_review sheet for per-cell provenance log.",
    ])

    # backend_ref_fill sheet
    ws = wb.create_sheet("backend_ref_fill")
    for col_i, h in enumerate(header, start=1):
        ws.cell(row=1, column=col_i, value=h)
    _apply_header_style(ws, 1)

    # Build a citation lookup: (row_id, field) -> citation cell
    cite_lookup = {}
    for c in citations.get("cells", []):
        key = (str(c["row_id"]), c["field"])
        cite_lookup.setdefault(key, []).append(c)

    # Render batch rows
    for r_offset, row in enumerate(batch, start=2):
        row_id = row[ci_row] if len(row) > ci_row else ""
        for col_i, val in enumerate(row, start=1):
            cell = ws.cell(row=r_offset, column=col_i, value=val)
            cell.alignment = WRAP_ALIGN
            # Check if this is a citation cell
            # Find canonical name for this column
            field_name = None
            for fk, fv in colmap.items():
                if fv == col_i - 1 and not fk.startswith("_"):
                    field_name = fk
                    break
            cites = cite_lookup.get((row_id, field_name), [])
            if cites:
                # New citation — apply confidence color and combine URLs
                # (one cell may have multiple URLs joined with newlines)
                conf = cites[0]["confidence"]
                fill = CONFIDENCE_FILLS.get(conf, FILL_RED)
                cell.fill = fill
                cell.value = "\n".join(c["url"] for c in cites)
            elif val and field_name and field_name.endswith("_ref"):
                # Pre-existing ref URL — gray
                cell.fill = FILL_GRAY

    # Freeze + widths
    ws.freeze_panes = "C2"
    for col_i, h in enumerate(header, start=1):
        col_letter = get_column_letter(col_i)
        if "[ref]" in h:
            ws.column_dimensions[col_letter].width = 50
        elif h.lower() in ("name", "shipowner", "shipbuilder", "operator/charterer"):
            ws.column_dimensions[col_letter].width = 25
        else:
            ws.column_dimensions[col_letter].width = 15

    # QA_review sheet
    ws_qa = wb.create_sheet("QA_review")
    qa_row = 1
    sections = [
        ("Per-cell citation log", ["row_id", "field", "action", "confidence", "url", "note"], citations.get("qa_log", [])),
        ("Data-value conflicts", ["row_id", "field", "backend_value", "research_value", "source_url", "note"], citations.get("data_conflicts", [])),
        ("Candidate data-value fills", ["row_id", "field", "proposed_value", "source_url", "confidence", "note"], citations.get("candidate_data_fills", [])),
        ("Defects corrected", ["row_id", "field", "old_url", "new_url", "reason"], citations.get("defects_corrected", [])),
        ("URL verification log", ["url", "status", "soft_error", "content_match", "result"], citations.get("verification_log", [])),
    ]
    for title, cols, items in sections:
        if not items:
            continue
        ws_qa.cell(row=qa_row, column=1, value=title).font = Font(bold=True, size=12)
        qa_row += 1
        for col_i, c in enumerate(cols, start=1):
            cell = ws_qa.cell(row=qa_row, column=col_i, value=c)
            cell.font = HEADER_FONT
            cell.fill = FILL_HEADER
            cell.alignment = HEADER_ALIGN
        qa_row += 1
        for item in items:
            for col_i, c in enumerate(cols, start=1):
                ws_qa.cell(row=qa_row, column=col_i,
                           value=str(item.get(c, ""))).alignment = WRAP_ALIGN
            qa_row += 1
        qa_row += 1  # blank row between sections

    # widths
    for col_letter in "ABCDEF":
        ws_qa.column_dimensions[col_letter].width = 25
    ws_qa.column_dimensions["E"].width = 60  # url column tends to be wide

    out_path = _resolve_out_path(args.out, "lng_carrier_backend_ref_fill.xlsx")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    print(f"  Wrote {out_path}")
    return out_path


def build_discovery(args):
    """Build the discovery mode workbook."""
    candidates_path = Path(args.candidates)
    payload = json.loads(candidates_path.read_text())

    wb = Workbook()

    build_readme(wb, f"LNG Carrier Discovery — gap window {payload.get('gap_window', 'unspecified')}", [
        f"Yards swept: {len(payload.get('yards_swept', []))}",
        f"Candidate clusters: {len(payload.get('candidates', []))}",
        f"Backend status flags: {len(payload.get('backend_status_flags', []))}",
        "",
        "Color coding (on candidate_vessels sheet):",
        "  Green  = 2+ cross-checked sources OR 1 primary/regulatory source with value verbatim",
        "  Yellow = entity-level confirmation; some data point implied/contested",
        "  Red    = single source / weak corroboration — review before promoting",
        "",
        "Workflow: review candidates -> approve/reject -> manually paste approved rows into backend.",
    ])

    # candidate_vessels sheet — mirrors the LIVE backend column order EXACTLY
    # after the four prefix columns (Discovery SOP §5.2 / §6.6 paste-compat).
    # The header is read from the fresh backend pull rather than hardcoded, so
    # the sheet always tracks the current schema (geolocation, Researcher, Last
    # updated, [Original source], etc. all appear as blank columns).
    with open(args.backend, encoding="utf-8") as f:
        backend_rows = list(csv.reader(f))
    colmap = json.loads(Path(args.backend).with_suffix(".colmap.json").read_text())
    backend_header = backend_rows[colmap["_header_row_idx"]]
    header_index = {h: i for i, h in enumerate(backend_header)}

    ws = wb.create_sheet("candidate_vessels")
    prefix_cols = ["cluster_id", "cluster_label", "confidence", "discovery_notes"]
    headers = prefix_cols + backend_header
    for col_i, h in enumerate(headers, start=1):
        ws.cell(row=1, column=col_i, value=h)
    _apply_header_style(ws, 1)

    n_prefix = len(prefix_cols)
    for r_offset, cand in enumerate(payload.get("candidates", []), start=2):
        confidence = cand.get("confidence", "Y")
        fill = CONFIDENCE_FILLS.get(confidence, FILL_YELLOW)
        # prefix cols
        ws.cell(row=r_offset, column=1, value=cand.get("cluster_id", "")).fill = fill
        ws.cell(row=r_offset, column=2, value=cand.get("cluster_label", "")).fill = fill
        ws.cell(row=r_offset, column=3, value=confidence).fill = fill
        ws.cell(row=r_offset, column=4, value=cand.get("discovery_notes", "")).fill = fill
        # backend cols — row_data is keyed by EXACT backend header strings.
        row_data = cand.get("row_data", {})
        unknown = [k for k in row_data if k not in header_index]
        if unknown:
            print(f"  [warn] candidate {cand.get('cluster_id')}: row_data keys not in "
                  f"backend header (ignored): {unknown}", file=sys.stderr)
        for h, idx in header_index.items():
            val = row_data.get(h, "")
            cell = ws.cell(row=r_offset, column=n_prefix + 1 + idx, value=val)
            cell.alignment = WRAP_ALIGN
            if val:  # only color cells that are populated
                cell.fill = fill

    ws.freeze_panes = "E2"
    for col_i, h in enumerate(headers, start=1):
        col_letter = get_column_letter(col_i)
        if "[ref]" in h:
            ws.column_dimensions[col_letter].width = 50
        elif h in ("cluster_label", "discovery_notes", "Name",
                   "Shipowner", "Shipbuilder", "Operator/charterer"):
            ws.column_dimensions[col_letter].width = 25
        else:
            ws.column_dimensions[col_letter].width = 15

    # QA_review sheet
    ws_qa = wb.create_sheet("QA_review")
    qa_row = 1
    sections = [
        ("Per-candidate provenance log",
         ["cluster_id", "cluster_label", "confidence", "source_urls", "notes"],
         payload.get("provenance_log", [])),
        ("Backend status flags",
         ["row_id", "issue_type", "details", "suggested_action"],
         payload.get("backend_status_flags", [])),
        ("URL verification log",
         ["url", "status", "soft_error", "content_match", "result"],
         payload.get("verification_log", [])),
        ("Search methodology audit",
         ["yard", "rows_in_window", "candidates_found", "notes"],
         payload.get("methodology_audit", {}).get("yards", [])),
    ]
    for title, cols, items in sections:
        if not items:
            continue
        ws_qa.cell(row=qa_row, column=1, value=title).font = Font(bold=True, size=12)
        qa_row += 1
        for col_i, c in enumerate(cols, start=1):
            cell = ws_qa.cell(row=qa_row, column=col_i, value=c)
            cell.font = HEADER_FONT
            cell.fill = FILL_HEADER
        qa_row += 1
        for item in items:
            for col_i, c in enumerate(cols, start=1):
                ws_qa.cell(row=qa_row, column=col_i,
                           value=str(item.get(c, ""))).alignment = WRAP_ALIGN
            qa_row += 1
        qa_row += 1

    for col_letter in "ABCDE":
        ws_qa.column_dimensions[col_letter].width = 30

    # backend_status_flags sheet (mirror of QA section 2)
    if payload.get("backend_status_flags"):
        ws_bsf = wb.create_sheet("backend_status_flags")
        cols = ["row_id", "issue_type", "details", "suggested_action"]
        for col_i, c in enumerate(cols, start=1):
            ws_bsf.cell(row=1, column=col_i, value=c)
        _apply_header_style(ws_bsf, 1)
        for r_offset, item in enumerate(payload["backend_status_flags"], start=2):
            for col_i, c in enumerate(cols, start=1):
                ws_bsf.cell(row=r_offset, column=col_i,
                            value=str(item.get(c, ""))).alignment = WRAP_ALIGN
        for col_letter in "ABCD":
            ws_bsf.column_dimensions[col_letter].width = 30

    out_path = _resolve_out_path(args.out, "lng_carrier_candidate_vessels.xlsx")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    print(f"  Wrote {out_path}")
    return out_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["ref_fill", "discovery"], required=True)
    p.add_argument("--rows", help="Row range for ref_fill, e.g. '1170-1190'")
    p.add_argument("--citations", help="Path to citations JSON (ref_fill mode)")
    p.add_argument("--candidates", help="Path to candidates JSON (discovery mode)")
    p.add_argument("--backend", default=str(backend_csv_path()),
                   help="Path to backend CSV (default: <work_dir>/backend.csv)")
    p.add_argument("--out",
                   help="Output path. Either a directory (the canonical xlsx "
                        "filename will be appended) or an explicit .xlsx file. "
                        "For batches, pass batches/<date>_<mode>_<scope>/.")
    args = p.parse_args()

    if args.mode == "ref_fill":
        if not args.citations:
            p.error("--citations required for ref_fill mode")
        build_ref_fill(args)
    else:
        if not args.candidates:
            p.error("--candidates required for discovery mode")
        build_discovery(args)


if __name__ == "__main__":
    main()
