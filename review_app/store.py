"""
The review app's decision store over the batch dirs (phase 1).

Reads each batch's `decisions.csv` (the store the pipeline reads) and the append-only audit
sidecar `review_log.jsonl`, and lays the current state over the built dataset. Nothing here
touches the backend.
"""
import csv
import json


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
