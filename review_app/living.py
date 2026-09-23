"""
The living workbook — the reconciliation's reference copy on the work Drive, kept in step
with what the backend actually holds.

One Google Sheet (converted from the combined workbook's xlsx) in the work Drive folder
`claude-output`, created once and updated in place, so its URL is stable and can be shared.
Two of its tabs carry a `processed` column that this module writes:

  all_proposals                    one line per proposed cell, keyed by `line id`
                                   ("<batch dir>::<decision id>", the review app's own key)
  remaining_changes_backend_shape  one row per vessel, keyed by `line key`
                                   ("row:<row_id>", or "cluster:<batch>:<cluster_id>" for a
                                   discovery row that is not in the backend yet)

Both key columns are written by `build_combined.py`; the sync reads them live, so sorting or
filtering the sheet never puts a `processed` value on the wrong line.

What `processed` means (PROCESSED_VALUES):

  processed - incorporated   the pulled backend holds the proposal — value and refs (the same
                             `in_backend` test the review app's "in the backend" flag uses), or,
                             for a suggestion, the backend holds the suggested value
  processed - rejected       someone rejected the line (apply_batch never pre-fills a reject, so
                             a reject in decisions.csv is always a person's call)
  (blank)                    still open: undecided, on hold, accepted but not yet written, a
                             suggestion whose value is not in the backend, or a value in the
                             backend whose proposed ref is not

A backend-shape row is `processed - incorporated` when every line the pass proposed for that
vessel is settled and at least one was incorporated, `processed - rejected` when all of them
were rejected, `partly processed - N of M` while some are still open, else blank. It counts
every line of that vessel, including ones the sheet does not draw (a landed or rejected cell is
left off the backend shape by design).

THE ONLY CELLS THIS MODULE EVER WRITES are those two `processed` columns: `plan()` refuses a
range outside them. It does not touch the backend sheet, and it is not on the backend's write
path — `push.py` is (AP §2b). A failure here never fails a push or a sync.

    python review_app/living.py --create [--xlsx <path>]   # once: upload + record data/living_workbook.json
    python review_app/living.py --sync [--dry-run]         # write the processed columns
    python review_app/living.py --rebuild [--xlsx <path>]  # replace the content, same file id / URL
"""
import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "scripts", ROOT / "review_app"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import store  # noqa: E402
from pull_backend import DEFAULT_SPREADSHEET_ID  # noqa: E402
from review_data import _same  # noqa: E402

ET = ZoneInfo("America/New_York")
CONFIG_PATH = ROOT / "data" / "living_workbook.json"
# the work Drive folder Baird named for this (shared drive "GEM", folder "claude-output")
FOLDER_ID = "1DnF6niKeRnbRyhVcmJDy7UkeZLjNGc4r"
DEFAULT_NAME = "living-workbook-for-update"
SHEET_MIME = "application/vnd.google-apps.spreadsheet"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

PROPOSALS_SHEET = "all_proposals"
SHAPE_SHEET = "remaining_changes_backend_shape"
PROCESSED = "processed"
LINE_ID = "line id"        # all_proposals key column
LINE_KEY = "line key"      # remaining_changes_backend_shape key column

INCORPORATED = "processed - incorporated"
REJECTED = "processed - rejected"
PARTLY = "partly processed - {n} of {m}"
PROCESSED_VALUES = (INCORPORATED, REJECTED)

GWS_READ_ENV = {
    "GOOGLE_WORKSPACE_CLI_CONFIG_DIR": str(Path.home() / ".config" / "gws-gem"),
    "GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND": "file",
}
GWS_WRITE_ENV = {
    "GOOGLE_WORKSPACE_CLI_CONFIG_DIR": str(Path.home() / ".config" / "gws-gem-write"),
    "GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND": "file",
}
HEADER_SCAN = 5      # rows searched for the header row of a tab


class LivingError(RuntimeError):
    """The living workbook could not be read or written (never fatal to a push or a sync)."""


