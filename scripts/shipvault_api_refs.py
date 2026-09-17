"""
Companion refs for shipvault pages that render blank.

shipvault.com/ships/{id} is a single-page app that loads its facts from
`api/units/{id}`. When that endpoint answers with a double-encoded record (a
JSON string holding JSON) the page's own code cannot read it and every value on
the page renders empty — the record is intact, a reader just cannot see it. The
§3.8 gate reads the record through the host adapter, so such a page still
passes. For those pages the unit-record endpoint itself goes in the cell as a
SECOND ref, right after the page URL (RF §4.15 ", " join): it answers a plain
browser click and shows the figures.

This patches a batch's source JSON in place (idempotent), so the normal
build_workbook / apply_batch chain carries the companion everywhere:

    data_fill.json   fills[].new_urls, candidate_data_fills[].new_urls
    candidates.json  candidates[].row_data["<col> [ref]"]
    citations.json   cells[].url
    fix.json         corrections[].cells[].refs   (preserve_ref cells skipped)

A companion is added only where (a) the page renders blank right now and
(b) the record corroborates the cell's value (§3.8c) — the same record the page
URL was gated on, so a miss means the page ref never supported that cell; it is
logged, not papered over.

Cells already IN the backend that cite such a page get the same companion through
a candidate batch (the backend is never edited, RF §4.7): `--backend-batch <dir>`
writes a data_fill-shaped `data_fill.json` of ref-only fills (`prev_state:
"corroborate"` — the value is untouched, the companion is appended to the existing
[ref]). Cells a pending fix batch will rewrite are passed with `--skip-fix` so the
two never collide.

Usage:
    python scripts/shipvault_api_refs.py --batch batches/<dir> [--dry-run]
    python scripts/shipvault_api_refs.py --backend-batch batches/<dir> \
        [--skip-fix batches/<fix dir>/fix.json ...]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend_io import load_backend  # noqa: E402
from url_verifier import (SHIPVAULT_API, SHIPVAULT_HEADERS, _fetch,  # noqa: E402
                          corroborates)

_PAGE_RE = re.compile(r"^https?://(?:www\.)?shipvault\.com/ships/(\d+)/?$")
SOURCES = ("data_fill.json", "candidates.json", "citations.json", "fix.json")

_blank_cache: dict[str, bool] = {}


def page_unit_id(url: str) -> str | None:
    m = _PAGE_RE.match((url or "").strip())
    return m.group(1) if m else None


def api_url(uid: str) -> str:
    return SHIPVAULT_API.format(id=uid)


def renders_blank(uid: str) -> bool:
    """True when the unit endpoint answers double-encoded (the SPA shows nothing)."""
    if uid not in _blank_cache:
        page = _fetch(api_url(uid), headers=SHIPVAULT_HEADERS)
        try:
            _blank_cache[uid] = page.status == "200" and isinstance(json.loads(page.text), str)
        except (ValueError, TypeError):
            _blank_cache[uid] = False
    return _blank_cache[uid]


def with_companions(urls: list[str], value: str, where: str, log: list) -> list[str]:
    """`urls` with the API companion inserted after each blank-rendering page URL."""
    out = list(urls)
    for u in urls:
        uid = page_unit_id(u)
        if not uid or api_url(uid) in out or not renders_blank(uid):
            continue
        comp = api_url(uid)
        if value:
            ok, reason = corroborates(comp, value)
            if not ok:
                log.append({"where": where, "value": value, "url": comp,
                            "result": f"SKIPPED ({reason})"})
                continue
        out.insert(out.index(u) + 1, comp)
        log.append({"where": where, "value": value, "url": comp, "result": "ADDED"})
    return out


def _split(cell: str) -> list[str]:
    return [p.strip() for p in str(cell or "").replace("\n", ", ").split(", ") if p.strip()]


def patch(name: str, payload: dict, log: list) -> None:
    if name == "data_fill.json" or name == "citations.json":
        be = None
        for f in payload.get("fills", []) + payload.get("candidate_data_fills", []):
            value = f.get("proposed_value", "")
            if not value:                       # corroborate fill: the value is the backend's
                be = be or load_backend()
                row = be.row_by_id().get(str(f.get("row_id")), [])
                value = be.cell(row, be.header_index.get(f.get("field", "")))
            f["new_urls"] = with_companions(f.get("new_urls") or [], value,
                                            f"{f.get('row_id')}|{f.get('field')}", log)
    if name == "citations.json":
        be = load_backend()
        rows = be.row_by_id()
        for c in payload.get("cells", []):
            ref_col = be.colmap.get(c.get("field", ""))
            ref_header = be.header[ref_col] if isinstance(ref_col, int) else c.get("field", "")
            data_col = be.header_index.get(ref_header.replace(" [ref]", ""))
            value = be.cell(rows.get(str(c["row_id"]), []), data_col)
            c["url"] = ", ".join(with_companions(_split(c.get("url")), value,
                                                 f"{c['row_id']}|{ref_header}", log))
    if name == "candidates.json":
        for cand in payload.get("candidates", []):
            rd = cand.get("row_data", {})
            for h in [k for k in rd if k.endswith(" [ref]") and rd[k]]:
                rd[h] = ", ".join(with_companions(_split(rd[h]), rd.get(h[:-6], ""),
                                                  f"{cand.get('cluster_id')}|{h}", log))
    if name == "fix.json":
        for corr in payload.get("corrections", []):
            for c in corr.get("cells", []):
                if c.get("preserve_ref") or not c.get("refs"):
                    continue
                refs = c["refs"]
                urls = [r["url"] if isinstance(r, dict) else r for r in refs]
                new = with_companions(urls, c.get("new_value", ""),
                                      f"{corr.get('row_id')}|{c.get('field')}", log)
                by_url = {(r["url"] if isinstance(r, dict) else r): r for r in refs}
                c["refs"] = [by_url.get(u, {"url": u, "soft": False}) for u in new]


def backend_batch(out_dir: Path, skip_fix: list[str]) -> None:
    """Ref-only companion fills for backend [ref] cells that cite a blank-rendering page."""
    be = load_backend()
    sheet_row = be.sheet_row_map()
    pending = set()                      # (row_id, ref header) a fix batch will replace
    for fx in skip_fix:
        for corr in json.loads(Path(fx).read_text()).get("corrections", []):
            pending |= {(str(corr.get("row_id")), f"{c.get('field')} [ref]")
                        for c in corr.get("cells", []) if not c.get("preserve_ref")}
    fills, skipped = [], []
    for rid, row in be.row_by_id().items():
        for h, idx in be.header_index.items():
            if not h.endswith(" [ref]"):
                continue
            urls = _split(be.cell(row, idx))
            if not any(page_unit_id(u) for u in urls):
                continue
            field = h[:-6]
            value = be.cell(row, be.header_index.get(field))
            where = f"live row {sheet_row.get(rid, '?')} (row_id {rid}) | {h}"
            if (rid, h) in pending:
                skipped.append({"where": where, "value": value,
                                "result": "SKIPPED (a pending fix batch rewrites this [ref])"})
                continue
            if not value:
                skipped.append({"where": where, "value": "",
                                "result": "SKIPPED (no paired data value - Rule F)"})
                continue
            log: list = []
            new = [u for u in with_companions(urls, value, where, log) if u not in urls]
            skipped += [e for e in log if e["result"] != "ADDED"]
            if new:
                fills.append({
                    "row_id": rid, "field": field, "ref_field": h, "proposed_value": "",
                    "new_urls": new, "prev_state": "corroborate",
                    "existing_ref_preserved": be.cell(row, idx), "confidence": "Y",
                    "derivable": False,
                    "note": (f"live row {sheet_row.get(rid, '?')}: the cited shipvault page renders "
                             f"blank (site bug); companion unit record shows {field} = {value!r}"),
                })
    order = lambda f: (int(f["row_id"]) if f["row_id"].isdigit() else 1 << 30, f["field"])
    fills.sort(key=order)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "data_fill.json").write_text(json.dumps({
        "batch_label": "Shipvault companion refs - existing backend cells citing a "
                       "blank-rendering shipvault page",
        "scope": {"filter": "backend [ref] cells citing shipvault.com/ships/{id}",
                  "row_ids": sorted({f["row_id"] for f in fills}, key=int)},
        "fills": fills, "documented_blanks": [], "verification_log": [],
        "candidate_findings": [],
    }, indent=2, ensure_ascii=False) + "\n")
    (out_dir / "shipvault_api_refs.json").write_text(
        json.dumps({"added": len(fills), "skipped": skipped}, indent=2, ensure_ascii=False) + "\n")
    print(f"  {out_dir.name}: {len(_blank_cache)} shipvault pages cited in the backend, "
          f"{sum(_blank_cache.values())} render blank; {len(fills)} ref-only fills in "
          f"{len({f['row_id'] for f in fills})} rows, {len(skipped)} cells skipped", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--batch", help="batch directory whose source JSON to patch")
    grp.add_argument("--backend-batch", metavar="DIR",
                     help="write a ref-only data_fill.json for existing backend cells into DIR")
    ap.add_argument("--skip-fix", nargs="*", default=[], metavar="FIX_JSON",
                    help="(--backend-batch) fix.json files whose cells are left alone")
    ap.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    args = ap.parse_args()

    if args.backend_batch:
        return backend_batch(Path(args.backend_batch), args.skip_fix)

    batch = Path(args.batch)
    found = [batch / n for n in SOURCES if (batch / n).exists()]
    if not found:
        sys.exit(f"{batch}: no source JSON ({' / '.join(SOURCES)})")
    log: list = []
    for path in found:
        raw = path.read_text()
        payload = json.loads(raw)
        patch(path.name, payload, log)
        if not args.dry_run:
            # keep the file's own indent / trailing newline so the diff is the refs alone
            m = re.search(r"\n( +)\S", raw)
            path.write_text(json.dumps(payload, indent=len(m.group(1)) if m else 2,
                                       ensure_ascii=False) + ("\n" if raw.endswith("\n") else ""))
    added = [e for e in log if e["result"] == "ADDED"]
    skipped = [e for e in log if e["result"] != "ADDED"]
    if not args.dry_run:
        (batch / "shipvault_api_refs.json").write_text(
            json.dumps({"added": added, "skipped": skipped}, indent=2, ensure_ascii=False) + "\n")
    blank = sum(_blank_cache.values())
    print(f"  {batch.name}: {len(_blank_cache)} shipvault pages cited, {blank} render blank; "
          f"{len(added)} companion refs {'would be ' if args.dry_run else ''}added, "
          f"{len(skipped)} skipped (record does not corroborate the cell)", file=sys.stderr)
    for e in skipped:
        print(f"    skipped {e['where']} = {e['value']!r}: {e['result']}", file=sys.stderr)


if __name__ == "__main__":
    main()
