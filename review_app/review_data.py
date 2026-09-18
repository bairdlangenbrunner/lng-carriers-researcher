"""
Build the review app's dataset (work/review_data.json) from one or more batch dirs.

Full values come from apply_batch's own item model (`_detect` + `_items_and_conflicts`),
never from decisions.csv, which truncates proposed_value / note to 80 characters. The
current decision per proposal comes from decisions.csv; backend context and current
values from the fresh pull (work/backend.csv). Every row a human sees is the LIVE sheet
row (`sheet_row_map`); `row_id` stays the key.

    python review_app/review_data.py --batches batches/<dir> [<dir> ...] [--out work/review_data.json]

Read-only over the batch dirs and the backend. Deterministic apart from `built`.
"""
import argparse
import csv
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from apply_batch import _default_decision, _detect, _items_and_conflicts  # noqa: E402
from backend_io import load_backend  # noqa: E402
from paths import backend_csv_path, work_dir  # noqa: E402

ET = ZoneInfo("America/New_York")
DECISIONS = ("accept", "hold", "reject")

# Linked columns by exact backend header (plan fact 8); X <-> "X [ref]" is handled generically.
PAIRS = [("Name", "Other names"), ("Price", "Price currency"), ("Capacity", "Capacity units")]
# The Name <-> Other names prompt is not skippable in the UI (RF §4.16).
STRICT_PAIR = {"Name", "Other names"}
IGU_PDF = re.compile(r"igu-world-lng-report", re.I)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def split_urls(s):
    return [u.strip() for u in re.split(r",\s+|\s*\n\s*|\s+;\s+", s or "") if u.strip()]


def partner_columns(col, header):
    """Columns linked to `col` (fact 8), restricted to columns present in the header."""
    out = []
    for a, b in PAIRS:
        if col == a:
            out.append(b)
        elif col == b:
            out.append(a)
    if col.endswith(" [ref]"):
        out.append(col[:-6])
    elif f"{col} [ref]" in header:
        out.append(f"{col} [ref]")
    return [c for c in out if c in header]


def batch_info(batch_dirs, info_path=None):
    """dir -> {label, apply_order, applied} from an optional review_batches.json.

    Looked up at --info, else in any batches/*/review_batches.json that names one of the
    dirs. Absent: label = dir name, order = dir sort order, applied = a verify_report.csv
    exists in the dir (verify_apply.py only runs after an apply)."""
    info = {}
    paths = [Path(info_path)] if info_path else sorted((ROOT / "batches").glob("*/review_batches.json"))
    names = {d.name for d in batch_dirs}
    for p in paths:
        doc = json.loads(p.read_text(encoding="utf-8"))
        if names & set(doc):
            info = doc
            break
    out = {}
    for i, d in enumerate(sorted(batch_dirs, key=lambda d: d.name), 1):
        meta = info.get(d.name, {})
        out[d.name] = {
            "label": meta.get("label", d.name),
            "apply_order": meta.get("apply_order", i),
            "applied": bool(meta.get("applied", (d / "verify_report.csv").exists())),
        }
    return out


# ---- gate verdicts (plan fact 6) --------------------------------------------------

def _qa_sections(wb_path):
    """QA_review -> {section title: [row dicts]} (the build_combined.py approach)."""
    import openpyxl
    wb = openpyxl.load_workbook(wb_path, read_only=True)
    if "QA_review" not in wb.sheetnames:
        return {}
    out, title, header = defaultdict(list), "", None
    for r in wb["QA_review"].iter_rows(values_only=True):
        r = list(r)
        vals = [v for v in r if v not in (None, "")]
        if not vals:
            continue
        if len(vals) == 1 and r[0] not in (None, "") and not str(r[0]).isdigit():
            title, header = str(r[0]), None
            continue
        if header is None:
            header = [h for h in r if h not in (None, "")]
            continue
        out[title].append(dict(zip(header, r)))
    wb.close()
    return out


