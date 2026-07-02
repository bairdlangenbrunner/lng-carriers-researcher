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
    be.row_by_id()                     # row_id -> raw row
    be.sheet_row_map()                 # row_id -> live 1-based sheet row

Row identity note (report-live-rows rule): ``row_id`` is column A ("original
order in sheet") — a static stamp that drifts from the live tab row as rows
are deleted. Humans navigate the live sheet, so anything reported to a human
uses ``sheet_row_map()`` / the CSV line position, never the column-A id.

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

    def row_by_id(self) -> dict:
        """row_id (column A stamp) -> raw row."""
        ri = self.colmap["row_id"]
        return {r[ri].strip(): r for r in self.data
                if len(r) > ri and r[ri].strip()}

    def sheet_row_map(self) -> dict:
        """row_id -> live Google Sheet tab row (1-based).

        The backend pull is 1:1 with the sheet, so live row = CSV line
        index + 1. Use this whenever a row is reported to a human.
        """
        ri = self.colmap["row_id"]
        out = {}
        for idx in range(self.data_start, len(self.rows)):
            r = self.rows[idx]
            if len(r) > ri and r[ri].strip():
                out[r[ri].strip()] = idx + 1
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
