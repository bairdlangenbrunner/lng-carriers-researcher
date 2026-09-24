"""
Shared backend-CSV loading and backend date parsing.

Every batch script needs the same three things from the fresh pull: the raw
rows, the header, and the column-index map (colmap) that pull_backend.py
derived from the header row. Before this module existed that load was
reimplemented in seven scripts with slightly different shapes and mostly
raw-traceback failure modes; this is the one canonical version, with a
friendly "run pull_backend.py first" error when the pull hasn't happened.

Library usage:
    from backend_io import load_backend, BackendNotPulled

    be = load_backend()                # default work/backend.csv
    be.header                          # header row (list of cell strings)
    be.data                            # data rows (below the header)
    be.colmap                          # canonical-name -> column index
    be.header_index                    # exact header text -> column index
    be.row_by_id()                     # key (UUID or legacy id) -> raw row
    be.sheet_row_map()                 # key -> live 1-based sheet row
    be.canonical_key(k)                # legacy id or UUID -> UUID

Row identity note (report-live-rows rule): ``row_id`` is the row KEY — the
``UUID`` column (column A since 2026-09-23), one random v4 UUID per row that
never changes. The old "original order in sheet" stamp is ``legacy_row_id``;
``data/legacy_row_ids.csv`` maps every legacy id to its UUID, so a batch keyed
by the old numeric id still resolves (``row_by_id`` / ``sheet_row_map`` /
``canonical_key`` accept either). Humans navigate the live sheet, so anything
reported to a human uses ``sheet_row_map()`` / the CSV line position, never a key.

Date parsing: ``parse_date`` and ``contract_month`` are the single home for
the backend's mixed date formats ("2026-03-15", "3/15/2026", "16-Dec-2025",
"Dec 2025", "2026"). They were previously triplicated across derive_fills,
dedup_index, and qc_backend.
"""
import csv
import json
import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from paths import backend_csv_path


class BackendNotPulled(RuntimeError):
    """The backend CSV or its colmap is missing — pull_backend.py hasn't run."""


@dataclass
class Backend:
    path: Path
    rows: list  # every raw CSV row, including any preamble + header
    colmap: dict

    @property
    def header_row_idx(self) -> int:
        return self.colmap["_header_row_idx"]

    @property
    def data_start(self) -> int:
        return self.colmap.get("_data_starts_at", self.header_row_idx + 1)

    @property
    def header(self) -> list:
        return self.rows[self.header_row_idx]

    @property
    def data(self) -> list:
        return self.rows[self.data_start:]

    @cached_property
    def header_index(self) -> dict:
        """Exact header text -> column index (first occurrence wins)."""
        out = {}
        for i, h in enumerate(self.header):
            out.setdefault(h, i)
        return out

    def cell(self, row: list, col: int | None) -> str:
        """row[col] stripped, or "" when the column is absent/short."""
        return row[col].strip() if col is not None and len(row) > col else ""

    def key_of(self, row: list) -> str:
        """The row's key (its UUID), or "" for a row without one or a spare row."""
        k = self.cell(row, self.colmap["row_id"])
        return "" if k and self.is_spare(row) else k

    def is_spare(self, row: list) -> bool:
        """A pre-generated key row: a UUID and nothing else — not a vessel yet."""
        ki = self.colmap["row_id"]
        return all(not c.strip() for i, c in enumerate(row) if i != ki)

    @cached_property
    def legacy_to_uuid(self) -> dict:
        """legacy "original order in sheet" id -> UUID: the frozen data/legacy_row_ids.csv
        (the column was deleted from the sheet 2026-09-24), overridden by a live legacy column if a
        snapshot still has one."""
        out = load_legacy_map()
        li = self.colmap.get("legacy_row_id")
        if li is not None and li != self.colmap["row_id"]:
            for r in self.data:
                lid, key = self.cell(r, li), self.key_of(r)
                if lid and key:
                    out[lid] = key
        return out

    def canonical_key(self, key) -> str:
        """Any accepted key (UUID or legacy numeric id) -> the UUID (unchanged if it names no live row)."""
        k = str(key).strip()
        u = self.legacy_to_uuid.get(k)
        return u if u and u in self._keys else k

    def canonical_item_id(self, item_id: str) -> str:
        """A proposal id "<key>|<column>" with its key made canonical (legacy -> UUID)."""
        key, sep, rest = str(item_id).partition("|")
        return self.canonical_key(key) + sep + rest if sep else str(item_id)

    @cached_property
    def _keys(self) -> set:
        return {self.key_of(r) for r in self.data} - {""}

    def row_by_id(self) -> "KeyedMap":
        """key -> raw row. Keyed by UUID; a legacy id resolves on lookup (get / [] / in)
        but is never listed, so keys() / values() / items() hold each row once."""
        return KeyedMap(((self.key_of(r), r) for r in self.data if self.key_of(r)),
                        alias=self.legacy_to_uuid)

    def sheet_row_map(self) -> "KeyedMap":
        """key -> live Google Sheet tab row (1-based); legacy ids resolve like row_by_id.

        The backend pull is 1:1 with the sheet, so live row = CSV line
        index + 1. Use this whenever a row is reported to a human.
        """
        return KeyedMap(((self.key_of(self.rows[i]), i + 1)
                         for i in range(self.data_start, len(self.rows))
                         if self.key_of(self.rows[i])),
                        alias=self.legacy_to_uuid)

    def map_rows(self, fn) -> "KeyedMap":
        """{key: fn(row)} over keyed rows, as a KeyedMap (legacy ids resolve on lookup)."""
        return KeyedMap(((k, fn(r)) for k, r in dict.items(self.row_by_id())),
                        alias=self.legacy_to_uuid)

    @cached_property
    def _uuid_to_legacy(self) -> dict:
        return {u: lid for lid, u in self.legacy_to_uuid.items()}

    def legacy_of(self, row: list) -> str:
        """The row's old "original order in sheet" id, or "" (rows added since have none)."""
        return self._uuid_to_legacy.get(self.key_of(row), "") or self.cell(row, self.colmap.get("legacy_row_id"))

    def rows_by_sheet_row(self, spec: str) -> list:
        """Data rows whose LIVE sheet row falls in a range/list spec ("1100-1220,5")."""
        want = parse_row_spec(spec)
        return [r for i, r in enumerate(self.data, start=self.data_start + 1) if i in want]


