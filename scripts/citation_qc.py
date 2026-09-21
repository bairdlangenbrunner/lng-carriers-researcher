"""
Citation rot sweep — grade every [ref] URL already in the backend.

Step 0 of a full research pass ([ref]-Fill SOP §3.8a). URLs decay between
passes; this sweep tells us which existing refs still resolve BEFORE new
research piles more refs on top, and it does so with the graded verdicts of
the §3.8 verifier rather than a binary "200 or not":

    ok        live, not an error/interstitial page (health only — no content
              claim unless --corroborate)
    blocked   401/403/429/5xx or a bot-wall / paywall interstitial with no
              Wayback snapshot to confirm content. NOT dead (§3.8a) — an
              environment block is not evidence about the page. Retry later,
              or human-confirm off-band.
    dead      404/410/transport failure, soft-error title, deep link that now
              redirects to the site root or to a different article. Candidate
              for replacement in a fix-mode batch.
    banned    a source the SOP forbids (GEM, abarrelfull, shorteners, search /
              tag / paginated navigation URLs, Wayback /save/). Must be replaced.

Each distinct URL is fetched ONCE (the backend's ~440 distinct URLs cover
~12,000 ref cells; one URL — the IGU World LNG Report — backs most of them),
so the sweep is cheap. With --corroborate every (cell value, URL) pair is
additionally run through the §3.8c value↔ref gate, which is the expensive
but decisive form: it reports refs that are live yet do not carry the value
they are cited on (`uncorroborated`).

Outputs (work/, gitignored):
    citation_qc.csv        one row per distinct URL: verdict, status, reason,
                           final_url, title, n_cells, n_rows, sheet_rows
                           (live tab rows, sample), fields
    citation_qc_cells.csv  (--corroborate) one row per (cell, URL): grade
    citation_qc.jsonl      the verifier's audit log for the run

Usage:
    python scripts/citation_qc.py                       # whole backend, health only
    python scripts/citation_qc.py --sheet-rows 900-1220 # live tab rows
    python scripts/citation_qc.py --rows 1100-1220      # by column-A row_id
    python scripts/citation_qc.py --corroborate         # + value↔ref gate per cell
    python scripts/citation_qc.py --delay 1.5 --resume  # polite; skip URLs already graded
    python scripts/citation_qc.py --resume --regrade dead,blocked  # re-fetch only those grades
    python scripts/citation_qc.py --hosts marinetraffic.org,lngprime.com

Never edits the backend. Findings route through a fix-mode batch (QC SOP §4)
or the next [ref]-fill batch.
"""
import argparse
import csv
import re
import sys
import time
from collections import Counter, defaultdict
from urllib.parse import urlsplit

import url_verifier
from backend_io import load_backend
from paths import backend_csv_path, work_dir
from igu_refs import corroborates_cell
from url_verifier import check_url, citable_form, classify, corroborates

_URL_SPLIT = re.compile(r"[\s,;|]+")


def split_urls(cell: str) -> list[str]:
    """URLs in a [ref] cell (cells hold one URL or a ', '-joined bundle)."""
    out = []
    for p in _URL_SPLIT.split(cell or ""):
        p = p.strip().rstrip(".)]")
        if p.lower().startswith("http") and p not in out:
            out.append(p)
    return out


def _parse_range(spec: str) -> set[int] | None:
    if not spec:
        return None
    ids = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            ids.update(range(int(a), int(b) + 1))
        else:
            ids.add(int(part))
    return ids


