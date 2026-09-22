"""
The review app's decision store over the batch dirs (phase 1).

Reads each batch's `decisions.csv` (the store the pipeline reads) and the append-only audit
sidecar `review_log.jsonl`, and lays the current state over the built dataset. Nothing here
touches the backend.
"""
import csv
import io
import json
import re
import os
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
DECISIONS = ("accept", "hold", "reject", "suggest")
SUGGEST_KINDS = ("value", "cosmetic")
# suggest is stored as reject in decisions.csv: the value as proposed is not wanted; its
# replacement (the suggested value + the reviewer's refs) is written by the app's push
# (push.py, gated) or built into a fix batch (suggestions.py)
CSV_DECISION = {"accept": "accept", "hold": "hold", "reject": "reject", "suggest": "reject"}


class Invalid(ValueError):
    """A request the store refuses before writing anything (HTTP 400)."""


def read_jsonl(path):
    """Records of a JSONL file; a torn last line (crash mid-append) is skipped, not fatal."""
    out = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def latest(records, field="key"):
    """field value -> the last record carrying it (the log is append-only; latest wins)."""
    out = {}
    for r in records:
        if r.get(field):
            out[r[field]] = r
    return out


def read_decisions(batch_dir):
    p = batch_dir / "decisions.csv"
    if not p.exists():
        return {}
    with open(p, newline="", encoding="utf-8") as f:
        return {r["id"]: (r.get("decision") or "").strip().lower() for r in csv.DictReader(f)}


def reviewed(rec, csv_decision):
    """The researcher's own call on a line, or None while nobody has made one.

    `decision` is what decisions.csv holds — pre-filled by the batch (apply_batch.py, by
    confidence) until someone decides. A line is reviewed when its latest log record is a
    person's: not the backend sync's, not an undo back to undecided, and still the decision
    the csv carries (a regenerated or hand-edited csv makes the line undecided again)."""
    if not rec or rec.get("reviewer") == SYNC_REVIEWER or rec.get("undecided"):
        return None
    if CSV_DECISION.get(rec.get("decision")) != csv_decision:
        return None
    return rec["decision"]


def overlay(data, dirs):
    """A copy of `data` with every proposal's current decision, the researcher's own call
    (`reviewed`, None = undecided) and last review record.

    decisions.csv is authoritative for the decision; review_log.jsonl supplies who / when /
    note, and turns a csv `reject` back into `suggest` when the latest record is a suggestion
    (suggest is stored as reject in decisions.csv)."""
    dec = {b: read_decisions(d) for b, d in dirs.items()}
    log = {b: latest(read_jsonl(d / "review_log.jsonl")) for b, d in dirs.items()}
    proposals = {}
    counts = {b: {"accept": 0, "hold": 0, "reject": 0, "suggest": 0} for b in dirs}
    for key, p in data["proposals"].items():
        q = dict(p)
        b = p["batch"]
        q["decision"] = dec.get(b, {}).get(p["id"]) or p["decision"]
        rec = log.get(b, {}).get(key)
        q["last"] = rec
        q["reviewed"] = reviewed(rec, q["decision"])
        q["suggestion"] = None
        if rec and rec.get("decision") == "suggest" and q["decision"] == "reject":
            q["decision"] = "suggest"
            q["suggestion"] = {"value": rec.get("suggested_value", ""),
                               "kind": rec.get("suggest_kind", "value"), "note": rec.get("note", ""),
                               "refs": list(rec.get("suggested_refs") or [])}
        counts.setdefault(b, {"accept": 0, "hold": 0, "reject": 0, "suggest": 0})
        counts[b][q["decision"]] = counts[b].get(q["decision"], 0) + 1
        proposals[key] = q
    out = dict(data)
    out["proposals"] = proposals
    out["batches"] = [dict(b, counts=counts.get(b["dir"], b["counts"])) for b in data["batches"]]
    return out


# ---- write-back ------------------------------------------------------------------

def now():
    return datetime.now(ET).isoformat(timespec="seconds")


