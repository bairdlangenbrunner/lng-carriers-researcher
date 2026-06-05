"""
Seed / refresh the authoritative builder & owner facts tables from the live backend.

The yard-location block (a property of the yard) and the shipowner country/area
(a property of the owner) are repeated across every vessel row in the backend.
This script lifts them into two editable, deduplicated CSVs that become the
canonical source the autofill and qc_backend.py read:

  refdata/shipbuilder_facts.csv   builder_tag -> 7-column yard-location block
  refdata/shipowner_facts.csv     owner_tag   -> Shipowner country/area (+[ref])

Re-runnable. By default it MERGES: adds newly-seen tags, and REPORTS (to stderr)
any tag whose backend-derived value differs from the curated file — but never
overwrites a curated row. Use --overwrite to regenerate from scratch.

Owners whose backend siblings disagree on country (e.g. 'mol': Japan/Türkiye) are
written with the AMBIGUOUS marker so the autofill never applies them — they're
researched per-vessel (matches the normalize.owner_country guard).

    python scripts/seed_lookups.py [--overwrite]
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from paths import backend_csv_path
from normalize import normalize_owner
from build_workbook import _build_yard_location_map
from lookups import (refdata_dir, YARD_FACT_COLS, OWNER_FACT_COLS, AMBIGUOUS,
                     BUILDER_FACTS_CSV, OWNER_FACTS_CSV)


def derive_owner_facts(data, H):
    """owner_tag -> {country/area(+[ref])} from backend siblings; AMBIGUOUS if mixed."""
    own_i, ctry_i, ref_i = (H["Shipowner"], H["Shipowner country/area"],
                            H["Shipowner country/area [ref]"])
    countries = defaultdict(set)
    a_ref = {}  # tag -> a [ref] seen paired with a country
    for r in data:
        if len(r) <= max(own_i, ctry_i, ref_i):
            continue
        tag = normalize_owner(r[own_i])
        c = r[ctry_i].strip()
        if not tag or not c:
            continue
        countries[tag].add(c)
        if r[ref_i].strip():
            a_ref.setdefault(tag, r[ref_i].strip())
    out = {}
    for tag, cset in countries.items():
        if len(cset) == 1:
            out[tag] = {"Shipowner country/area": next(iter(cset)),
                        "Shipowner country/area [ref]": a_ref.get(tag, "")}
        else:
            out[tag] = {"Shipowner country/area": AMBIGUOUS,
                        "Shipowner country/area [ref]": ""}
    return out


def write_facts(path, key_col, fact_cols, derived, overwrite):
    """Merge `derived` into the curated CSV at `path`. Returns (added, changed, total)."""
    existing = {}
    if path.exists() and not overwrite:
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                k = (row.get(key_col) or "").strip()
                if k:
                    existing[k] = {c: (row.get(c) or "").strip() for c in fact_cols}
    final = dict(existing)
    added, changed = [], []
    for tag, block in derived.items():
        block = {c: block.get(c, "") for c in fact_cols}
        if tag not in final:
            final[tag] = block
            added.append(tag)
        elif final[tag] != block:
            changed.append(tag)  # curated row kept; difference only reported
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([key_col] + fact_cols)
        for tag in sorted(final):
            w.writerow([tag] + [final[tag].get(c, "") for c in fact_cols])
    return added, changed, len(final)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=str(backend_csv_path()))
    ap.add_argument("--overwrite", action="store_true",
                    help="Regenerate from the backend, discarding curated edits")
    args = ap.parse_args()

    rows = list(csv.reader(open(args.backend, encoding="utf-8")))
    colmap = json.loads(Path(args.backend).with_suffix(".colmap.json").read_text())
    hdr = rows[colmap["_header_row_idx"]]
    H = {h: i for i, h in enumerate(hdr)}
    data = rows[colmap.get("_data_starts_at", colmap["_header_row_idx"] + 1):]

    builder_derived = _build_yard_location_map(data, hdr)
    owner_derived = derive_owner_facts(data, H)

    refdata_dir().mkdir(parents=True, exist_ok=True)
    for name, key_col, cols, derived in [
        (BUILDER_FACTS_CSV, "builder_tag", YARD_FACT_COLS, builder_derived),
        (OWNER_FACTS_CSV, "owner_tag", OWNER_FACT_COLS, owner_derived),
    ]:
        path = refdata_dir() / name
        added, changed, total = write_facts(path, key_col, cols, derived, args.overwrite)
        print(f"{name}: {total} rows  (+{len(added)} new, {len(changed)} differ from backend)")
        if added:
            print(f"    new tags: {', '.join(sorted(added))}")
        if changed:
            print(f"    backend differs (curated kept — review): {', '.join(sorted(changed))}")
    amb = [t for t, b in owner_derived.items() if b["Shipowner country/area"] == AMBIGUOUS]
    if amb:
        print(f"  ambiguous owners (won't autofill, research per-vessel): {', '.join(sorted(amb))}")
    print("Review the two CSVs in refdata/ before relying on them.")


if __name__ == "__main__":
    main()