def collect(be, row_ids=None, sheet_rows=None, hosts=None):
    """-> (url -> {cells:[(row_id, sheet_row, field, value)], ...})"""
    srmap = be.sheet_row_map()
    ri = be.colmap["row_id"]
    ref_cols = [(i, h) for i, h in enumerate(be.header) if h.endswith("[ref]")]
    by_url = defaultdict(list)
    for r in be.data:
        rid = be.cell(r, ri)
        if not rid:
            continue
        sr = srmap.get(rid)
        if row_ids is not None and (not rid.isdigit() or int(rid) not in row_ids):
            continue
        if sheet_rows is not None and sr not in sheet_rows:
            continue
        for ci, h in ref_cols:
            for u in split_urls(be.cell(r, ci)):
                host = (urlsplit(u).hostname or "").lower()
                if hosts and not any(host == x or host.endswith("." + x) for x in hosts):
                    continue
                field = h[:-len(" [ref]")].strip()
                vi = be.header_index.get(field)
                value = be.cell(r, vi) if vi is not None else ""
                by_url[u].append((rid, sr, field, value))
    return by_url


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--backend", default=str(backend_csv_path()))
    ap.add_argument("--rows", default="", help="row_id range/list, e.g. 1100-1220")
    ap.add_argument("--sheet-rows", default="", help="LIVE sheet tab rows, e.g. 900-1220")
    ap.add_argument("--hosts", default="", help="comma-separated host filter")
    ap.add_argument("--corroborate", action="store_true",
                    help="also run the §3.8c value↔ref gate for every (cell, URL)")
    ap.add_argument("--delay", type=float, default=0.5,
                    help="seconds between live fetches (default 0.5)")
    ap.add_argument("--no-wayback", action="store_true")
    ap.add_argument("--resume", action="store_true",
                    help="skip URLs already graded in the existing citation_qc.csv")
    ap.add_argument("--regrade", default="",
                    help="with --resume: comma-separated verdicts to re-fetch anyway, e.g. dead,blocked")
    ap.add_argument("--limit", type=int, default=0, help="stop after N distinct URLs")
    ap.add_argument("--out", default=str(work_dir() / "citation_qc.csv"))
    args = ap.parse_args()

    url_verifier.FETCH_DELAY = args.delay
    url_verifier.WAYBACK_ENABLED = not args.no_wayback
    url_verifier.set_log_path(str(work_dir() / "citation_qc.jsonl"))

    be = load_backend(args.backend)
    hosts = [h.strip().lower() for h in args.hosts.split(",") if h.strip()] or None
    by_url = collect(be, _parse_range(args.rows), _parse_range(args.sheet_rows), hosts)

    prior, carried = {}, {}
    if args.resume:
        try:
            with open(args.out, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    prior[row["url"]] = row
        except FileNotFoundError:
            pass
        # Rows outside this run's selection (--hosts / --rows / --sheet-rows)
        # are carried into the output untouched, so a filtered re-run never
        # shrinks the sweep file.
        carried = {u: r for u, r in prior.items() if u not in by_url}
        regrade = {v.strip() for v in args.regrade.split(",") if v.strip()}
        if regrade:
            prior = {u: r for u, r in prior.items() if r["verdict"] not in regrade}

    urls = sorted(by_url, key=lambda u: (-len(by_url[u]), u))
    if args.limit:
        urls = urls[:args.limit]
    print(f"{len(urls)} distinct URLs across {sum(len(v) for v in by_url.values())} ref cells "
          f"({len(prior)} already graded)", file=sys.stderr)

    results = []
    for n, u in enumerate(urls, 1):
        cells = by_url[u]
        if u in prior:
            row = dict(prior[u])
        else:
            info = check_url(u)
            row = {"url": u, "verdict": info["verdict"], "status": info["status"],
                   "reason": info["reason"], "final_url": info["final_url"],
                   "title": info["title"][:120], "is_pdf": int(info["is_pdf"])}
        rows_ = sorted({sr for _, sr, _, _ in cells if sr})
        row.update({
            "n_cells": len(cells), "n_rows": len(rows_),
            "sheet_rows": ",".join(str(x) for x in rows_[:12]) + (",…" if len(rows_) > 12 else ""),
            "fields": "; ".join(sorted({f for _, _, f, _ in cells})),
            "host": (urlsplit(u).hostname or "").lower(),
        })
        results.append(row)
        print(f"  [{n}/{len(urls)}] {row['verdict']:<8} {row['status']:>3}  {u[:100]}", file=sys.stderr)

    # Second look at every fresh `dead` verdict: HTTP 000 flaps and CDN
    # hiccups flip on a retry, and `dead` is the grade that drops refs.
    recheck = [r for r in results if r["verdict"] == "dead" and r["url"] not in prior]
    if recheck:
        print(f"re-checking {len(recheck)} dead verdict(s) after a pause", file=sys.stderr)
        time.sleep(max(5.0, args.delay * 10))
        for r in recheck:
            url_verifier.clear_cache(r["url"])
            info = check_url(r["url"])
            if info["verdict"] != "dead":
                first = r["reason"]
                r.update({"verdict": info["verdict"], "status": info["status"],
                          "reason": f"{info['reason']} [first pass: {first}]",
                          "final_url": info["final_url"], "title": info["title"][:120]})
                print(f"  flipped -> {info['verdict']:<8} {r['url'][:100]}", file=sys.stderr)

    fields = ["url", "host", "verdict", "status", "reason", "final_url", "title", "is_pdf",
              "n_cells", "n_rows", "sheet_rows", "fields"]
    if carried:
        results.extend(carried.values())
        print(f"carried {len(carried)} previously graded URL(s) outside this selection",
              file=sys.stderr)
    order = {"banned": 0, "dead": 1, "blocked": 2, "ok": 3}
    results.sort(key=lambda r: (order.get(r["verdict"], 9), -int(r["n_cells"]), r["url"]))
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)

    if args.corroborate:
        cell_out = str(work_dir() / "citation_qc_cells.csv")
        ok_urls = {r["url"] for r in results if r["verdict"] == "ok"}
        _imo = be.header_index.get("IMO number")
        imo_by_id = {rid: be.cell(row, _imo).strip() for rid, row in be.row_by_id().items()} if _imo is not None else {}
        with open(cell_out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["sheet_row", "row_id", "field", "value", "url", "grade", "reason"])
            for u in urls:
                for rid, sr, field, value in by_url[u]:
                    if u not in ok_urls:
                        grade = next(r["verdict"] for r in results if r["url"] == u)
                        w.writerow([sr, rid, field, value, u, grade, "(url not ok — see citation_qc.csv)"])
                        continue
                    if not value.strip():
                        w.writerow([sr, rid, field, value, u, "orphan", "ref with blank value (Rule F)"])
                        continue
                    # an IGU report PDF is held to what it prints for this row's IMO (igu_refs)
                    ok, reason = corroborates_cell(u, value, field, imo_by_id.get(rid, ""))
                    if not ok and citable_form(u) != u and classify(reason) == "uncorroborated":
                        # a landing page prints no per-vessel value; the report it stands for does
                        ok, reason = corroborates_cell(citable_form(u), value, field, imo_by_id.get(rid, ""))
                        if ok:
                            reason = f"OK (via the report PDF {citable_form(u)} — cite it, not the landing page)"
                    if not ok and field == "Price" and classify(reason) == "uncorroborated":
                        # DF §5a: a per-vessel Price divided out of an order total cites
                        # the page stating the TOTAL. The backend keeps no divisor, so
                        # try value x N (to the $m) — the Price cells sharing this URL and
                        # value first, then any plausible order size.
                        sibs = sum(1 for _r, _s, fl, v in by_url[u] if fl == "Price" and v == value)
                        try:
                            per = float(value.replace(",", ""))
                        except ValueError:
                            per = 0
                        for n in dict.fromkeys([sibs, *range(2, 13)]) if per >= 1_000_000 else ():
                            total = int(round(per * n, -6))
                            if n >= 2 and corroborates(u, str(total))[0]:
                                ok, reason = True, f"OK (order total {total} / {n} vessels, DF §5a)"
                                break
                    w.writerow([sr, rid, field, value, u, "ok" if ok else classify(reason), reason])
        print(f"cell-level gate -> {cell_out}", file=sys.stderr)

    tally = Counter(r["verdict"] for r in results)
    cells = Counter()
    for r in results:
        cells[r["verdict"]] += int(r["n_cells"])
    print(f"\ncitation_qc -> {args.out}", file=sys.stderr)
    for v in ("ok", "blocked", "dead", "banned"):
        print(f"  {v:<8} {tally.get(v, 0):4d} URLs  {cells.get(v, 0):6d} cells", file=sys.stderr)
    by_host = defaultdict(Counter)
    for r in results:
        if r["verdict"] != "ok":
            by_host[r["host"]][r["verdict"]] += 1
    if by_host:
        print("  non-ok by host:", file=sys.stderr)
        for h, c in sorted(by_host.items(), key=lambda kv: -sum(kv[1].values()))[:25]:
            print(f"    {sum(c.values()):3d}  {h:<40} {dict(c)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
