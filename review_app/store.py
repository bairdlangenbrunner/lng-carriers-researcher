"""
The review app's decision store over the batch dirs (phase 1).

Reads each batch's `decisions.csv` (the store the pipeline reads) and the append-only audit
sidecar `review_log.jsonl`, and lays the current state over the built dataset. Nothing here
touches the backend.
"""
import csv
import io
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
DECISIONS = ("accept", "hold", "reject", "suggest")
SUGGEST_KINDS = ("value", "cosmetic")
# suggest is stored as reject in decisions.csv: the value as proposed is not wanted; its
# replacement arrives through a fix batch (suggestions.py)
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


def overlay(data, dirs):
    """A copy of `data` with every proposal's current decision and last review record.

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
        q["suggestion"] = None
        if rec and rec.get("decision") == "suggest" and q["decision"] == "reject":
            q["decision"] = "suggest"
            q["suggestion"] = {"value": rec.get("suggested_value", ""),
                               "kind": rec.get("suggest_kind", "value"), "note": rec.get("note", "")}
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
        rec = {"key": key, "decision": decision, "suggested_value": "", "suggest_kind": "",
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
        out.append(rec)
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


def plan_csv(path, updates):
    """New text of decisions.csv with only the `decision` cell of the ids in `updates`
    changed; every other record keeps its exact source bytes. Invalid if an id is missing."""
    with open(path, encoding="utf-8", newline="") as f:   # newline="": keep \r\n as written
        text = f.read()
    recs = _records_with_raw(text)
    if not recs:
        raise Invalid(f"{path} is empty")
    header = recs[0][1]
    if "id" not in header or "decision" not in header:
        raise Invalid(f"{path} has no id / decision column")
    i_id, i_dec = header.index("id"), header.index("decision")
    seen = set()
    parts = [recs[0][0]]
    for raw, fields in recs[1:]:
        rid = fields[i_id] if len(fields) > i_id else None
        if rid in updates and len(fields) > i_dec:
            seen.add(rid)
            if fields[i_dec] != updates[rid]:
                fields = list(fields)
                fields[i_dec] = updates[rid]
                raw = _serialise(fields, raw)
        parts.append(raw)
    missing = set(updates) - seen
    if missing:
        raise Invalid(f"{path.parent.name}: decisions.csv has no line for {', '.join(sorted(missing))} "
                      "— re-run apply_batch.py on the batch, then rebuild review_data.json")
    return "".join(parts)


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
