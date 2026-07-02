"""
Reference-data loaders — the single source of truth for data/.

Two kinds of reference data the toolchain reads, both centralized here so the
lists/tables live in exactly one place:

1. Controlled vocabularies for the type columns (Data-fill SOP §8) — the exact
   canonical value sets the backend uses. build_workbook.py's data-fill validator
   and qc_backend.py both import CONTROLLED_VOCAB from here. data/controlled_vocab.md
   is the human-readable mirror.

2. Builder / owner FACTS tables — facts that belong to the shipyard or the owner,
   NOT the individual vessel: the yard-location block (keyed by normalize_builder)
   and the shipowner country/area (keyed by normalize_owner). Stored as editable
   CSVs in data/ and AUTHORITATIVE — the autofill (build_workbook, derive_fills)
   reads them first, and qc_backend.py flags backend rows that disagree with them.
   Seed / refresh them from the live backend with seed_lookups.py.

These modules import only `normalize` and `paths` (both light) — never
build_workbook — so there's no import cycle.
"""
import csv
from pathlib import Path

from paths import repo_root
from normalize import normalize_builder, normalize_owner


# --- 1. Controlled vocabularies (mirrors data/controlled_vocab.md) ----------
# A proposal for these columns must use one of these exact canonical values, and
# a value appearing in a DIFFERENT column is the signal qc_backend.py keys on.
CONTROLLED_VOCAB = {
    "Cargo type": {"membrane", "spherical", "self-supporting prismatic", "type C"},
    "Vessel type": {"conventional", "FSRU", "q-flex", "q-max", "icebreaker",
                    "FSU", "Supporting", "small-scale", "mid-scale"},
    "Propulsion type": {"X-DF", "DFDE", "steam", "ME-GA", "ME-GI", "SSD",
                        "steam reheat", "STaGE", "prismatic conventional DFDE",
                        "prismatic small-scale DFDE"},
    "Capacity units": {"cbm"},
    "Price currency": {"$m", "USD"},
}


# --- 2. Builder / owner facts tables -------------------------------------------
BUILDER_FACTS_CSV = "shipbuilder_facts.csv"
OWNER_FACTS_CSV = "shipowner_facts.csv"

# The 7-column yard-location block (a property of the yard, not the vessel).
# Defined here as the canonical list; build_workbook re-exports it as
# YARD_LOCATION_COLS for backward compatibility.
YARD_FACT_COLS = [
    "Shipbuilder yard country/area",
    "Shipbuilder yard country/area [ref]",
    "Yard location latitude",
    "Yard location longitude",
    "Yard location plus code",
    "Yard location accuracy",
    "Yard location lat/lon [ref]",
]
OWNER_FACT_COLS = ["Shipowner country/area", "Shipowner country/area [ref]"]

# Marker written into a facts cell that must NEVER be auto-applied — the fact is
# genuinely ambiguous for this tag (e.g. owner 'mol' is Japan in some rows,
# Türkiye in others) and must be researched per-vessel. _usable() drops these.
AMBIGUOUS = "AMBIGUOUS"


def data_dir() -> Path:
    return repo_root() / "data"


def _load_facts(filename: str, key_col: str) -> dict:
    """tag -> {column header: value} from a data/ facts CSV. {} if absent."""
    path = data_dir() / filename
    if not path.exists():
        return {}
    out = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            tag = (row.get(key_col) or "").strip()
            if not tag:
                continue
            out[tag] = {k: (v or "").strip() for k, v in row.items()
                        if k and k != key_col}
    return out


def load_builder_facts() -> dict:
    """Raw shipbuilder facts: builder_tag -> {yard-location header: value}."""
    return _load_facts(BUILDER_FACTS_CSV, "builder_tag")


def load_owner_facts() -> dict:
    """Raw shipowner facts: owner_tag -> {Shipowner country/area(+[ref]): value}."""
    return _load_facts(OWNER_FACTS_CSV, "owner_tag")


def _usable(block: dict) -> dict:
    """Drop blank and AMBIGUOUS-marked values so callers only see applicable facts."""
    return {k: v for k, v in block.items() if v and v != AMBIGUOUS}


def builder_facts(builder_raw: str, facts: dict = None) -> dict:
    """Usable yard-location facts for a raw shipbuilder name ({} if none/ambiguous).

    Pass a pre-loaded `facts` dict (from load_builder_facts()) to avoid re-reading
    the CSV in a per-row loop.
    """
    facts = load_builder_facts() if facts is None else facts
    return _usable(facts.get(normalize_builder(builder_raw), {}))


def owner_facts(owner_raw: str, facts: dict = None) -> dict:
    """Usable owner facts (country/area + [ref]) for a raw owner name."""
    facts = load_owner_facts() if facts is None else facts
    return _usable(facts.get(normalize_owner(owner_raw), {}))
