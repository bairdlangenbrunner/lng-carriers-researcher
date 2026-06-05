"""
Merge data-fill research outputs and run the central §3.8 gate (Data-fill SOP §6).

Combines the derivable work/data_fill.json with every work/research_*.json, dedups
on (row_id, field), re-verifies the distinct fill URLs (drops dead / soft-errored
URLs; demotes any fill that loses all its URLs to documented_blanks), and rewrites
work/data_fill.json ready for `build_workbook.py --mode data_fill`.

Trust model: the per-cluster subagents already ran the §3.8 gate (url_verifier.py)
and included only PASS URLs. This central pass is the authoritative backstop — it
catches dead/hallucinated/soft-errored URLs AND enforces the value↔ref
corroboration gate (hard-block): a live URL whose page does not contain the cell's
value (in any plausible rendering — value_variants handles "180,000"/"$254M" forms)
may NOT be cited on that cell. This is what stops a ref corroborating a *different*
number than the cell carries (the 176,400-vs-180,000 capacity defect). The gate is
value-format-aware, so a Price 254000000 rendered "$254M" still passes.

A ref dropped for non-corroboration (as opposed to dead/soft-error) is logged as a
candidate_finding so the conflicting number gets a human eye — never silently kept.
Soft-blocked URLs (HTTP 000/403, e.g. Cloudflare) can't be machine-corroborated
here; they are dropped from the auto-gate but may be re-added by hand under §3.8a
ONLY after out-of-band content confirmation that they carry the value.
"""
import glob
import json
from pathlib import Path

from paths import work_dir
from url_verifier import corroborates


def main():
    wd = work_dir()
    base = json.loads((wd / "data_fill.json").read_text())
    fills = list(base.get("fills", []))
    blanks = list(base.get("documented_blanks", []))
    vlog = list(base.get("verification_log", []))
    findings = list(base.get("candidate_findings", []))

    for rf in sorted(glob.glob(str(wd / "research_*.json"))):
        d = json.loads(Path(rf).read_text())
        fills += d.get("fills", [])
        blanks += d.get("documented_blanks", [])
        vlog += d.get("verification_log", [])
        for k in ("candidate_findings", "conflicts", "data_conflicts"):
            findings += d.get(k, [])
        print(f"  merged {Path(rf).name}: +{len(d.get('fills', []))} fills, "
              f"+{len(d.get('documented_blanks', []))} blanks")

    # Dedup on (row_id, field) — clusters are disjoint, but derivable + research
    # could in principle both touch a cell. Keep the first (derivable wins).
    seen, deduped = set(), []
    for f in fills:
        key = (str(f["row_id"]), f.get("field", ""))
        if key in seen:
            print(f"  [warn] duplicate fill {key} dropped")
            continue
        seen.add(key)
        deduped.append(f)
    fills = deduped

    # Flatten any ", "- or newline-joined URL strings into separate items (a
    # copied sibling [ref] may itself hold several URLs, §4.15).
    def _flatten(urls):
        out = []
        for u in urls or []:
            for p in str(u).replace("\n", ", ").split(", "):
                p = p.strip()
                if p and p not in out:
                    out.append(p)
        return out
    for f in fills:
        f["new_urls"] = _flatten(f.get("new_urls"))

    # Central §3.8 re-verification, now per (fill, url): a URL is judged against
    # THIS fill's value (the same URL can be cited for different values on
    # different cells — e.g. one source page for capacity AND cargo type).
    #
    #   - dead / soft-error (HTTP!=200, Cloudflare title) -> URL dropped everywhere
    #   - live but value NOT corroborated -> URL dropped from THIS fill (hard-block,
    #     §3.8 value↔ref gate) and logged as a conflict finding for human review
    #   - corroborated -> kept
    survivors, demoted, conflicts_logged = [], 0, 0
    for f in fills:
        val = f.get("proposed_value", "")
        kept, dropped_conflict = [], []
        for u in f.get("new_urls", []):
            ok, reason = corroborates(u, val)
            if ok:
                kept.append(u)
                tag = "PASS"
            elif reason.startswith("HTTP") or "soft-error" in reason:
                tag = f"DROP-dead ({reason})"
            else:
                # live page that does not carry this cell's value -> hard-block
                dropped_conflict.append(u)
                tag = f"DROP-conflict ({reason})"
            print(f"  [verify {f['row_id']}/{f.get('field','')}={val!r}] {tag}: {u}")

        for u in dropped_conflict:
            conflicts_logged += 1
            findings.append({
                "row_id": f["row_id"], "field": f.get("field", ""),
                "finding": (f"Ref does NOT corroborate proposed value {val!r} — "
                            f"page is live but lacks the value. Possible value/source "
                            f"mismatch; do not cite this URL on this cell as-is."),
                "url": u, "action": "dropped by §3.8 value↔ref gate; reconcile by hand",
            })

        # Derivable fills stand on backend-internal consistency, so a dropped
        # copied sibling ref loses the URL but never the value. Research fills that
        # lose ALL their URLs are demoted to documented_blanks (no value without a
        # corroborating citation, §3.8).
        if kept or not f.get("new_urls") or f.get("derivable"):
            f["new_urls"] = kept
            survivors.append(f)
        else:
            demoted += 1
            blanks.append({
                "row_id": f["row_id"], "field": f.get("field", ""),
                "searched": "central §3.8 re-verify (value↔ref gate)", "as_of": "2026-06-04",
                "note": "all proposed URLs failed re-verification (dead/blocked/non-corroborating); value dropped",
            })

    base["fills"] = survivors
    base["documented_blanks"] = blanks
    base["verification_log"] = vlog
    if findings:
        base["candidate_findings"] = findings
    (wd / "data_fill.json").write_text(json.dumps(base, indent=2, ensure_ascii=False))

    print(f"\nfinal fills: {len(survivors)}  (demoted {demoted} for losing all URLs; "
          f"{conflicts_logged} ref(s) dropped by value↔ref gate)")
    print(f"documented_blanks: {len(blanks)}  candidate_findings: {len(findings)}  "
          f"verify_log: {len(vlog)}")
    if conflicts_logged:
        print(f"  ⚠ {conflicts_logged} value↔ref conflict(s) logged to candidate_findings — review before build")


if __name__ == "__main__":
    main()