def validate(records, proposals):
    """Normalised decision records, or Invalid (nothing is written for a bad request)."""
    if not isinstance(records, list) or not records:
        raise Invalid("expected a non-empty list of decision records")
    out = []
    for i, r in enumerate(records):
        if not isinstance(r, dict):
            raise Invalid(f"record {i}: not an object")
        key, decision = r.get("key"), r.get("decision")
        if key not in proposals:
            raise Invalid(f"record {i}: unknown key {key!r}")
        if decision not in DECISIONS:
            raise Invalid(f"record {i}: decision {decision!r} is not one of {', '.join(DECISIONS)}")
        rec = {"key": key, "decision": decision, "suggested_value": "", "suggest_kind": "", "suggested_refs": [],
               "note": str(r.get("note") or ""), "via": str(r.get("via") or "single")[:500]}
        if decision == "suggest":
            kind = r.get("suggest_kind") or "value"
            if kind not in SUGGEST_KINDS:
                raise Invalid(f"record {i}: suggest_kind {kind!r} is not one of {', '.join(SUGGEST_KINDS)}")
            if not str(r.get("suggested_value") or "").strip():
                raise Invalid(f"record {i}: a suggestion needs a value")
            if not rec["note"].strip():
                raise Invalid(f"record {i}: a suggestion needs a note")
            rec["suggested_value"] = str(r["suggested_value"])
            rec["suggest_kind"] = kind
            rec["suggested_refs"] = suggested_refs(r.get("suggested_refs"), i)
        elif r.get("undecided"):
            # back to a line nobody has decided (an undo, or a click on the pressed button): the
            # csv gets its pre-filled decision back and the line reads as undecided again
            rec["undecided"] = True
        out.append(rec)
    return out


def suggested_refs(raw, i=0):
    """The refs typed with a suggestion — a list, or one string with a URL per line / comma —
    as a deduplicated list of http(s) URLs; anything else is Invalid."""
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = re.split(r"[\s,]+", raw)
    if not isinstance(raw, list):
        raise Invalid(f"record {i}: suggested_refs must be a list of URLs")
    out = []
    for u in raw:
        u = str(u or "").strip()
        if not u:
            continue
        if not re.match(r"https?://\S+$", u):
            raise Invalid(f"record {i}: suggested ref {u!r} is not an http(s) URL")
        if u not in out:
            out.append(u)
    return out


def _records_with_raw(text):
    """[(raw_text, fields)] for each CSV record, raw_text being its exact source bytes
    (a record may span lines when a quoted field holds a newline)."""
    # split on "\n" only (str.splitlines would also split on   etc. inside a field)
    parts = text.split("\n")
    lines = [p + "\n" for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])
    consumed = []

    def feed():
        for ln in lines:
            consumed.append(ln)
            yield ln
    out = []
    for fields in csv.reader(feed()):
        out.append(("".join(consumed), fields))
        consumed.clear()
    return out


def _serialise(fields, raw):
    """One record in csv-module form, keeping the line ending its source line had."""
    ending = "\r\n" if raw.endswith("\r\n") else ("\n" if raw.endswith("\n") else "")
    buf = io.StringIO()
    csv.writer(buf, lineterminator=ending).writerow(fields)
    return buf.getvalue()


def _rewrite(path, column, new_value):
    """New text of a csv with only cells of `column` changed, where
    new_value(index, row_dict) returns the value (None = leave the record alone). Every other
    record keeps its exact source bytes."""
    with open(path, encoding="utf-8", newline="") as f:   # newline="": keep \r\n as written
        text = f.read()
    recs = _records_with_raw(text)
    if not recs:
        raise Invalid(f"{path} is empty")
    header = recs[0][1]
    if column not in header:
        raise Invalid(f"{path} has no {column} column")
    i_col = header.index(column)
    parts = [recs[0][0]]
    for n, (raw, fields) in enumerate(recs[1:]):
        v = new_value(n, dict(zip(header, fields)))
        if v is not None and len(fields) > i_col and fields[i_col] != v:
            fields = list(fields)
            fields[i_col] = v
            raw = _serialise(fields, raw)
        parts.append(raw)
    return "".join(parts)


