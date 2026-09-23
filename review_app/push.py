"""
Push changes — accepted lines and suggestions — into the backend sheet: the one place the
review app writes the backend.

Never on a click of `accept` or a submitted suggestion: the reviewer presses **push changes**, the server pulls the
backend fresh, computes the plan (every cell that would change: live row, column, old -> new),
the page shows it, and one confirmation writes it. The confirmation carries the plan's token; the
server pulls again, recomputes, and refuses when the plan is no longer the one that was shown
(the sheet or a decision changed in between). After the write it pulls once more and verifies
every cell, as verify_apply.py does.

Only a line a reviewer clicked accept on is pushed: its latest review_log.jsonl record is an
accept by a person. An accept that apply_batch pre-filled by the computed grade (RF §5 rev 28),
one typed into decisions.csv, or one a machine set — the backend sync, a §5 regrade
(store.MACHINE_REVIEWERS) — was never clicked: it is counted (`unclicked`) and left alone.

What is pushed: clicked-accept value / [ref] lines, computed by apply_batch.cell_writes — the same
cells apply_patch.csv would carry — laid over the pull in apply order, so a later batch's value
wins and appended refs accumulate; and **suggestions** (a reviewer's own value in place of the
proposal, stored as reject in decisions.csv): the suggested value with the refs typed alongside
it (else the proposal's), each ref first passed through the §3.8c gate against that value
(igu_refs.corroborates_cell, as build_workbook --mode fix does) — a fix cell, so passing refs
replace the paired [ref]; a cosmetic suggestion keeps the cell's [ref]; a suggestion no ref
corroborates is listed as not pushed. What is not (they stay on the Apply SOP's by-hand path):
discovery new rows, conflicts, and a data-fill / ref-fill value whose cell is no longer blank or `unknown` (additive to blanks
holds — that is a conflict). Lines of an already-applied batch whose cell differs from the
accepted value are planned separately and left out unless the reviewer includes them: there the
difference is more likely a later hand edit than a missed apply. Reject writes nothing.

Cells are addressed by row_id + header name against the fresh pull, never by a stored offset.
Writes go through the `gws` CLI under the work WRITE profile (~/.config/gws-gem-write).
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import store  # noqa: E402
import suggestions  # noqa: E402
from apply_batch import _detect, _items_and_conflicts, cell_writes  # noqa: E402
from backend_io import load_backend  # noqa: E402
from pull_backend import DEFAULT_GID, DEFAULT_SPREADSHEET_ID, resolve_tab_title  # noqa: E402
from review_data import _norm, _same  # noqa: E402

GWS_WRITE_ENV = {
    "GOOGLE_WORKSPACE_CLI_CONFIG_DIR": str(Path.home() / ".config" / "gws-gem-write"),
    "GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND": "file",
}
CHUNK = 200   # ValueRanges per values.batchUpdate call
GATE = None   # (url, value, field, imo) -> (ok, reason); igu_refs.corroborates_cell unless a test swaps it
_GATE_CACHE = {}


def gate(url, value, field, imo):
    """§3.8c for a suggestion's ref, cached for the process (a plan is computed twice: shown, then
    recomputed on confirm) — the IGU landing page gates and is cited as its PDF (IG §1)."""
    global GATE
    if GATE is None:
        from igu_refs import corroborates_cell
        GATE = corroborates_cell
    from url_verifier import citable_form
    url = citable_form(url)
    k = (url, str(value), field, str(imo or ""))
    if k not in _GATE_CACHE:
        _GATE_CACHE[k] = (url,) + tuple(GATE(url, value, field, imo))
    return _GATE_CACHE[k]


def suggestion_item(p, mode, row, H):
    """The fix-style item a suggestion writes, or (None, why). The reviewer's refs (else the
    proposal's) are gated against the suggested value; a cosmetic suggestion keeps the [ref]."""
    cell, rep = suggestions.cell_for(p, mode, p["last"])
    if cell is None:
        return None, rep[1]
    imo_i = H.get("IMO number")
    imo = row[imo_i] if imo_i is not None and len(row) > imo_i else ""
    kept, verdicts = [], []
    if not cell.get("preserve_ref"):
        gate_value = str(cell.get("gate_value") or cell["new_value"])
        for r in cell.get("refs", []):
            url, ok, reason = gate(r["url"], gate_value, cell["field"], imo)
            if ok and url not in kept:
                kept.append(url)
            elif not ok:
                verdicts.append(f"{url}: {reason}")
        if not kept:
            return None, ("no ref corroborates the suggested value (§3.8c) — add a source in the suggestion"
                          + (": " + "; ".join(verdicts) if verdicts else ""))
    return {"id": p["id"], "kind": "fill", "row_id": p["row_id"], "cluster_id": "", "column": cell["field"],
            "value": cell["new_value"], "ref_column": f"{cell['field']} [ref]" if kept else "",
            "ref_value": ", ".join(kept), "confidence": cell["confidence"], "derivable": False,
            "note": cell["note"], "prev_state": "fix", "replace_ref": not cell.get("append_ref"),
            "row_data": None}, None


