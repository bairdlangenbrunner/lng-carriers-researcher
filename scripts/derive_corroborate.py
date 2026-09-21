"""
Corroborate-batch derivation — find data points whose ONLY source is the IGU 2025
World LNG Report and queue them for independent corroboration.

The backend leans on a single aggregate source: the IGU 2025 World LNG Report
(https://www.igu.org/igu-reports/2025-world-lng-report) is the sole [ref] on
thousands of cells. A report PDF standing alone behind a specific per-vessel
figure is weak provenance and fails the spirit of the §3.8c value↔ref gate (the
report page does not surface per-vessel numbers). This batch type KEEPS the IGU
ref and APPENDS >=2 independent corroborators per cell.

This selector picks the cells in scope and emits the same two files the data-fill
pipeline consumes, so the rest of the chain (research fan-out -> merge_fills ->
build_workbook --mode data_fill -> apply_batch) is reused unchanged:

  work/data_fill.json       {batch_label, scope{row_ids, igu_url}, fills:[] (none derivable here),
                             documented_blanks, verification_log}
  work/research_tasks.json  per-cluster lists of (field, existing_value) pairs to corroborate

Scope = the five priority fields whose [ref] equals EXACTLY the IGU url (after
splitting on ", "/newline) and whose data value is non-blank/non-`unknown`,
within a --rows X-Y row_id range. Identity (IMO/hull) and soft fields (status,
propulsion, cargo/vessel type) are out of scope by design.

    python scripts/derive_corroborate.py --rows 3-22
"""
import argparse
import json
import sys
from collections import defaultdict

from backend_io import load_backend
from paths import backend_csv_path, work_dir
from normalize import normalize_builder, normalize_owner
from url_verifier import citable_form, citable_forms

IGU_URL = "https://www.igu.org/igu-reports/2025-world-lng-report"

# Priority fields to corroborate (exact backend headers) + their paired [ref].
PRIORITY_COLS = [
    ("Name", "Name [ref]"),
    ("Shipbuilder", "Shipbuilder [ref]"),
    ("Shipowner", "Shipowner [ref]"),
    ("Capacity", "Capacity [ref]"),
    ("Delivery year", "Delivery year [ref]"),
]


def _refs(cell):
    """Split a [ref] cell into its individual URLs (", "- or newline-joined)."""
    return [p.strip() for p in str(cell or "").replace("\n", ", ").split(", ") if p.strip()]


def _parse_rows(spec):
    lo, _, hi = spec.partition("-")
    lo, hi = int(lo), int(hi or lo)
    return (lo, hi) if lo <= hi else (hi, lo)


def main():
    from derive_fills import _check_stale_research

    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True, help="row_id range, inclusive (e.g. 3-22)")
    ap.add_argument("--igu-url", default=IGU_URL, help="the sole-source URL to corroborate")
    ap.add_argument("--backend", default=str(backend_csv_path()))
    ap.add_argument("--force", action="store_true",
                    help="proceed even if work/ holds research_*.json from a prior batch")
    args = ap.parse_args()
    _check_stale_research(args.force)
    lo, hi = _parse_rows(args.rows)
    # the landing page and the edition's report PDF are one source (IG §1): a cell holding
    # either is in scope. The backend's ref stays as it is — the batch keeps --igu-url as given.
    igu = args.igu_url.strip()

    be = load_backend(args.backend)
    H, data = be.header_index, be.data
    RID = be.colmap["row_id"]

    scope_ids = []
    research = defaultdict(list)
    n_cells = 0

    for r in data:
        if len(r) <= RID:
            continue
        rid = r[RID].strip()
        if not (rid.isdigit() and lo <= int(rid) <= hi):
            continue

        def val(h):
            i = H.get(h)
            return r[i].strip() if i is not None and len(r) > i else ""

        targets = []
        for value_col, ref_col in PRIORITY_COLS:
            vi, ri = H.get(value_col), H.get(ref_col)
            if vi is None or ri is None:
                continue
            value = r[vi].strip() if len(r) > vi else ""
            cell_refs = _refs(r[ri] if len(r) > ri else "")
            # in scope iff the value is real AND the ONLY ref is the IGU report
            if value and value.lower() != "unknown" and citable_forms(cell_refs) == [citable_form(igu)]:
                targets.append({
                    "field": value_col, "ref_field": ref_col, "existing_value": value,
                })
        if not targets:
            continue

        scope_ids.append(rid)
        n_cells += len(targets)
        cluster = f"{normalize_builder(val('Shipbuilder'))}|{normalize_owner(val('Shipowner'))}"
        research[cluster].append({
            "row_id": rid, "name": val("Name"), "shipbuilder": val("Shipbuilder"),
            "shipowner": val("Shipowner"), "imo": val("IMO number"),
            "hull": val("Hull number"), "contract_date": val("Contract date"),
            "delivery_year": val("Delivery year"), "capacity": val("Capacity"),
            "corroborate": targets,
        })

    payload = {
        "batch_label": f"Corroborate IGU-only refs — rows {lo}-{hi}",
        "scope": {
            "filter": f"sole-ref == IGU 2025; priority fields; row_id in [{lo}, {hi}]",
            "row_ids": scope_ids, "igu_url": igu,
            "priority_fields": [c for c, _ in PRIORITY_COLS],
        },
        "fills": [], "documented_blanks": [], "verification_log": [],
    }
    (work_dir() / "data_fill.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    (work_dir() / "research_tasks.json").write_text(json.dumps({
        "mode": "corroborate", "igu_url": igu,
        "instructions": (
            "For each row's `corroborate` entries, find >=2 INDEPENDENT sources (Tier 1-2 per "
            "data/source_roster.md; never IGU, GTT-standalone, SFOC, or GEM) that each contain "
            "the EXACT existing_value for that field. Run every URL through scripts/url_verifier.py "
            "first. Emit fills shaped like data_fill: "
            "{row_id, field, ref_field, proposed_value=<existing_value verbatim>, "
            "new_urls=[corroborators, IGU EXCLUDED], confidence in {G,Y}, derivable=false, "
            "prev_state='corroborate'}. merge_fills re-prepends IGU and enforces the >=2 rule."),
        "clusters": research,
    }, indent=2, ensure_ascii=False))

    print(f"in-scope rows:           {len(scope_ids)}"
          + (f"  (ids {scope_ids[0]}..{scope_ids[-1]})" if scope_ids else "  (none)"),
          file=sys.stderr)
    print(f"clusters needing research: {len(research)}", file=sys.stderr)
    print(f"IGU-only priority cells: {n_cells}", file=sys.stderr)
    print(f"wrote {work_dir() / 'data_fill.json'} and research_tasks.json", file=sys.stderr)


if __name__ == "__main__":
    main()
