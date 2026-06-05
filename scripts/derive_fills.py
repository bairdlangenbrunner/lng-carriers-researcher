"""
Data-fill derivation (Data-fill SOP §5-§6).

From the fresh backend, select in-scope rows by a `Last updated >= DATE` filter,
compute the deterministic *derivable* fills (yard-location block; Shipowner
country/area sibling-copy; Capacity units), and emit:

  work/data_fill.json       {batch_label, scope, fills:[derivable...], documented_blanks, verification_log}
  work/research_tasks.json  per-cluster lists of the cells still needing web research

The researched fills (produced by per-cluster subagents) are merged into
work/data_fill.json later, before the §3.8 verification gate and the build.
"""
import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from paths import backend_csv_path, work_dir
from normalize import normalize_builder, normalize_owner, owner_country
from build_workbook import YARD_LOCATION_COLS, _yard_location_map_table_first
from lookups import owner_facts, load_owner_facts

# Primary researchable columns (exact backend headers) + their paired [ref].
# Capacity units / Price currency are NOT listed here — they are dependent
# (units follows Capacity, currency follows Price) and handled alongside them.
RESEARCH_COLS = [
    ("IMO number", "IMO number [ref]"),
    ("Name", "Name [ref]"),
    ("Hull number", "Hull number [ref]"),
    ("Shipowner", "Shipowner [ref]"),
    ("Shipowner country/area", "Shipowner country/area [ref]"),
    ("Capacity", "Capacity [ref]"),
    ("Cargo type", "Cargo type [ref]"),
    ("Vessel type", "Vessel type [ref]"),
    ("Propulsion type", "Propulsion type [ref]"),
    ("Delivery year", "Delivery year [ref]"),
    ("Operator/charterer", "Operator/charterer [ref]"),
    ("Contract date", "Contract date [ref]"),
    ("Price", "Price [ref]"),
]

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_date(s):
    """Parse M/D/YYYY, YYYY-MM-DD, or DD-Mon-YYYY into a (y, m, d) tuple; None if unparseable."""
    s = (s or "").strip()
    if not s:
        return None
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return (int(m[3]), int(m[1]), int(m[2]))
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return (int(m[1]), int(m[2]), int(m[3]))
    m = re.match(r"(\d{1,2})[-\s]([A-Za-z]{3})[-\s](\d{4})", s)
    if m:
        return (int(m[3]), _MONTHS.get(m[2].lower(), 0), int(m[1]))
    return None


def _sibling_country_ref(data, owner_tag, own_i, ctry_i, ctry_ref_i):
    """A sibling row's Shipowner country/area [ref] for this owner, if any has one."""
    for r in data:
        if len(r) > max(own_i, ctry_i, ctry_ref_i) and normalize_owner(r[own_i]) == owner_tag \
                and r[ctry_i].strip() and r[ctry_ref_i].strip():
            return r[ctry_ref_i].strip()
    return ""


