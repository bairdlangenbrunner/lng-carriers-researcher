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

Two guards on what may skip or bend the gate (Data-fill SOP §5 / §5a):
  - `derivable: true` is honoured only on the §5 autofill columns (DERIVABLE_FIELDS).
    On any other column the flag is cleared, so a research fill can never ride it
    past the gate or into a default `accept`.
  - A per-vessel Price divided out of a reported order total carries
    `derived_from: {"total": ..., "n": ...}`. Its refs are gated on the TOTAL (the
    figure the page states) and kept in `Price [ref]`; confidence is capped at Y.
"""
import glob
import json
import sys
from datetime import date
from pathlib import Path

import confidence
from paths import work_dir
from igu_refs import corroborates_cell
from url_verifier import citable_forms, classify

# Data-fill SOP §5 — the only columns a backend-internal autofill may fill.
DERIVABLE_FIELDS = {"Shipowner country/area", "Capacity units", "Price currency",
                    "Shipbuilder yard country/area", "Shipbuilder yard country/area [ref]"}


def is_derivable_field(field: str) -> bool:
    return field in DERIVABLE_FIELDS or field.startswith("Yard location")


def order_total(f: dict) -> tuple[str | None, str | None]:
    """(total, problem) for a per-vessel Price derived from an order total (DF §5a).

    (None, None) when the fill declares no `derived_from`. The total is what the
    source states, so it — not the per-vessel quotient — is what the gate checks.
    """
    d = f.get("derived_from")
    if not d:
        return None, None
    if f.get("field") != "Price":
        return None, "derived_from is only valid on Price"
    try:
        total, n = int(float(d["total"])), int(d["n"])
        val = int(float(str(f.get("proposed_value", "")).replace(",", "")))
    except (KeyError, TypeError, ValueError):
        return None, "derived_from needs a numeric total and n"
    if n < 2:
        return None, "derived_from n must be >= 2 (a single-vessel price is not derived)"
    if abs(total / n - val) > 1:
        return None, f"proposed_value {val} != {total} / {n}"
    return str(total), None


def _imo_by_row_id() -> dict:
    """row_id -> IMO from the fresh pull ({} without one: the IGU check then abstains)."""
    try:
        from backend_io import BackendNotPulled, load_backend
        be = load_backend()
    except (BackendNotPulled, FileNotFoundError):
        return {}
    i = be.header_index.get("IMO number")
    return {rid: be.cell(row, i).strip() for rid, row in be.row_by_id().items()} if i is not None else {}


def main():
    wd = work_dir()
    base_path = wd / "data_fill.json"
    if not base_path.exists():
        sys.exit(f"error: {base_path} not found — run `python scripts/derive_fills.py "
                 "--since <YYYY-MM-DD>` (or derive_corroborate.py) first")
    base = json.loads(base_path.read_text())
    fills = list(base.get("fills", []))
    blanks = list(base.get("documented_blanks", []))
    vlog = list(base.get("verification_log", []))
    findings = list(base.get("candidate_findings", []))

    research_files = [p for p in sorted(glob.glob(str(wd / "research_*.json")))
                      if Path(p).name != "research_tasks.json"]
    for rf in research_files:
        d = json.loads(Path(rf).read_text())
        fills += d.get("fills", [])
        blanks += d.get("documented_blanks", [])
        vlog += d.get("verification_log", [])
        for k in ("candidate_findings", "conflicts", "data_conflicts"):
            findings += d.get(k, [])
        print(f"  merged {Path(rf).name}: +{len(d.get('fills', []))} fills, "
              f"+{len(d.get('documented_blanks', []))} blanks", file=sys.stderr)
    print(f"  merged {len(research_files)} research file(s) from {wd}", file=sys.stderr)
    if not research_files:
        print("  [warn] no work/research_*.json found — output will hold only the "
              "derivable fills already in data_fill.json", file=sys.stderr)

    # Dedup on (row_id, field) — clusters are disjoint, but derivable + research
    # could in principle both touch a cell. Keep the first (derivable wins).
    seen, deduped = set(), []
    for f in fills:
        key = (str(f["row_id"]), f.get("field", ""))
        if key in seen:
            print(f"  [warn] duplicate fill {key} dropped", file=sys.stderr)
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
    #   - banned (GEM / abarrelfull / shortener / navigation URL) -> dropped everywhere
    #   - dead (HTTP 404/410/000, soft-error title, redirect to site root) -> dropped
    #     everywhere
    #   - blocked (401/403/429/5xx or a bot-wall / paywall interstitial, and no
    #     Wayback snapshot carrying the value) -> dropped from THIS fill but logged
    #     as a *blocked* finding, not a conflict: §3.8a — an environment block is
    #     not evidence the page is dead or that the value is wrong. Retry later
    #     or confirm by hand.
    #   - live but value NOT corroborated -> URL dropped from THIS fill (hard-block,
    #     §3.8c value↔ref gate) and logged as a conflict finding for human review
    #   - corroborated (live page or its Wayback snapshot) -> kept
    survivors, demoted, conflicts_logged = [], 0, 0
    imo_by_id = _imo_by_row_id()
    for f in fills:
        val = f.get("proposed_value", "")
        if f.get("derivable") and not is_derivable_field(f.get("field", "")):
            print(f"  [warn] {f['row_id']}/{f.get('field','')}: derivable=true is reserved for "
                  "the DF §5 autofill columns — cleared; gated as a research fill", file=sys.stderr)
            f["derivable"] = False

        # DF §5a: a per-vessel Price divided out of an order total is gated on the
        # total (what the page says); the quotient never appears on the page.
        total, problem = order_total(f)
        if problem:
            print(f"  [warn] {f['row_id']}/{f.get('field','')}: {problem} — derived_from ignored",
                  file=sys.stderr)
            f.pop("derived_from", None)
        if total:
            val = total

        kept, passes, dropped_conflict, dropped_blocked = [], [], [], []
        for u in citable_forms(f.get("new_urls", [])):   # IGU landing page -> the edition's PDF
            # an IGU report PDF is held to what it prints for this row's IMO (igu_refs, IG §1)
            ok, reason = corroborates_cell(u, val, f.get("field", ""), imo_by_id.get(str(f["row_id"]), ""))
            grade = classify(reason)
            if ok:
                kept.append(u)
                passes.append((u, reason))
                tag = "PASS" if reason == "OK" else f"PASS ({reason})"
            elif grade in ("dead", "banned"):
                tag = f"DROP-{grade} ({reason})"
            elif grade == "blocked":
                dropped_blocked.append((u, reason))
                tag = f"DROP-blocked ({reason})"
            else:
                # live page that does not carry this cell's value -> hard-block
                dropped_conflict.append(u)
                tag = f"DROP-conflict ({reason})"
            print(f"  [verify {f['row_id']}/{f.get('field','')}={val!r}] {tag}: {u}",
                  file=sys.stderr)

        for u in dropped_conflict:
            conflicts_logged += 1
            findings.append({
                "row_id": f["row_id"], "field": f.get("field", ""),
                "finding": (f"Ref does NOT corroborate proposed value {val!r} — "
                            f"page is live but lacks the value. Possible value/source "
                            f"mismatch; do not cite this URL on this cell as-is."),
                "url": u, "action": "dropped by §3.8 value↔ref gate; reconcile by hand",
            })
        for u, reason in dropped_blocked:
            findings.append({
                "row_id": f["row_id"], "field": f.get("field", ""),
                "finding": (f"Ref could not be verified for {val!r}: {reason}. "
                            f"Bot-block / paywall ≠ dead (§3.8a); the value is NOT "
                            f"contradicted."),
                "url": u, "action": "retry the gate later or confirm off-band and re-add",
            })

        # §5 (RF rev 28): the grade is what the gate did, not the researcher's label.
        # Derivable autofills stand on backend-internal consistency, not on a URL.
        if not f.get("derivable"):
            caps = []
            if total:
                caps.append(confidence.CAP_DERIVED)
            if dropped_conflict:
                caps.append(confidence.CAP_CONFLICT)
            if f.get("cap") or f.get("cap_reason"):
                caps.append(f.get("cap_reason") or "researcher capped this cell at Y")
            caps.append(confidence.note_cap(f.get("note")))
            conf, why = confidence.grade(passes, field=f.get("field", ""), value=val, caps=caps)
            if conf != f.get("confidence"):
                print(f"  [conf {f['row_id']}/{f.get('field','')}] "
                      f"{f.get('confidence', '-')} -> {conf}: {why}", file=sys.stderr)
            f["confidence"], f["confidence_why"] = conf, why

        # Corroborate batch: the grandfathered IGU ref is kept out of new_urls by the
        # selector, so the gate never tested it — re-prepend it (it stays FIRST) and
        # require >=2 SURVIVING independent corroborators for "full". The value is
        # never dropped here (a corroborate batch never writes the value column);
        # a cell short of two survivors is flagged "partial" for a human follow-up.
        if f.get("prev_state") == "corroborate":
            igu = base.get("scope", {}).get("igu_url", "")
            corrob = [u for u in kept if u != igu]
            f["new_urls"] = ([igu] + corrob) if igu else corrob
            if len(corrob) >= 2:
                f["corroboration"] = "full"
            else:
                f["corroboration"] = "partial"
                # keys chosen to match apply_batch._conflict_row so conflicts.csv is populated
                findings.append({
                    "row_id": f["row_id"], "column": f.get("field", ""),
                    "backend_value": val, "proposed_value": val,
                    "sources": "; ".join(corrob) or "(none)",
                    "recommendation": (f"only {len(corrob)} surviving corroborator(s); need >=2. "
                                       "IGU kept; cell left partially corroborated — "
                                       "find another independent source before promotion."),
                })
            survivors.append(f)
            continue

        # Derivable fills stand on backend-internal consistency, so a dropped
        # copied sibling ref loses the URL but never the value (companion cells —
        # Price currency, Capacity units — ride their parent's citation the same
        # way). Any other fill left with no URL is demoted to documented_blanks
        # (no value without a corroborating citation, §3.8).
        if kept or f.get("derivable"):
            f["new_urls"] = kept
            survivors.append(f)
        else:
            demoted += 1
            blanks.append({
                "row_id": f["row_id"], "field": f.get("field", ""),
                "searched": "central §3.8 re-verify (value↔ref gate)",
                "as_of": date.today().isoformat(),
                "note": "no proposed URL survived re-verification (none given, or dead/blocked/non-corroborating); value dropped",
            })

    base["fills"] = survivors
    base["documented_blanks"] = blanks
    base["verification_log"] = vlog
    if findings:
        base["candidate_findings"] = findings
    (wd / "data_fill.json").write_text(json.dumps(base, indent=2, ensure_ascii=False))

    n_partial = sum(1 for f in survivors if f.get("corroboration") == "partial")
    n_full = sum(1 for f in survivors if f.get("corroboration") == "full")
    print(f"\nfinal fills: {len(survivors)}  (demoted {demoted} for losing all URLs; "
          f"{conflicts_logged} ref(s) dropped by value↔ref gate)", file=sys.stderr)
    if n_full or n_partial:
        print(f"corroborate: {n_full} full (>=2 survivors), {n_partial} partial (<2; IGU kept, flagged)",
              file=sys.stderr)
    print(f"documented_blanks: {len(blanks)}  candidate_findings: {len(findings)}  "
          f"verify_log: {len(vlog)}", file=sys.stderr)
    if conflicts_logged:
        print(f"  ⚠ {conflicts_logged} value↔ref conflict(s) logged to candidate_findings "
              "— review before build", file=sys.stderr)


if __name__ == "__main__":
    main()
