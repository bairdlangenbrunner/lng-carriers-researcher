"""
What an IGU World LNG Report prints for ONE vessel — the IMO-keyed check behind every
IGU report-PDF ref (IG §1).

The report PDF is a 1,000-vessel table: a text search of it "corroborates" any common
value (`China`, `174000`, somebody's `Hull 3387`). So a cell that cites the PDF is checked
against what the coordinate extraction (work/igu_fleet_<edition>.json, igu_fleet.py)
prints for the row's IMO, column by column:

    check(edition, imo, field, value) -> (True | False | None, reason)

    True   IGU prints this value for this IMO            -> the PDF is the ref
    False  IGU prints something else, has no such column / vessel, or the row has no IMO
           to look up (a text match on a generic value is not this vessel) -> not a ref here
    None   cannot tell (no extraction in work/) -> the caller's text gate stands

`corroborates_cell()` is the gate every caller uses: `url_verifier.corroborates` plus this
check whenever the URL is an IGU report PDF.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import work_dir  # noqa: E402

# backend header -> IGU record key ("" = handled specially below)
FIELD_KEY = {"Name": "name", "Shipowner": "shipowner", "Shipbuilder": "shipbuilder",
             "Capacity": "capacity", "Cargo type": "cargo_type", "Vessel type": "vessel_type",
             "Propulsion type": "propulsion", "Delivery year": "delivery_year",
             "IMO number": "imo", "Hull number": "", "Other names": "", "Status": "",
             # a former year an earlier edition printed (RF §4.19); the caller gates one year
             "Previous delivery year(s)": "delivery_year"}
_STATUS_TABLE = {"active": "fleet", "on order": "orderbook"}
_EDITION_RE = re.compile(r"igu-world-lng-report-(\d{4})", re.I)


def edition_of(url: str) -> str:
    m = _EDITION_RE.search(url or "")
    return m.group(1) if m else ""


def field_of(column: str) -> str:
    """'Capacity [ref]' / 'capacity_ref'-style keys are the caller's business; this takes
    the backend header, with or without its ' [ref]' suffix."""
    return re.sub(r"\s*\[ref\]\s*$", "", str(column or "")).strip()


def _hull_in(printed: str, value: str) -> bool:
    """Hull forms `hull_only` cannot reduce to one token: 'Hull CMHI-282-01', IGU's
    'Hull No.YZJ2022-1475', an unbalanced 'Energy Fortitude (ex-Victor Hugo (8107)'.
    The cell's hull (yard tag dropped) must be one of the digit-bearing tokens IGU prints."""
    key = lambda x: re.sub(r"^H(?=\d)", "", re.sub(r"[^A-Z0-9]", "", x.upper()))
    want = key(re.sub(r"\s*\([^()]*\)\s*$", "", re.sub(r"^\s*hull\s+(?:no\.?\s*)?", "", value, flags=re.I)))
    toks = re.findall(r"[A-Za-z][\w-]*\d[\w-]*|\d[\w-]*", re.sub(r"\bNo\.", " ", printed or ""))
    return bool(want) and any(key(t) == want for t in toks)


class IguTable:
    def __init__(self, records: dict | None = None, pairs=None):
        self._rec = records            # {edition: {imo: [record, ...]}}; loaded on first use
        self._pairs = pairs            # learned (IGU builder label, backend builder) pairs

    def records(self) -> dict:
        if self._rec is None:
            self._rec = {}
            for f in sorted(work_dir().glob("igu_fleet_*.json")):
                d, by = json.loads(f.read_text()), {}
                for t in ("fleet", "orderbook"):
                    for r in d.get(t, []):
                        if r.get("imo"):
                            by.setdefault(str(r["imo"]), []).append(r)
                self._rec[str(d.get("edition"))] = by
        return self._rec

    def pairs(self):
        """Builder label pairs, learned over the IMO-matched vessels (igu_reconcile)."""
        if self._pairs is None:
            from collections import Counter
            self._pairs = Counter()
            try:
                from backend_io import load_backend
                from igu_reconcile import backend_entries, builder_pairs
                from paths import backend_csv_path
                ents = backend_entries(load_backend(backend_csv_path()))
                for by in self.records().values():
                    self._pairs.update(builder_pairs(
                        [(r, e) for e in ents for r in by.get(e["imo"], [])]))
            except (FileNotFoundError, SystemExit):
                pass
        return self._pairs

    def check(self, edition: str, imo, field: str, value) -> tuple[bool | None, str]:
        from igu_reconcile import _int, _name_key, field_differs
        from other_names import hull_only, igu_prints_name
        field, imo, v = field_of(field), re.sub(r"\D", "", str(imo or "")), str(value or "").strip()
        by = self.records().get(str(edition))
        if by is None:
            return None, f"no IGU {edition} extraction in work/"
        if field not in FIELD_KEY:
            return False, f"IGU {edition} prints no {field or 'such'} column"
        if not imo:
            return False, f"row has no IMO, so nothing IGU {edition} prints can be tied to it"
        recs = by.get(imo)
        if not recs:
            return False, f"IGU {edition} does not list IMO {imo}"
        if not v:
            return True, "OK (no value to corroborate)"
        printed = []
        for r in recs:
            key = FIELD_KEY[field]
            if field == "Status":
                got, ok = f"the {r['table']} table", _STATUS_TABLE.get(v.lower()) == r["table"]
            elif field in ("Hull number", "Other names"):
                got = r.get("name", "")
                # 'Hull 3387' / 'Al Nigyan (3387)' / '… (ex-Victor Hugo (8107))'; a Hull number
                # cell must be a hull (a vessel name there is a column offset, not a match)
                # An Other names cell is a list: the PDF is cited for the element it prints.
                parts = [x.strip() for x in v.split(";") if x.strip()] if field == "Other names" else [v]
                ok = any(igu_prints_name(got, x) and (field == "Other names" or bool(hull_only(x)))
                         for x in parts) or (field == "Hull number" and _hull_in(got, v))
            elif field == "IMO number":
                got, ok = r["imo"], re.sub(r"\D", "", v) == r["imo"]
            elif key in ("capacity", "delivery_year"):   # the figure itself, no tolerance (§3.8c)
                got = r.get(key)
                ok = got not in (None, "") and _int(v) == _int(got)
            elif field == "Name":
                got = r.get("name", "")
                ok = _name_key(v) == _name_key(got) or igu_prints_name(got, v)
            else:
                got = r.get(key)
                ok = got not in (None, "") and not field_differs(key, v, got, self.pairs())
            if ok:
                return True, f"OK (IGU {edition} prints {got!r} for IMO {imo}, coordinate extraction)"
            printed.append(got)
        shown = ", ".join(repr(p) for p in printed if p not in (None, "")) or "nothing"
        return False, f"IGU {edition} prints {shown} for IMO {imo}, not {v!r}"


_TABLE = IguTable()


def corroborates_cell(url: str, value, field: str = "", imo: str = "", table: IguTable | None = None):
    """`url_verifier.corroborates`, with an IGU report PDF held to what it prints for this
    row's IMO in this column. Any other URL: unchanged."""
    from url_verifier import corroborates
    ok, reason = corroborates(url, value)
    ed = edition_of(url)
    if not ed or not field or not (ok or reason.startswith("page does not contain")):
        return ok, reason                                   # not IGU / dead / blocked / banned
    verdict, why = (table or _TABLE).check(ed, imo, field, value)
    if verdict is None:
        return ok, (f"{reason} [{why}]" if ok else reason)
    return verdict, why