def _derivable(row_id, field, value, ref_field="", new_urls=None, note=""):
    return {
        "row_id": row_id, "field": field, "ref_field": ref_field,
        "proposed_value": value, "new_urls": new_urls or [],
        "prev_state": "blank", "existing_ref_preserved": "",
        "confidence": "G", "derivable": True, "note": note,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True, help="Last updated >= this date (YYYY-MM-DD)")
    ap.add_argument("--backend", default=str(backend_csv_path()))
    args = ap.parse_args()
    cut = tuple(int(x) for x in args.since.split("-"))

    rows = list(csv.reader(open(args.backend, encoding="utf-8")))
    colmap = json.loads(Path(args.backend).with_suffix(".colmap.json").read_text())
    hdr = rows[colmap["_header_row_idx"]]
    H = {h: i for i, h in enumerate(hdr)}
    data = rows[colmap.get("_data_starts_at", colmap["_header_row_idx"] + 1):]
    RID = colmap["row_id"]
    LU, OWN, CTRY, CTRY_REF = H["Last updated"], H["Shipowner"], \
        H["Shipowner country/area"], H["Shipowner country/area [ref]"]
    CAP, UNITS = H["Capacity"], H["Capacity units"]
    yard_map = _yard_location_map_table_first(data, hdr)
    owner_facts_tbl = load_owner_facts()

    in_scope = [r for r in data if len(r) > LU and (parse_date(r[LU]) or (0, 0, 0)) >= cut]
    scope_ids = [r[RID].strip() for r in in_scope]

    fills = []
    research = defaultdict(list)

    for r in in_scope:
        rid = r[RID].strip()

        def val(h):
            i = H.get(h)
            return r[i].strip() if i is not None and len(r) > i else ""

        builder_tag = normalize_builder(val("Shipbuilder"))
        owner_tag = normalize_owner(val("Shipowner"))
        cluster = f"{builder_tag}|{owner_tag}"

        # --- derivable: yard-location block (DC §6.7) ---
        if builder_tag in yard_map:
            for h, v in yard_map[builder_tag].items():
                if v.strip() and not val(h):
                    fills.append(_derivable(rid, h, v,
                                            note=f"yard-location for '{builder_tag}' (DC §6.7)"))

        # --- derivable: Shipowner country/area — refdata table first, then
        #     backend sibling-copy (DF §5) ---
        if not val("Shipowner country/area"):
            facts = owner_facts(val("Shipowner"), owner_facts_tbl)
            c = facts.get("Shipowner country/area")
            if c:
                ref = facts.get("Shipowner country/area [ref]", "")
                note = f"from refdata/shipowner_facts.csv for owner '{owner_tag}'" \
                       + ("" if ref else " (no [ref] in table; value only)")
            else:
                c = owner_country(val("Shipowner"), data, OWN, CTRY)
                ref = _sibling_country_ref(data, owner_tag, OWN, CTRY, CTRY_REF) if c else ""
                note = (f"derived from backend sibling rows for owner '{owner_tag}'"
                        + ("" if ref else " (no sibling country [ref]; value only)")) if c else ""
            if c:
                fills.append({
                    "row_id": rid, "field": "Shipowner country/area",
                    "ref_field": "Shipowner country/area [ref]",
                    "proposed_value": c, "new_urls": [ref] if ref else [],
                    "prev_state": "blank", "existing_ref_preserved": "",
                    "confidence": "G", "derivable": True, "note": note,
                })

        # --- derivable: Capacity units = cbm when Capacity already present ---
        if val("Capacity") and not val("Capacity units"):
            fills.append(_derivable(rid, "Capacity units", "cbm",
                                    note="units follow Capacity (only 'cbm' in backend)"))

        # --- research targets: remaining blank/unknown in-scope columns ---
        derivable_fields = {f["field"] for f in fills if f["row_id"] == rid}
        blanks, unknowns = [], []
        for col, _ref in RESEARCH_COLS:
            if col in derivable_fields:
                continue
            v = val(col)
            if not v:
                blanks.append(col)
            elif v.lower() == "unknown":
                unknowns.append(col)
        if blanks or unknowns:
            research[cluster].append({
                "row_id": rid, "name": val("Name"), "shipbuilder": val("Shipbuilder"),
                "shipowner": val("Shipowner"), "contract_date": val("Contract date"),
                "delivery_year": val("Delivery year"), "capacity": val("Capacity"),
                "blanks": blanks, "unknowns": unknowns,
            })

    payload = {
        "batch_label": f"Data-fill batch — Last updated >= {args.since}",
        "scope": {"filter": f"Last updated >= {args.since}", "row_ids": scope_ids},
        "fills": fills, "documented_blanks": [], "verification_log": [],
    }
    (work_dir() / "data_fill.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    (work_dir() / "research_tasks.json").write_text(
        json.dumps({"since": args.since, "clusters": research}, indent=2, ensure_ascii=False))

    n_cells = sum(len(x["blanks"]) + len(x["unknowns"]) for v in research.values() for x in v)
    print(f"in-scope rows:           {len(scope_ids)}  (ids {scope_ids[0]}..{scope_ids[-1]})")
    print(f"derivable fills:         {len(fills)}")
    print(f"clusters needing research: {len(research)}")
    print(f"cells needing research:  {n_cells}")
    print(f"wrote {work_dir() / 'data_fill.json'} and research_tasks.json")


if __name__ == "__main__":
    main()