def gate_verdicts(batch_dir, key_to_header):
    """(by_cell, by_url): (row_id, field, url) -> verdict and url -> verdict.

    The batch workbook's QA_review sheet, with gate_log.json (when the batch has one) laid
    over it — a gate log can cover only part of a batch (the roll-forward's covers 263 of
    473 checks). Nothing found -> None, and the UI shows "—" (a verdict is never invented)."""
    by_cell, by_url = {}, {}
    for wb in sorted(batch_dir.glob("lng_carrier_*.xlsx")):
        for title, rows in _qa_sections(wb).items():
            for q in rows:
                url = str(q.get("url") or "")
                if q.get("verdict") and url:                       # fix workbooks
                    by_cell[(str(q.get("row_id")), str(q.get("field")), url)] = str(q["verdict"])
                elif title == "Per-cell citation log" and url:     # ref_fill
                    note = str(q.get("note") or "")
                    field = key_to_header.get(str(q.get("field")), str(q.get("field")))
                    for u in split_urls(url):
                        by_cell[(str(q.get("row_id")), field, u)] = \
                            f"{'PASS' if ': OK' in note else 'FAIL'} ({note})"
                elif title == "URL verification log" and url:      # data_fill / discovery
                    res = q.get("result") if q.get("result") not in (None, "None") else q.get("status")
                    if res not in (None, "None", ""):
                        by_url[url] = f"{res} (URL log)"
    gl = batch_dir / "gate_log.json"
    if gl.exists():
        for g in json.loads(gl.read_text(encoding="utf-8")):
            v = f"{'PASS' if g.get('ok') else 'FAIL'} ({g.get('reason', '')})"
            by_cell[(str(g.get("row_id")), g.get("field", ""), g.get("url", ""))] = v
    return by_cell, by_url


# ---- review items (plan fact 7) --------------------------------------------------

def collect_items(bdir, mode, srm):
    name = bdir.name
    items = []

    def live(ids):
        return [srm[i] for i in ids if i in srm]

    cpath = bdir / "conflicts.csv"
    if cpath.exists():
        for i, c in enumerate(read_csv(cpath)):
            ids = [x for x in re.split(r"[/,;\s]+", c.get("row_id", "")) if x]
            rows = live(ids)
            if not rows:  # discovery flags carry "live row(s) 1168" in the text
                rows = [int(x) for x in re.findall(r"live row\(s\)\s*([\d,\s/-]+)", c.get("recommendation", ""))
                        for x in re.findall(r"\d+", x)][:20]
            items.append({
                "item_id": f"{name}::conflict:{i}", "type": "flag" if mode == "discovery" else "conflict",
                "batch": name, "live_rows": rows, "row_ids": ids,
                "title": " · ".join(x for x in (c.get("column"), c.get("backend_value") and
                                               f"{c['backend_value']} → {c.get('proposed_value', '')}") if x)
                or "backend flag",
                "detail": c.get("recommendation", ""), "urls": split_urls(c.get("sources", "")),
                "conflict_index": i, "conflict_decision": c.get("decision", ""),
            })
    mpath = bdir / "manual_review.json"
    if mpath.exists():
        for i, m in enumerate(json.loads(mpath.read_text(encoding="utf-8"))):
            rid = str(m.get("row_id", ""))
            title = m.get("name") or ""
            if m.get("field"):
                title = f"{m['field']}: {m.get('backend', '')} vs IGU {m.get('igu', '')}"
            elif m.get("verdict"):
                title = f"press follow-up: {m['verdict']}" + (f" ({m['name']})" if m.get("name") else "")
            urls = [u for k in ("status_urls", "year_urls", "name_urls") for u in (m.get(k) or [])]
            items.append({
                "item_id": f"{name}::manual:{i}", "type": "manual", "batch": name,
                "live_rows": live([rid]), "row_ids": [rid], "title": title or "manual review",
                "detail": " ".join(x for x in (m.get("why"), m.get("note")) if x), "urls": urls,
            })
    ppath = bdir / "proposed_review.json"
    if ppath.exists():
        for p in json.loads(ppath.read_text(encoding="utf-8")).get("programmes", []):
            urls = [e.get("url", "") for e in p.get("evidence", []) if e.get("url")]
            for a in p.get("row_actions", []):
                rid = str(a.get("row_id", ""))
                items.append({
                    "item_id": f"{name}::proposed:{rid}", "type": "proposed_bucket", "batch": name,
                    "live_rows": live([rid]), "row_ids": [rid],
                    "title": f"{p.get('programme', '')} · {a.get('action', '')}"
                             + ("" if rid in srm else " · row no longer in backend"),
                    "detail": a.get("note", ""), "urls": urls,
                })
    dpath = bdir / "dedupe_report.csv"
    if dpath.exists():
        for i, d in enumerate(read_csv(dpath)):
            ids = [x for x in re.split(r"[/,;\s]+", d.get("row_ids", "")) if x]
            items.append({
                "item_id": f"{name}::duplicate:{i}", "type": "duplicate", "batch": name,
                "live_rows": live(ids), "row_ids": ids,
                "title": f"{d.get('tier', '')} {d.get('reason', '')}".strip() or "possible duplicate",
                "detail": "; ".join(f"{k}: {v}" for k, v in d.items() if v and k not in ("row_ids",)),
                "urls": [],
            })
    return items


# ---- build -----------------------------------------------------------------------