class PushFailed(RuntimeError):
    """The sheet write did not (fully) happen — HTTP 502."""


class PlanChanged(RuntimeError):
    """The plan the reviewer confirmed is no longer the plan — HTTP 409, nothing written."""


def a1(col_idx, row):
    letters, n = "", col_idx + 1
    while n:
        n, r = divmod(n - 1, 26)
        letters = chr(65 + r) + letters
    return f"{letters}{row}"


def token(writes):
    doc = [[w["row_id"], w["column"], w["old"], w["new"]] for w in writes]
    return hashlib.sha256(json.dumps(doc, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def clicked(p):
    """A reviewer clicked accept on this line: its latest log record is a person's accept."""
    return store.reviewed(p.get("last"), p.get("decision")) == "accept"


def plan(data, dirs, backend_path=None, batch=None):
    """{"writes": [...], "applied_writes": [...], "skipped": [...], "unclicked": n, "token",
    "token_all"} against
    the backend csv as pulled. Read-only (the §3.8c gate on a suggestion's refs fetches, cached).
    `batch` (a dir name) keeps only that batch's cells —
    every batch is still laid over the pull, so a cell a later batch also sets belongs to the
    later batch and is left to its push. A write carries `suggest: true` when it comes from a
    suggestion rather than an accepted line; a skip carries the line's `decision`."""
    be = load_backend(backend_path)
    H = be.header_index
    orig = be.row_by_id()
    work = {rid: list(r) + [""] * (len(be.header) - len(r)) for rid, r in orig.items()}
    srm = be.sheet_row_map()
    current = store.overlay(data, dirs)["proposals"]
    name_i = H.get("Name")

    source, skipped = {}, []      # (row_id, column) -> the line that last set it
    unclicked = 0                 # accept in decisions.csv, never clicked, not yet in the backend

    suggested = set()             # keys written from a suggestion

    def skip(key, p, why):
        skipped.append({"key": key, "batch": p["batch"], "row_id": p["row_id"], "decision": p["decision"],
                        "live_row": srm.get(p["row_id"]), "column": p["column"], "why": why})

    for b in sorted(data["batches"], key=lambda b: (b["apply_order"], b["dir"])):
        if b["dir"] not in dirs:
            continue
        mode, payload = _detect(dirs[b["dir"]])
        items, _ = _items_and_conflicts(mode, payload, be.header, be.colmap)
        for it in items:
            key = f"{b['dir']}::{it['id']}"
            p = current.get(key)
            if not p or p["decision"] not in ("accept", "suggest"):
                continue
            if p["decision"] == "suggest":
                # a suggestion is a person's record by construction (the sync never writes one)
                if it["kind"] == "new_row":
                    skip(key, p, "new row — a suggestion on it is decided by hand (Apply SOP)")
                    continue
                row = work.get(it["row_id"])
                if row is None:
                    skip(key, p, "row is no longer in the backend")
                    continue
                it, why = suggestion_item(p, mode, row, H)
                if it is None:
                    skip(key, p, why)
                    continue
                if str(it["value"]).lstrip().startswith("="):
                    skip(key, p, "value starts with '=' (the sheet would read a formula)")
                    continue
                for column, value in cell_writes(it, H, row):
                    row[H[column]] = value
                    source[(it["row_id"], column)] = (key, b)
                suggested.add(key)
                continue
            if not clicked(p):
                if not {"in_backend", "value_in_backend"} & set(p["flags"]) and (not batch or b["dir"] == batch):
                    unclicked += 1
                continue
            if it["kind"] == "new_row":
                if "in_backend" not in p["flags"]:
                    skip(key, p, "new row — added by hand (Apply SOP)")
                continue
            row = work.get(it["row_id"])
            if row is None:
                skip(key, p, "row is no longer in the backend")
                continue
            if it["kind"] == "fill" and not it.get("ref_only") and it["column"] in H:
                cur = row[H[it["column"]]]
                if str(it["value"]).lstrip().startswith("="):
                    skip(key, p, "value starts with '=' (the sheet would read a formula)")
                    continue
                if it.get("prev_state") != "fix" and _norm(cur) and _norm(cur).lower() != "unknown" \
                        and not _same(cur, it["value"]):
                    skip(key, p, f"cell is no longer blank (holds {_norm(cur)!r}) — a conflict, decided by hand")
                    continue
            for column, value in cell_writes(it, H, row):
                row[H[column]] = value
                source[(it["row_id"], column)] = (key, b)

    writes, applied_writes = [], []
    for (rid, column), (key, b) in source.items():
        i = H[column]
        old = orig[rid][i] if len(orig[rid]) > i else ""
        new = work[rid][i]
        if _same(old, new):
            continue
        w = {"row_id": rid, "live_row": srm[rid], "column": column, "a1": a1(i, srm[rid]),
             "old": old, "new": new, "key": key, "batch": b["dir"], "label": b["label"], "suggest": key in suggested,
             "name": orig[rid][name_i] if name_i is not None and len(orig[rid]) > name_i else ""}
        if batch and b["dir"] != batch:
            continue
        (applied_writes if b["applied"] else writes).append(w)
    order = lambda w: (w["live_row"], H[w["column"]])
    writes.sort(key=order)
    applied_writes.sort(key=order)
    if batch:
        skipped = [x for x in skipped if x["batch"] == batch]
    return {"writes": writes, "applied_writes": applied_writes, "skipped": skipped,
            "unclicked": unclicked, "batch": batch,
            "token": token(writes), "token_all": token(writes + applied_writes)}


def sheet_value(v):
    if re.fullmatch(r"-?(0|[1-9]\d*)", v):
        return int(v)
    if re.fullmatch(r"-?(0|[1-9]\d*)\.\d+", v):
        return float(v)
    return v


def write_sheet(writes):
    """values.batchUpdate the planned cells. RAW, so the sheet parses nothing (`2027-03` stays
    text, not a date); a plain number is sent as a number, as if typed. Raises PushFailed;
    chunks already sent stay written — push() reports what landed."""
    sid = os.environ.get("LNGCT_BACKEND_SHEET_ID", DEFAULT_SPREADSHEET_ID)
    gid = int(os.environ.get("LNGCT_BACKEND_GID", DEFAULT_GID))
    title = resolve_tab_title(sid, gid).replace("'", "''")
    for n in range(0, len(writes), CHUNK):
        chunk = writes[n:n + CHUNK]
        body = {"valueInputOption": "RAW",
                "data": [{"range": f"'{title}'!{w['a1']}", "values": [[sheet_value(w["new"])]]} for w in chunk]}
        r = subprocess.run(
            ["gws", "sheets", "spreadsheets", "values", "batchUpdate",
             "--params", json.dumps({"spreadsheetId": sid}), "--json", json.dumps(body)],
            env={**os.environ, **GWS_WRITE_ENV}, capture_output=True, text=True)
        if r.returncode != 0:
            raise PushFailed(f"sheet write failed after {n} of {len(writes)} cells: "
                             + (r.stderr.strip().splitlines() or ["no output"])[-1])


def log(writes, dirs, reviewer):
    """Append each written cell to its batch's push_log.jsonl (commit it with the batch)."""
    ts = store.now()
    by_batch = {}
    for w in writes:
        by_batch.setdefault(w["batch"], []).append(
            {"key": w["key"], "row_id": w["row_id"], "live_row": w["live_row"], "column": w["column"],
             "old": w["old"], "new": w["new"], "reviewer": reviewer, "ts": ts})
    for b, recs in by_batch.items():
        store.append_jsonl(dirs[b] / "push_log.jsonl", recs)


def verify(writes, backend_path=None):
    """The written cells that do not hold their value in the (re-pulled) backend."""
    be = load_backend(backend_path)
    rows, H = be.row_by_id(), be.header_index
    bad = []
    for w in writes:
        r, i = rows.get(w["row_id"]), H.get(w["column"])
        got = r[i] if r is not None and i is not None and len(r) > i else ""
        if not _same(got, w["new"]):
            bad.append(dict(w, got=got))
    return bad