def _backend_spreadsheet_id():
    """The backend sheet's id, same resolution as review_app/push.py `write_sheet`."""
    return os.environ.get("LNGCT_BACKEND_SHEET_ID", DEFAULT_SPREADSHEET_ID)


def _refuse_if_backend(spreadsheet_id, where):
    """Guard: the living workbook must never BE the backend sheet — `rebuild` overwrites a
    file's entire content, and even `sync`'s narrower batchUpdate would be writing into the
    live backend, not a copy of it. Checked before any write to `spreadsheet_id`."""
    backend_id = _backend_spreadsheet_id()
    if spreadsheet_id and backend_id and spreadsheet_id == backend_id:
        raise LivingError(
            f"refusing to {where}: the living-workbook spreadsheet id ({spreadsheet_id}) is "
            f"the BACKEND sheet's id — this would write over the live backend, not a copy of "
            f"it. Check data/living_workbook.json and LNGCT_BACKEND_SHEET_ID.")


# ---- gws plumbing ------------------------------------------------------------------

def _gws(args, env, timeout=300):
    """A `gws` subcommand; parsed JSON. The CLI prints a keyring preamble before the body."""
    try:
        r = subprocess.run(["gws", *args], env={**os.environ, **env},
                           capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise LivingError(f"gws {args[0]} {args[1]} failed: {e}") from e
    if r.returncode != 0:
        tail = (r.stderr.strip().splitlines() or r.stdout.strip().splitlines() or ["no output"])[-1]
        raise LivingError(f"gws {args[0]} {args[1]} failed: {tail}")
    out = r.stdout
    if "{" not in out:
        raise LivingError(f"gws {args[0]} {args[1]} returned no JSON: {out.strip()[:200]}")
    try:
        return json.loads(out[out.index("{"):])
    except ValueError as e:
        raise LivingError(f"gws {args[0]} {args[1]} returned unparseable JSON: {e}") from e


def col_letter(i):
    """0-based column index -> A1 letters."""
    letters, n = "", i + 1
    while n:
        n, r = divmod(n - 1, 26)
        letters = chr(65 + r) + letters
    return letters


def quoted(title):
    return "'" + title.replace("'", "''") + "'"


# ---- config ------------------------------------------------------------------------

def load_config(path=None):
    p = Path(path or os.environ.get("LNGCT_LIVING_CONFIG") or CONFIG_PATH)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        raise LivingError(f"{p} is not valid JSON: {e}") from e


def save_config(cfg, path=None):
    p = Path(path or os.environ.get("LNGCT_LIVING_CONFIG") or CONFIG_PATH)
    p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


# ---- what "processed" means --------------------------------------------------------

def line_state(p):
    """The `processed` value for one proposal line ("" while it is still open)."""
    if "in_backend" in (p.get("flags") or []):
        return INCORPORATED
    decision = p.get("decision")
    if decision == "suggest":
        s = p.get("suggestion") or {}
        # the flags compare the batch's proposal; a suggestion lands as the reviewer's own value
        return INCORPORATED if s.get("value") and _same(p.get("current", ""), s["value"]) else ""
    if decision == "reject":
        return REJECTED
    return ""


def row_key(p):
    """The backend-shape key of the vessel a proposal belongs to."""
    return f"row:{p['row_id']}" if p.get("row_id") else f"cluster:{p['batch']}:{p['cluster_id']}"


def row_state(states):
    """The `processed` value for a vessel, from its lines' states."""
    if not states:
        return ""
    done = [s for s in states if s]
    if len(done) < len(states):
        return PARTLY.format(n=len(done), m=len(states)) if done else ""
    return INCORPORATED if any(s == INCORPORATED for s in done) else REJECTED


def states(data, dirs):
    """{PROPOSALS_SHEET: {line id: value}, SHAPE_SHEET: {line key: value}} for the current
    decisions laid over `data` — pure, no network."""
    cur = store.overlay(data, dirs)["proposals"]
    lines = {key: line_state(p) for key, p in cur.items()}
    by_row = defaultdict(list)
    for key, p in cur.items():
        by_row[row_key(p)].append(lines[key])
    return {PROPOSALS_SHEET: lines,
            SHAPE_SHEET: {k: row_state(v) for k, v in by_row.items()}}


# ---- reading and writing the sheet -------------------------------------------------

def read_tab(sid, title, key_column, env=None):
    """(header_row, processed column index, [(sheet row, key, current processed value)]).

    Two small reads: the top rows to locate the header, then just the key and `processed`
    columns — never the whole tab."""
    head = _gws(["sheets", "spreadsheets", "values", "get", "--params",
                 json.dumps({"spreadsheetId": sid,
                             "range": f"{quoted(title)}!A1:BZ{HEADER_SCAN}"})],
                env or GWS_READ_ENV).get("values", [])
    for n, row in enumerate(head, 1):
        if key_column in row and PROCESSED in row:
            hrow, i_key, i_proc = n, row.index(key_column), row.index(PROCESSED)
            break
    else:
        raise LivingError(f"{title!r} has no {key_column!r} + {PROCESSED!r} header in its first "
                          f"{HEADER_SCAN} rows — rebuild the living workbook (--rebuild)")
    k_a1 = f"{quoted(title)}!{col_letter(i_key)}{hrow + 1}:{col_letter(i_key)}"
    p_a1 = f"{quoted(title)}!{col_letter(i_proc)}{hrow + 1}:{col_letter(i_proc)}"
    got = _gws(["sheets", "spreadsheets", "values", "batchGet", "--params",
                json.dumps({"spreadsheetId": sid, "ranges": [k_a1, p_a1],
                            "valueRenderOption": "FORMATTED_VALUE"})],
               env or GWS_READ_ENV).get("valueRanges", [])
    keys = [(r or [""])[0] for r in (got[0].get("values") or [])] if got else []
    procs = [(r or [""])[0] for r in (got[1].get("values") or [])] if len(got) > 1 else []
    procs += [""] * (len(keys) - len(procs))
    rows = [(hrow + 1 + n, str(k).strip(), str(procs[n]).strip()) for n, k in enumerate(keys)]
    return hrow, i_proc, rows


def plan(title, i_proc, rows, want):
    """The `processed` cells to write: [(a1 range, [[v], ...])] over contiguous runs.

    A key the current dataset does not know is left alone (the workbook may be older than the
    batch set being reviewed). Nothing outside column `i_proc` is ever produced."""
    letter = col_letter(i_proc)
    changed = [(r, want[k]) for r, k, cur in rows if k in want and want[k] != cur]
    out, run = [], []
    for r, v in changed:
        if run and r == run[-1][0] + 1:
            run.append((r, v))
            continue
        if run:
            out.append((f"{quoted(title)}!{letter}{run[0][0]}:{letter}{run[-1][0]}",
                        [[v] for _r, v in run]))
        run = [(r, v)]
    if run:
        out.append((f"{quoted(title)}!{letter}{run[0][0]}:{letter}{run[-1][0]}",
                    [[v] for _r, v in run]))
    return out


def write_cells(sid, ranges, env=None):
    """values.batchUpdate the planned ranges, RAW (the labels are text)."""
    if not ranges:
        return 0
    body = {"valueInputOption": "RAW",
            "data": [{"range": a1, "values": vals} for a1, vals in ranges]}
    got = _gws(["sheets", "spreadsheets", "values", "batchUpdate", "--params",
                json.dumps({"spreadsheetId": sid}), "--json", json.dumps(body)],
               env or GWS_WRITE_ENV)
    return got.get("totalUpdatedCells", sum(len(v) for _a, v in ranges))


# ---- the sync ----------------------------------------------------------------------

class Living:
    """The configured living workbook. `read` / `write` are injectable so the sync can be
    tested without a network."""

    def __init__(self, config, read=None, write=None):
        self.config = config
        self.id = config["spreadsheet_id"]
        _refuse_if_backend(self.id, "sync the living workbook")
        self.url = config.get("url") or f"https://docs.google.com/spreadsheets/d/{self.id}/edit"
        self.tabs = [(PROPOSALS_SHEET, LINE_ID), (SHAPE_SHEET, LINE_KEY)]
        self._read = read or (lambda title, key: read_tab(self.id, title, key))
        self._write = write or (lambda ranges: write_cells(self.id, ranges))

    def matches(self, dirs):
        """True when the batches being reviewed are the ones this workbook was built from.

        The workbook belongs to one reconciliation; a session over other batch dirs must not
        write its `processed` columns."""
        known = set(self.config.get("batches") or [])
        return bool(known) and bool(known & set(dirs))

    def sync(self, data, dirs, dry_run=False):
        """Write each tab's `processed` column from the current decisions. Returns a summary;
        raises LivingError."""
        want = states(data, dirs)
        out = {"spreadsheet_id": self.id, "url": self.url, "name": self.config.get("name", ""),
               "written": 0, "tabs": {}, "dry_run": bool(dry_run)}
        for title, key_column in self.tabs:
            _hrow, i_proc, rows = self._read(title, key_column)
            ranges = plan(title, i_proc, rows, want[title])
            n = sum(len(v) for _a, v in ranges)
            if ranges and not dry_run:
                self._write(ranges)
            out["tabs"][title] = {"rows": len(rows), "changed": n,
                                  "unknown": sum(1 for _r, k, _c in rows if k and k not in want[title])}
            out["written"] += n
        out["synced"] = datetime.now(ET).isoformat(timespec="seconds")
        return out


def from_config(dirs=None, path=None, read=None, write=None):
    """The configured Living, or None when there is none, it is switched off
    (LNGCT_LIVING_SYNC=0), or `dirs` is not the reconciliation it belongs to."""
    if os.environ.get("LNGCT_LIVING_SYNC", "").strip() in ("0", "off", "no"):
        return None
    cfg = load_config(path)
    if not cfg or not cfg.get("spreadsheet_id"):
        return None
    living = Living(cfg, read=read, write=write)
    if dirs is not None and not living.matches(dirs):
        return None
    return living


# ---- creating / rebuilding the workbook --------------------------------------------

def newest_combined(xlsx=None):
    """The combined workbook to upload: the newest built file, or the given path."""
    if xlsx:
        p = Path(xlsx)
        if not p.exists():
            raise LivingError(f"{p} not found")
        return p
    found = sorted(ROOT.glob("batches/*/lng_carrier_*_results_*.xlsx"),
                   key=lambda p: p.stat().st_mtime)
    if not found:
        raise LivingError("no combined results workbook found — build one first "
                          "(batches/*/build_combined.py)")
    return found[-1]


def _batch_dirs(xlsx):
    """The batch dirs the workbook covers, from its own dir's review_batches.json."""
    info = xlsx.parent / "review_batches.json"
    if info.exists():
        try:
            return sorted(json.loads(info.read_text(encoding="utf-8")))
        except ValueError:
            pass
    return []


def create(xlsx=None, folder_id=FOLDER_ID, name=DEFAULT_NAME, config_path=None, env=None):
    """Upload the combined workbook as a NEW Google Sheet in `folder_id`; record the config."""
    src = newest_combined(xlsx)
    meta = {"name": name, "parents": [folder_id], "mimeType": SHEET_MIME}
    got = _gws(["drive", "files", "create",
                "--params", json.dumps({"supportsAllDrives": True,
                                        "fields": "id,name,webViewLink,mimeType,parents"}),
                "--json", json.dumps(meta),
                "--upload", str(src), "--upload-content-type", XLSX_MIME],
               env or GWS_WRITE_ENV)
    if got.get("mimeType") != SHEET_MIME:
        raise LivingError(f"Drive did not convert the upload to a Google Sheet (got "
                          f"{got.get('mimeType')!r}) — nothing is configured")
    cfg = {"spreadsheet_id": got["id"], "name": got.get("name", name),
           "url": got.get("webViewLink", ""), "folder_id": folder_id,
           "source_workbook": str(src.relative_to(ROOT)), "batches": _batch_dirs(src),
           "tabs": {PROPOSALS_SHEET: LINE_ID, SHAPE_SHEET: LINE_KEY},
           "created": datetime.now(ET).isoformat(timespec="seconds")}
    save_config(cfg, config_path)
    return cfg


def rebuild(xlsx=None, config_path=None, env=None):
    """Replace the living workbook's content with a freshly built combined workbook, keeping
    the same file id and URL. The `processed` columns come back on the next sync."""
    cfg = load_config(config_path)
    if not cfg or not cfg.get("spreadsheet_id"):
        raise LivingError("no living workbook configured — run --create first")
    _refuse_if_backend(cfg["spreadsheet_id"], "rebuild the living workbook")
    src = newest_combined(xlsx)
    got = _gws(["drive", "files", "update",
                "--params", json.dumps({"fileId": cfg["spreadsheet_id"], "supportsAllDrives": True,
                                        "fields": "id,name,mimeType,modifiedTime"}),
                "--upload", str(src), "--upload-content-type", XLSX_MIME],
               env or GWS_WRITE_ENV)
    if got.get("mimeType") != SHEET_MIME:
        raise LivingError(f"the file is no longer a Google Sheet ({got.get('mimeType')!r})")
    cfg.update({"source_workbook": str(src.relative_to(ROOT)), "batches": _batch_dirs(src),
                "rebuilt": datetime.now(ET).isoformat(timespec="seconds")})
    save_config(cfg, config_path)
    return cfg


# ---- CLI ----------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--create", action="store_true", help="upload a new living workbook and record it")
    ap.add_argument("--rebuild", action="store_true", help="replace its content, same file id / URL")
    ap.add_argument("--sync", action="store_true", help="write the processed columns")
    ap.add_argument("--dry-run", action="store_true", help="--sync without writing")
    ap.add_argument("--xlsx", default=None, help="combined workbook (default: the newest built)")
    ap.add_argument("--folder", default=FOLDER_ID)
    ap.add_argument("--name", default=DEFAULT_NAME)
    ap.add_argument("--data", default=None, help="review dataset (default: work/review_data.json)")
    ap.add_argument("--batches", nargs="+", default=None, help="batch dirs for --sync")
    args = ap.parse_args(argv)
    if not (args.create or args.rebuild or args.sync):
        ap.error("pass --create, --rebuild or --sync")
    if args.create:
        cfg = create(args.xlsx, args.folder, args.name)
        print(f"living workbook: {cfg['url']}\n  {cfg['spreadsheet_id']}  "
              f"from {cfg['source_workbook']}  ({len(cfg['batches'])} batches)")
    if args.rebuild:
        cfg = rebuild(args.xlsx)
        print(f"living workbook rebuilt from {cfg['source_workbook']}: {cfg['url']}")
    if args.sync:
        import review_data
        from paths import work_dir
        data_path = Path(args.data) if args.data else work_dir() / "review_data.json"
        if args.batches:
            dirs = {Path(d).name: Path(d) for d in review_data.resolve_dirs(args.batches)}
        else:
            data = json.loads(data_path.read_text(encoding="utf-8"))
            dirs = {b["dir"]: ROOT / "batches" / b["dir"] for b in data["batches"]}
        data = json.loads(data_path.read_text(encoding="utf-8"))
        living = from_config()
        if living is None:
            raise SystemExit("no living workbook configured (or LNGCT_LIVING_SYNC=0)")
        out = living.sync(data, dirs, dry_run=args.dry_run)
        for title, t in out["tabs"].items():
            print(f"  {title}: {t['changed']} of {t['rows']} rows"
                  + (f", {t['unknown']} keys not in this dataset" if t["unknown"] else ""))
        print(("would write " if args.dry_run else "wrote ") + f"{out['written']} cells — {out['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