def build(batch_dirs, backend_path=None, info_path=None):
    be = load_backend(backend_path)
    header, colmap = be.header, be.colmap
    H = {h: i for i, h in enumerate(header)}
    rows = be.row_by_id()
    srm = be.sheet_row_map()
    key_to_header = {k: header[v] for k, v in colmap.items()
                     if not k.startswith("_") and isinstance(v, int) and v < len(header)}
    info = batch_info(batch_dirs, info_path)

    def cell(rid, col):
        r = rows.get(rid)
        return r[H[col]].strip() if r is not None and col in H and len(r) > H[col] else ""

    batches, proposals, all_items = [], {}, []
    for bdir in sorted(batch_dirs, key=lambda d: (info[d.name]["apply_order"], d.name)):
        mode, payload = _detect(bdir)
        items, _ = _items_and_conflicts(mode, payload, header, colmap)
        dec_path = bdir / "decisions.csv"
        dec = {r["id"]: (r.get("decision") or "").strip().lower() for r in read_csv(dec_path)} \
            if dec_path.exists() else {}
        by_cell, by_url = gate_verdicts(bdir, key_to_header)
        # fix-mode cell flags the item model does not carry (read from the already-loaded payload)
        fix_flags = {}
        if mode == "fix":
            for corr in payload.get("corrections", []):
                for c in corr.get("cells", []):
                    fix_flags[(str(corr["row_id"]), c.get("field", ""))] = c
        counts = {k: 0 for k in DECISIONS}
        meta = info[bdir.name]
        for it in items:
            key = f"{bdir.name}::{it['id']}"
            default = _default_decision(it["confidence"], it["derivable"])
            decision = dec.get(it["id"]) or default
            counts[decision] = counts.get(decision, 0) + 1
            rid, col = it["row_id"], it["column"]
            flags = []
            fc = fix_flags.get((rid, col), {})
            if fc.get("preserve_ref"):
                flags.append("preserve_ref")
            if fc.get("append_ref"):
                flags.append("append_ref")
            if it.get("ref_only"):
                flags.append("ref_only")
            if meta["applied"]:
                flags.append("applied")
            ref_urls = split_urls(it["ref_value"])
            if it["kind"] == "new_row":
                rd = it["row_data"] or {}
                ref_urls = list(dict.fromkeys(u for h, v in rd.items() if h.endswith("[ref]")
                                              for u in split_urls(v)))
            vfield = col[:-6] if it["kind"] == "ref" and col.endswith(" [ref]") else col
            refs = [{"url": u, "verdict": by_cell.get((rid, vfield, u)) or by_cell.get((rid, col, u))
                     or by_url.get(u)} for u in ref_urls]
            if fc.get("preserve_ref"):
                v = next((v for (r, f, _u), v in by_cell.items() if r == rid and f == col), None)
                if v:
                    flags.append("verdict:" + v)
            if ref_urls and all(IGU_PDF.search(u) for u in ref_urls):
                flags.append("igu_pdf_only")
            current_refs = split_urls(cell(rid, it["ref_column"] or (col if col.endswith("[ref]") else "")))
            if "preserve_ref" in flags and not current_refs:
                current_refs = split_urls(cell(rid, f"{col} [ref]"))
            proposals[key] = {
                "batch": bdir.name, "id": it["id"], "kind": it["kind"],
                "row_id": rid, "cluster_id": it["cluster_id"], "column": col,
                "current": cell(rid, col) if rid else "",
                "proposed": it["value"] or it["ref_value"] if it["kind"] != "new_row" else "",
                "refs": refs, "ref_column": it["ref_column"], "current_refs": current_refs,
                "confidence": it["confidence"], "derivable": it["derivable"],
                "prev_state": it["prev_state"], "default": default, "decision": decision,
                "note": it["note"], "links": [], "flags": flags,
                # a ref line: the backend value the ref is meant to cite
                "cited_value": cell(rid, vfield) if it["kind"] == "ref" and rid else "",
                "row_data": it["row_data"] if it["kind"] == "new_row" else None,
                "cluster_label": it.get("cluster_label", ""),
            }
        batches.append({"dir": bdir.name, "mode": mode, "label": meta["label"],
                        "apply_order": meta["apply_order"], "applied": meta["applied"],
                        "counts": counts, "n": len(items)})
        all_items.extend(collect_items(bdir, mode, srm))

    # links: linked-column partners on the same row (any batch) + same id in another batch
    by_cell_key = defaultdict(list)
    for k, p in proposals.items():
        if p["row_id"]:
            by_cell_key[(p["row_id"], p["column"])].append(k)
    for k, p in proposals.items():
        if not p["row_id"]:
            continue
        links = []
        for other in by_cell_key[(p["row_id"], p["column"])]:
            if other != k:
                links.append(other)
                if "overlaps_batch" not in p["flags"]:
                    p["flags"].append("overlaps_batch")
        for pc in partner_columns(p["column"], header):
            links.extend(by_cell_key.get((p["row_id"], pc), []))
        if any(proposals[o]["column"] != p["column"] and {p["column"], proposals[o]["column"]} == STRICT_PAIR
               for o in links):
            p["flags"].append("strict_pair")
        p["links"] = links

    # vessels, ordered by live row (new discovery clusters last)
    order = {b["dir"]: (b["apply_order"], b["dir"]) for b in batches}
    grouped = defaultdict(list)
    for k, p in proposals.items():
        grouped[p["row_id"] or f"cluster:{p['batch']}:{p['cluster_id']}"].append(k)
    vessels = []
    for vid, keys in grouped.items():
        keys.sort(key=lambda k: (order[proposals[k]["batch"]], H.get(proposals[k]["column"], 999),
                                 proposals[k]["column"]))
        p0 = proposals[keys[0]]
        if p0["row_id"]:
            rid = p0["row_id"]
            vessels.append({"row_id": rid, "live_row": srm.get(rid), "new": False,
                            "in_backend": rid in rows,
                            "name": cell(rid, "Name"), "imo": cell(rid, "IMO number"),
                            "status": cell(rid, "Status"), "shipbuilder": cell(rid, "Shipbuilder"),
                            "shipowner": cell(rid, "Shipowner"), "hull": cell(rid, "Hull number"),
                            "delivery_year": cell(rid, "Delivery year"), "proposals": keys})
        else:
            rd = p0["row_data"] or {}
            vessels.append({"row_id": "", "live_row": None, "new": True, "in_backend": False,
                            "cluster_id": p0["cluster_id"], "batch": p0["batch"],
                            "name": rd.get("Name") or p0["cluster_label"], "imo": rd.get("IMO number", ""),
                            "status": rd.get("Status", ""), "shipbuilder": rd.get("Shipbuilder", ""),
                            "shipowner": rd.get("Shipowner", ""), "hull": rd.get("Hull number", ""),
                            "delivery_year": rd.get("Delivery year", ""), "proposals": keys})
    vessels.sort(key=lambda v: (v["new"], v["live_row"] if v["live_row"] is not None else 10 ** 9,
                                v.get("cluster_id", ""), v["row_id"]))

    ordered = {k: proposals[k] for v in vessels for k in v["proposals"]}
    return {
        "built": datetime.now(ET).isoformat(timespec="seconds"),
        "backend_pulled": datetime.fromtimestamp(be.path.stat().st_mtime, ET).isoformat(timespec="seconds"),
        "header": header,
        "batches": batches,
        "vessels": vessels,
        "proposals": ordered,
        "items": all_items,
    }


