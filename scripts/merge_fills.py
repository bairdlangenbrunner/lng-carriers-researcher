"""
Merge data-fill research outputs and run the central §3.8 gate (Data-fill SOP §6).

Combines the derivable work/data_fill.json with every work/research_*.json, dedups
on (row_id, field), re-verifies the distinct fill URLs (drops dead / soft-errored
URLs; demotes any fill that loses all its URLs to documented_blanks), and rewrites
work/data_fill.json ready for `build_workbook.py --mode data_fill`.

Trust model: the per-cluster subagents already ran the §3.8 gate (url_verifier.py)
and included only PASS URLs. This central pass is the authoritative backstop — it
catches dead/hallucinated/soft-errored URLs. A URL that is live (HTTP 200, not a
soft-error) but whose page doesn't contain the raw proposed value verbatim is KEPT
(the subagent verified it with a smarter, value-format-aware substring; a Price like
254000000 legitimately renders as "$254M").
"""
import glob
import json
from pathlib import Path

from paths import work_dir
from url_verifier import verify_url


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

    # Central §3.8 re-verification over distinct fill URLs.
    url_value = {}
    for f in fills:
        for u in f.get("new_urls", []):
            url_value.setdefault(u, f.get("proposed_value", ""))
    dead = set()
    for u, val in sorted(url_value.items()):
        ok, reason = verify_url(u, [val] if val else ["http"])
        if ok:
            tag = "PASS"
        elif reason.startswith("HTTP") or "soft-error" in reason:
            dead.add(u)
            tag = f"DROP ({reason})"
        else:
            tag = f"live ({reason})"
        print(f"  [verify] {tag}: {u}")

    survivors, demoted = [], 0
    for f in fills:
        kept = [u for u in f.get("new_urls", []) if u not in dead]
        # Derivable fills stand on backend-internal consistency, so a dead/blocked
        # copied sibling ref drops the URL but never the value. Research fills that
        # lose ALL their URLs are demoted to documented_blanks (no value without a
        # passing citation, §3.8).
        if kept or not f.get("new_urls") or f.get("derivable"):
            f["new_urls"] = kept
            survivors.append(f)
        else:
            demoted += 1
            blanks.append({
                "row_id": f["row_id"], "field": f.get("field", ""),
                "searched": "central §3.8 re-verify", "as_of": "2026-06-04",
                "note": "all proposed URLs failed re-verification (dead/blocked); value dropped",
            })

    base["fills"] = survivors
    base["documented_blanks"] = blanks
    base["verification_log"] = vlog
    if findings:
        base["candidate_findings"] = findings
    (wd / "data_fill.json").write_text(json.dumps(base, indent=2, ensure_ascii=False))

    print(f"\nfinal fills: {len(survivors)}  (dropped {demoted} for dead URLs)")
    print(f"documented_blanks: {len(blanks)}  candidate_findings: {len(findings)}  "
          f"verify_log: {len(vlog)}")


if __name__ == "__main__":
    main()