def plan_csv(path, updates):
    """New text of decisions.csv with only the `decision` cell of the ids in `updates`
    changed. Invalid if an id is missing."""
    seen = set()

    def val(_n, row):
        if row.get("id") in updates:
            seen.add(row["id"])
            return updates[row["id"]]
        return None
    with open(path, encoding="utf-8", newline="") as f:
        if "id" not in next(csv.reader(f), []):
            raise Invalid(f"{path} has no id column")
    text = _rewrite(path, "decision", val)
    missing = set(updates) - seen
    if missing:
        raise Invalid(f"{path.parent.name}: decisions.csv has no line for {', '.join(sorted(missing))} "
                      "— re-run apply_batch.py on the batch, then rebuild review_data.json")
    return text


def plan_conflicts(path, calls):
    """conflicts.csv with the `decision` cell of record i set, for {i: (row_id, column, call)}.
    Invalid when record i no longer holds that row_id + column (the file was regenerated)."""
    seen = {}

    def val(n, row):
        if n in calls:
            seen[n] = (row.get("row_id", ""), row.get("column", ""))
            return calls[n][2]
        return None
    text = _rewrite(path, "decision", val)
    for n, (rid, col, _c) in calls.items():
        if seen.get(n) != (rid, col):
            raise Invalid(f"{path.parent.name}: conflicts.csv record {n} is no longer {rid} / {col} "
                          "— rebuild review_data.json")
    return text


def atomic_write(path, text):
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def append_jsonl(path, records):
    """Append records; returns the file's prior size so a failed step can roll it back."""
    size = path.stat().st_size if path.exists() else 0
    with open(path, "a", encoding="utf-8", newline="") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return size


def rollback(path, size):
    if size == 0:
        path.unlink(missing_ok=True)
    else:
        with open(path, "r+b") as f:
            f.truncate(size)


def decide(records, data, dirs, reviewer):
    """Validate, then per batch: append to review_log.jsonl and rewrite only the decision
    column of decisions.csv (atomically). The caller holds the process lock.

    Everything is validated and every new csv text computed before the first write, so a bad
    request changes nothing; a failed write rolls back that batch's log append and leaves its
    csv untouched."""
    recs = validate(records, data["proposals"])
    ts = now()
    by_batch = {}
    for r in recs:
        r["reviewer"], r["ts"] = reviewer, ts
        by_batch.setdefault(data["proposals"][r["key"]]["batch"], []).append(r)
    plans = {}
    for b, rs in by_batch.items():
        if b not in dirs:
            raise Invalid(f"batch dir not known to the server: {b}")
        updates = {data["proposals"][r["key"]]["id"]: CSV_DECISION[r["decision"]] for r in rs}
        plans[b] = plan_csv(dirs[b] / "decisions.csv", updates)
    for b, rs in by_batch.items():
        log = dirs[b] / "review_log.jsonl"
        size = append_jsonl(log, rs)
        try:
            atomic_write(dirs[b] / "decisions.csv", plans[b])
        except Exception:
            rollback(log, size)
            raise
    return recs


# ---- review items (Items tab) ------------------------------------------------------

ITEM_STATUSES = ("open", "resolved", "needs research")
# a conflict's call, written to conflicts.csv `decision` (AP §4: decided by hand; an accepted
# one is still applied as a deliberate single-cell edit, never by the app)
CONFLICT_CALLS = ("accept", "hold", "reject")


def overlay_items(data, dirs):
    """Items with their latest status / note / call from each batch's review_items.jsonl;
    a conflict's call is read back from conflicts.csv when it still matches the record."""
    log = {b: latest(read_jsonl(d / "review_items.jsonl"), "item_id") for b, d in dirs.items()}
    conflicts = {}
    out = []
    for it in data.get("items", []):
        q = dict(it)
        rec = log.get(it["batch"], {}).get(it["item_id"])
        q["status"] = (rec or {}).get("status", "open")
        q["last"] = rec
        if it.get("conflict_match") and it["batch"] in dirs:
            b = it["batch"]
            if b not in conflicts:
                p = dirs[b] / "conflicts.csv"
                conflicts[b] = []
                if p.exists():
                    with open(p, newline="", encoding="utf-8") as f:
                        conflicts[b] = list(csv.DictReader(f))
            rows = conflicts[b]
            i = it["conflict_index"]
            if i < len(rows) and [rows[i].get("row_id", ""), rows[i].get("column", "")] == it["conflict_match"]:
                q["conflict_decision"] = rows[i].get("decision", "")
            # apply_batch.py regenerates conflicts.csv with every call back at hold; the log keeps it
            call = next((r.get("conflict_decision") for r in reversed(read_jsonl(dirs[b] / "review_items.jsonl"))
                         if r.get("item_id") == it["item_id"] and r.get("conflict_decision")), "")
            q["logged_call"] = call
        out.append(q)
    return out


