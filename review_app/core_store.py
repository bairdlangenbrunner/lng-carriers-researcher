"""
The review app's decision store: the shared store in ../gem-review-app (review_core/store.py) bound to the LNG config (trackers/lng/config.py), with the files apply_batch.py reads kept as they were.

Every write goes through `sink`, under the core's process lock, as one transaction across the batch dirs it touches:

    line decisions   review_log.jsonl (the core's log; review_decisions.json is derived from it) and the `decision` cell of decisions.csv (a suggest is stored as reject; an undo puts the batch's pre-fill back)
    item calls       review_items.jsonl, in the shape it has always had (item_id, status, note, conflict_decision), and a conflict's call in the `decision` cell of its conflicts.csv record

Everything is planned before the first write, and a failed step rolls every touched file back. decisions.csv stays authoritative: `overlay` shows a person's call only while decisions.csv still holds it, so a regenerated or hand-edited csv makes the line undecided again (store.reviewed has always read it that way). The old store (review_app/store.py) stays for push.py, living.py and suggestions.py, which read the raw dataset.

    import core_store as store     # store.overlay / decide / record_items / sync_backend / sink
"""
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
for p in (REPO / "scripts", HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import gem_core  # noqa: E402,F401  (puts ../gem-review-app on sys.path)
import store as legacy  # noqa: E402
from review_core.store import bind  # noqa: E402
from trackers.lng.config import CONFIG, ITEMS_PID, OTHER_CALLS, REGRADE_REVIEWER, SYNC_REVIEWER  # noqa: E402,F401

BATCHES = REPO / "batches"
bind(CONFIG, BATCHES, into=sys.modules[__name__])      # ROOT is now BATCHES: dir labels are batch dir names
_core_overlay = overlay  # noqa: F821  (bind put it here)

CSV_DECISION = legacy.CSV_DECISION
ITEMS_LOG = "review_items.jsonl"
SYNC_VIA = legacy.SYNC_VIA
# review_items.jsonl `status` <-> a call on any item but a conflict
STATUS_CALL = {"resolved": "resolved", "needs research": "needs_research"}
CALL_STATUS = {v: k for k, v in STATUS_CALL.items()}
# kept from a core item record in its review_items.jsonl line (id and origin: a page record imported by import_log.py)
ITEM_FIELDS = ("key", "dir", "pid", "kind", "call", "undecided", "via", "id", "origin")
assert set(CALL_STATUS) == set(OTHER_CALLS)


def _conflict_rows(d, cache):
    if d not in cache:
        p = d / "conflicts.csv"
        cache[d] = []
        if p.exists():
            with open(p, newline="", encoding="utf-8") as f:
                cache[d] = list(csv.DictReader(f))
    return cache[d]


def overlay(data, dirs=None, root=None):  # noqa: F811
    """The core overlay, then what decisions.csv and review_items.jsonl say.

    A line gets `prefill` (what decisions.csv holds now), its `decision` only while the csv still
    agrees with it, `suggest_kind` / `suggested_refs` on a suggest, `applied` from the latest
    machine record, and `decided_by` as initials (older records carry full names). An item's call
    comes from review_items.jsonl; a conflict's counts only while conflicts.csv still holds it, and
    `logged_call` keeps the last one logged (apply_batch.py regenerates conflicts.csv at hold)."""
    dirs = dirs if dirs is not None else dir_paths(data, root)  # noqa: F821
    _core_overlay(data, dirs)
    csvs, logs, items, conflicts = {}, {}, {}, {}
    for card in cards(data):  # noqa: F821
        for line in card.get("lines", []):
            d = line["dir"]
            if d not in dirs:
                continue
            if d not in csvs:
                csvs[d] = legacy.read_decisions(dirs[d])
                logs[d] = calls(read_log(dirs[d]))  # noqa: F821
            line["prefill"] = csvs[d].get(line["id"]) or line.get("prefill") or line.get("default")
            rec, mach = speaker(logs[d], line["key"])  # noqa: F821
            live = rec if rec and not rec.get("undecided") else None
            if live and CSV_DECISION.get(live.get("decision")) != line["prefill"]:
                live = None
                for f in ("decision", "decided_by", "decided_at"):
                    line[f] = None
                line.update(reviewed=False, decision_note="", suggested_value="")
            sug = bool(live) and live.get("decision") == "suggest"
            line["suggest_kind"] = live.get("suggest_kind") or "value" if sug else ""
            line["suggested_refs"] = list(live.get("suggested_refs") or []) if sug else []
            line["decided_by"] = initials(line.get("decided_by"))  # noqa: F821
            line["applied"] = {"by": mach["reviewer"], "at": mach.get("ts")} if mach else None
        for it in card.get("items", []):
            d = it["dir"]
            if d not in dirs:
                continue
            if d not in items:
                items[d] = read_jsonl(dirs[d] / ITEMS_LOG)  # noqa: F821
            recs = [r for r in in_time_order(items[d]) if r.get("item_id") == it["key"]]  # noqa: F821
            rec = recs[-1] if recs else None
            call = item_call(it, rec)
            if it.get("conflict_match"):
                rows = _conflict_rows(dirs[d], conflicts)
                i = it.get("conflict_index")
                held = rows[i].get("decision", "") if isinstance(i, int) and i < len(rows) and \
                    [rows[i].get("row_id", ""), rows[i].get("column", "")] == list(it["conflict_match"]) else ""
                it["prefill"] = held or None
                if call in legacy.CONFLICT_CALLS and call != held:
                    call = None
                it["logged_call"] = next((r["conflict_decision"] for r in reversed(recs)
                                          if r.get("conflict_decision") and not r.get("undecided")), "")
            person = bool(rec) and call is not None and not is_machine(rec)  # noqa: F821
            it["call"] = call
            it["call_note"] = rec.get("note", "") if call is not None else None
            it["reviewed"] = person
            it["decided_by"] = initials(rec.get("reviewer")) if call is not None else None  # noqa: F821
            it["decided_at"] = rec.get("ts") if call is not None else None
    return data


def item_call(it, rec):
    """The call a review_items.jsonl record makes on an item, or None (open, or undone)."""
    if not rec or rec.get("undecided"):
        return None
    if rec.get("call"):
        return rec["call"]
    if it.get("conflict_match") and rec.get("conflict_decision"):
        return rec["conflict_decision"]
    return STATUS_CALL.get(rec.get("status"))


def item_status(rec):
    """review_items.jsonl `status` for a core item record."""
    if rec.get("undecided"):
        return "open"
    if rec.get("conflict_match") and rec.get("call") in legacy.CONFLICT_CALLS:
        return "open" if rec["call"] == "hold" else "resolved"
    return CALL_STATUS.get(rec.get("call"), "resolved")


def conflict_call(rec):
    """True when an item record puts a call into conflicts.csv: a conflict's accept / hold / reject, or its undo (back to hold)."""
    return bool(rec.get("conflict_match")) and (rec.get("call") in legacy.CONFLICT_CALLS or bool(rec.get("undecided")))


def read_item_log(d):
    """A batch dir's review_items.jsonl."""
    return read_jsonl(Path(d) / ITEMS_LOG)  # noqa: F821


def sink(recs, dirs, stamp=True):
    """Write core records (the caller holds the core lock): line records to review_log.jsonl and
    decisions.csv, item records to review_items.jsonl and conflicts.csv. All the csv texts are
    computed before the first write; on a failure every file written so far goes back."""
    lines = [r for r in recs if "decision" in r]
    items = [r for r in recs if "decision" not in r]
    ts = now()  # noqa: F821
    for r in items:
        if stamp:
            r["ts"] = ts
        if r["dir"] not in dirs:
            raise Invalid(f"batch dir not known to the server: {r['dir']}")  # noqa: F821
    plans = {}          # path -> new text
    by_dir = {}
    for r in lines:
        if r["dir"] not in dirs:
            raise Invalid(f"batch dir not known to the server: {r['dir']}")  # noqa: F821
        by_dir.setdefault(r["dir"], {})[r["record_id"]] = CSV_DECISION[r["decision"]]
    for d, updates in by_dir.items():
        plans[Path(dirs[d]) / "decisions.csv"] = legacy.plan_csv(Path(dirs[d]) / "decisions.csv", updates)
    calls_by_dir = {}
    for r in items:
        if conflict_call(r):
            call = "hold" if r.get("undecided") else r["call"]
            calls_by_dir.setdefault(r["dir"], {})[r["conflict_index"]] = (*r["conflict_match"], call)
    for d, calls_ in calls_by_dir.items():
        plans[Path(dirs[d]) / "conflicts.csv"] = legacy.plan_conflicts(Path(dirs[d]) / "conflicts.csv", calls_)
    item_logs = {}
    for r in items:
        rec = {"item_id": r["key"], "status": item_status(r), "note": r.get("note", ""),
               "reviewer": r.get("reviewer"), "ts": r.get("ts")}
        if conflict_call(r):
            rec["conflict_decision"] = "hold" if r.get("undecided") else r["call"]
        rec.update({k: r[k] for k in ITEM_FIELDS if k in r})
        item_logs.setdefault(r["dir"], []).append(rec)

    # the line log goes last: the core's _write rolls its own append back when it fails
    saved = {}           # path -> prior text
    appended = []        # (path, prior size)
    try:
        for d, rs in item_logs.items():
            log = Path(dirs[d]) / ITEMS_LOG
            appended.append((log, append_jsonl(log, rs)))  # noqa: F821
        for path, text in plans.items():
            saved[path] = path.read_text(encoding="utf-8")
            atomic_write(path, text)  # noqa: F821
        if lines:
            _write(lines, dirs, stamp=stamp)  # noqa: F821
    except Exception:
        for path, old in saved.items():
            try:
                atomic_write(path, old)  # noqa: F821
            except Exception:
                pass
        for log, size in appended:
            rollback(log, size)  # noqa: F821
        raise
    return recs


def sync_backend(data, dirs):
    """After a fresh pull and rebuild, settle what the backend already settles: a held line the
    backend already holds (`in_backend`) is accepted, and an open item the backend resolves
    (`backend_resolved`) is marked resolved, both as SYNC_REVIEWER. A line or item a person has
    called is never touched. Reads the backend's state, never writes it."""
    overlay(data, dirs)
    lines, items = [], []
    for card in cards(data):  # noqa: F821
        for ln in card.get("lines", []):
            if "in_backend" in ln.get("flags", []) and ln.get("prefill") == "hold" and not ln.get("reviewed"):
                lines.append({"key": ln["key"], "decision": "accept", "via": SYNC_VIA,
                              "note": "the backend already holds this"})
        for it in card.get("items", []):
            if it.get("backend_resolved") and it.get("call") is None:
                items.append({"key": it["key"], "call": "resolved", "note": it["backend_resolved"]})
    accepted = decide(lines, data, SYNC_REVIEWER, dirs, sink=sink) if lines else []  # noqa: F821
    resolved = record_items(items, data, SYNC_REVIEWER, dirs, sink=sink) if items else []  # noqa: F821
    return {"accepted": [r["key"] for r in accepted], "resolved": [r["key"] for r in resolved]}