class KeyedMap(dict):
    """A UUID-keyed dict that also answers to legacy "original order" ids.

    Lookups (``m[k]``, ``m.get(k)``, ``k in m``) translate a legacy id through
    ``alias`` when it is not itself a key; iteration and len() see only the real
    keys, so no row is ever counted twice. Plain assignment adds real keys.
    """

    def __init__(self, items=(), alias=None):
        super().__init__(items)
        self._alias = alias or {}

    def _k(self, key):
        k = str(key).strip() if key is not None else key
        if dict.__contains__(self, k):
            return k
        a = self._alias.get(k)
        return a if a is not None and dict.__contains__(self, a) else k

    def __getitem__(self, key):
        return dict.__getitem__(self, self._k(key))

    def __contains__(self, key):
        return dict.__contains__(self, self._k(key))

    def get(self, key, default=None):
        return dict.get(self, self._k(key), default)

    def __setitem__(self, key, value):
        dict.__setitem__(self, self._k(key), value)


LEGACY_MAP = Path(__file__).resolve().parent.parent / "data" / "legacy_row_ids.csv"


def load_legacy_map(path: Path = LEGACY_MAP) -> dict:
    """data/legacy_row_ids.csv -> {legacy_row_id: uuid}; {} if the file is absent."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8", newline="") as f:
        return {r["legacy_row_id"].strip(): r["uuid"].strip() for r in csv.DictReader(f)}


def parse_row_spec(spec: str) -> set:
    """"1100-1220,5" -> {1100..1220, 5}; "" -> empty set."""
    out = set()
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def load_colmap(csv_path: str | Path) -> dict:
    """Load the .colmap.json sibling of a backend CSV, or raise BackendNotPulled."""
    map_path = Path(csv_path).with_suffix(".colmap.json")
    if not map_path.exists():
        raise BackendNotPulled(
            f"{map_path} not found — run `python scripts/pull_backend.py` "
            f"first to pull the backend and derive the column map."
        )
    return json.loads(map_path.read_text())


def load_backend(csv_path: str | Path | None = None) -> Backend:
    """Load the backend CSV + colmap (default: work/backend.csv)."""
    path = Path(csv_path) if csv_path else backend_csv_path()
    if not path.exists():
        raise BackendNotPulled(
            f"{path} not found — run `python scripts/pull_backend.py` first "
            f"to pull a fresh backend CSV (mandatory at the start of a batch)."
        )
    colmap = load_colmap(path)
    with open(path, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    return Backend(path=path, rows=rows, colmap=colmap)


# ---------------------------------------------------------------------------
# Backend date parsing
# ---------------------------------------------------------------------------

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


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


def contract_month(s: str) -> str:
    """
    Normalize the backend's contract-date formats to "YYYY-MM" (or "YYYY-00"
    for a bare year, "" when unparseable). Accepts everything parse_date does
    plus month-only forms: "2026-03", "Dec 2025", "2026".
    """
    s = (s or "").strip()
    if not s:
        return ""
    full = parse_date(s)
    if full and full[1] >= 1:
        return f"{full[0]}-{full[1]:02d}"
    # YYYY-MM (no day)
    m = re.match(r"(\d{4})-(\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    # MMM YYYY
    m = re.match(r"([A-Za-z]{3})\s+(\d{4})", s)
    if m:
        mon = _MONTHS.get(m.group(1).lower(), 0)
        if mon:
            return f"{m.group(2)}-{mon:02d}"
    # Just a year
    m = re.match(r"(\d{4})$", s)
    if m:
        return f"{m.group(1)}-00"
    return ""