def record_items(records, data, dirs, reviewer):
    """Validate item records {item_id, status, note, conflict_decision?}; per batch append
    them to review_items.jsonl and write conflict calls into conflicts.csv `decision`."""
    if not isinstance(records, list) or not records:
        raise Invalid("expected a non-empty list of item records")
    items = {it["item_id"]: it for it in data.get("items", [])}
    ts = now()
    by_batch = {}
    for i, r in enumerate(records):
        if not isinstance(r, dict):
            raise Invalid(f"record {i}: not an object")
        it = items.get(r.get("item_id"))
        if not it:
            raise Invalid(f"record {i}: unknown item {r.get('item_id')!r}")
        status = r.get("status") or "open"
        if status not in ITEM_STATUSES:
            raise Invalid(f"record {i}: status {status!r} is not one of {', '.join(ITEM_STATUSES)}")
        rec = {"item_id": it["item_id"], "status": status, "note": str(r.get("note") or ""),
               "reviewer": reviewer, "ts": ts}
        call = r.get("conflict_decision")
        if call:
            if not it.get("conflict_match"):
                raise Invalid(f"record {i}: {it['item_id']} is not a conflicts.csv record")
            if call not in CONFLICT_CALLS:
                raise Invalid(f"record {i}: conflict call {call!r} is not one of {', '.join(CONFLICT_CALLS)}")
            rec["conflict_decision"] = call
        if it["batch"] not in dirs:
            raise Invalid(f"batch dir not known to the server: {it['batch']}")
        by_batch.setdefault(it["batch"], []).append((rec, it))
    plans = {}
    for b, pairs in by_batch.items():
        calls = {it["conflict_index"]: (*it["conflict_match"], rec["conflict_decision"])
                 for rec, it in pairs if rec.get("conflict_decision")}
        if calls:
            plans[b] = plan_conflicts(dirs[b] / "conflicts.csv", calls)
    for b, pairs in by_batch.items():
        log = dirs[b] / "review_items.jsonl"
        size = append_jsonl(log, [rec for rec, _ in pairs])
        if b in plans:
            try:
                atomic_write(dirs[b] / "conflicts.csv", plans[b])
            except Exception:
                rollback(log, size)
                raise
    return [rec for pairs in by_batch.values() for rec, _ in pairs]


# ---- backend sync (the refresh button) ---------------------------------------------

SYNC_REVIEWER = "backend sync"
SYNC_VIA = "sync:backend"


def sync_backend(data, dirs):
    """After a fresh pull + rebuild: settle what the backend already settles.

    A held line the backend already holds (`in_backend`) is accepted; an open item the backend
    resolves (`backend_resolved`) is marked resolved. Both go through the ordinary write paths,
    logged as SYNC_REVIEWER / SYNC_VIA, so the batch dir records why. A line someone decided
    (accept / reject / suggest) is never touched. Reads the backend's state, never writes it."""
    cur = overlay(data, dirs)["proposals"]
    lines = [{"key": k, "decision": "accept", "via": SYNC_VIA,
              "note": "the backend already holds this"}
             for k, p in cur.items() if "in_backend" in p["flags"] and p["decision"] == "hold"]
    items = [{"item_id": it["item_id"], "status": "resolved", "note": it["backend_resolved"]}
             for it in overlay_items(data, dirs)
             if it.get("backend_resolved") and it["status"] == "open"]
    accepted = decide(lines, data, dirs, SYNC_REVIEWER) if lines else []
    resolved = record_items(items, data, dirs, SYNC_REVIEWER) if items else []
    return {"accepted": [r["key"] for r in accepted], "resolved": [r["item_id"] for r in resolved]}