def check_backend(backend_path):
    """Refuse without a pull; warn when the pull is older than a day. Returns the path."""
    p = Path(backend_path) if backend_path else backend_csv_path()
    if not p.exists():
        raise SystemExit(f"{p} not found — run `python scripts/pull_backend.py` first.")
    age_h = (time.time() - p.stat().st_mtime) / 3600
    if age_h > 24:
        print(f"WARNING: {p} is {age_h:.0f} h old — re-pull (python scripts/pull_backend.py) "
              "before deciding on current values.", file=sys.stderr)
    return p


def resolve_dirs(names):
    out = []
    for n in names:
        p = Path(n)
        if not p.is_dir():
            p = ROOT / "batches" / n
        if not p.is_dir():
            raise SystemExit(f"batch dir not found: {n}")
        out.append(p.resolve())
    return out


def write(data, out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--batches", nargs="+", required=True)
    ap.add_argument("--out", default=None, help="default work/review_data.json")
    ap.add_argument("--backend", default=None)
    ap.add_argument("--info", default=None, help="review_batches.json (dir -> label / apply_order / applied)")
    args = ap.parse_args(argv)
    backend = check_backend(args.backend)
    data = build(resolve_dirs(args.batches), backend, args.info)
    out = args.out or (work_dir() / "review_data.json")
    write(data, out)
    tot = {k: sum(b["counts"].get(k, 0) for b in data["batches"]) for k in DECISIONS}
    print(f"review_data: {len(data['proposals'])} proposals ({tot['accept']} accept / {tot['hold']} hold / "
          f"{tot['reject']} reject), {len(data['vessels'])} vessels, {len(data['items'])} items -> {out}",
          file=sys.stderr)
    for b in data["batches"]:
        c = b["counts"]
        print(f"  {b['apply_order']:>3}  {b['label'][:40]:<40} {b['n']:>5}  accept {c['accept']:>4}  "
              f"hold {c['hold']:>4}  reject {c['reject']:>2}{'  (applied)' if b['applied'] else ''}",
              file=sys.stderr)
    return data


if __name__ == "__main__":
    main()
