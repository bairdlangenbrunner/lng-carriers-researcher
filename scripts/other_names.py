"""
Former names -> `Other names` (RF §4.16).

Whenever a batch proposes a different `Name` for a backend row, the name the row
carried until then is proposed as an ADDITION to the row's `Other names` cell — a
reader holding the previous release can still find the vessel. This script derives
those proposals from a fix batch's `Name` cells, so the rule does not depend on
anyone remembering it:

    python scripts/other_names.py --batch batches/<dir> | work/<name>_fix.json
        patch the batch's fix.json in place (idempotent) — run BEFORE build_workbook.py,
        beside shipvault_api_refs.py. Each Name cell gains an `Other names` sibling.

    python scripts/other_names.py --collect batches/<dir> [batches/<dir> ...] --out work/x_fix.json
        a standalone fix.json for batches that are already built and gated (rebuilding
        them would re-gate every other ref). Build it as its own fix batch.

The `Other names` cell it writes (fix-mode schema, scripts/build_workbook.py):

    { "field": "Other names", "append_ref": true,
      "new_value":  "LNG Pioneer; Pioneer Spirit",   # existing cell + "; " + former name
      "gate_value": "Pioneer Spirit",                # what the §3.8c gate runs on
      "refs": [...], "confidence": "G" | "Y", "note": "..." }

Refs: the candidates are the refs the batch cites for the NEW name (pages about this
vessel — a shipvault record carries the yard number behind a `Hull 2541 (Hanwha)`
placeholder, IGU prints `(ex-…)`) plus the row's existing `Name [ref]`; each is kept
only if its page contains the former name (§3.8c) — the name itself, not scattered
tokens, and never where the former name is part of the new one (`LNGT Americas` ->
`Karadeniz LNGT Americas`: any page printing the new name would "pass"). An IGU
report PDF wraps its `(ex-…)` names across table lines, so there the name is checked
against the coordinate extraction (work/igu_fleet_<edition>.json, the row's IMO).
When nothing passes for a real former name, the shipvault record for the row's IMO is
the last candidate: shipvault lags renames, so it often still carries the old name
(`ENERGY FRONTIER TBR`). No ref passing is not a reason to
drop the proposal — the former name is the backend's own published value — but the
cell is then Y (held by default). Tracker hosts are paced and are not asked about
hull placeholders (they never print a yard number); vesselfinder is not asked at all
(`--ask-vesselfinder` to override; see CLAUDE.md on the 2026-09-17 IP ban).

Not a former name, so skipped (logged, `--include <row_id>` overrides):
  - a spelling / truncation correction (`Greenenergy Wind` -> `Greenergy Wind`,
    `Hoegh` -> `Hoegh Esperanza`) — the old string was a defect, never a name;
  - a name that belongs to another row (`Puteri Sarawak` sat on the wrong hull; the
    batch gives it to the right one);
  - a placeholder restyled as another placeholder (QC §4 cosmetic normalization).

Every Name cell is stamped `former_name: <outcome>` so build_workbook.py can warn
about a Name change nobody ran this over.
"""
import argparse
import csv
import json
import re
import sys
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend_io import load_backend  # noqa: E402

FIELD, REF_FIELD, SEP = "Other names", "Other names [ref]", "; "
SPELLING_RATIO = 0.85
TRACKER_HOSTS = ("vesselfinder.com", "marinetraffic.com", "marinetraffic.org")
TRACKER_DELAY, DEFAULT_DELAY = 10.0, 1.0
# landing pages that surface no per-vessel value: they cannot pass §3.8c (IG §5.4)
UNGATEABLE = ("igu.org/igu-reports",)

_HULL_RE = re.compile(r"^Hull\s+\S+", re.I)
_SYNTH_RE = re.compile(r"^[^()]+\([^()]*\)$")      # "Builder (Owner N)", "Hull 2541 (Hanwha)"


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def is_placeholder(name: str) -> bool:
    n = str(name or "").strip()
    return bool(_HULL_RE.match(n) or _SYNTH_RE.match(n))


def split_names(cell: str) -> list[str]:
    return [p.strip() for p in str(cell or "").split(";") if p.strip()]


def is_spelling_fix(former: str, new: str) -> bool:
    """A typo or truncation of the SAME name, as opposed to a different name."""
    a, b = fold(former), fold(new)
    if is_placeholder(former) or not a or not b:
        return False
    if b.startswith(a + " "):                        # 'Hoegh' -> 'Hoegh Esperanza'
        return True
    return SequenceMatcher(None, a, b).ratio() >= SPELLING_RATIO


def classify(former: str, new: str, existing_cell: str, claimed_by: str | None) -> str | None:
    """Why this Name change does NOT yield an Other-names proposal (None = it does)."""
    if not former.strip():
        return "row had no name"
    if fold(former) == fold(new):
        return "same name (case / punctuation only)"
    if fold(former) in {fold(x) for x in split_names(existing_cell)}:
        return "already in Other names"
    if is_placeholder(former) and is_placeholder(new):
        return "placeholder restyled as a placeholder"
    if claimed_by:
        return f"name belongs to another row ({claimed_by})"
    if is_spelling_fix(former, new):
        return "spelling / truncation correction"
    return None


def _split_refs(cell: str) -> list[str]:
    return [p.strip() for p in str(cell or "").replace("\n", ", ").split(", ") if p.strip()]


def _host(url: str) -> str:
    return (urlparse(url).netloc or "").lower().removeprefix("www.")


class Gate:
    """§3.8c on the former name, paced per host (uncached fetches only)."""

    def __init__(self, enabled=True, ask_vesselfinder=False, sleep=time.sleep, igu_names=None):
        self.enabled, self.ask_vf, self.sleep = enabled, ask_vesselfinder, sleep
        self.last, self.seen, self.log = {}, {}, []
        self._igu = igu_names          # {edition: {imo: printed name}}; loaded on first use

    def _igu_prints(self, url: str, imo: str, former: str) -> bool:
        """The IGU report's name cell for this IMO carries the former name (`(ex-…)`)."""
        m = re.search(r"igu-world-lng-report-(\d{4})", url.lower())
        if not m or not imo:
            return False
        if self._igu is None:
            self._igu = load_igu_names()
        printed = self._igu.get(m.group(1), {}).get(str(imo).strip(), "")
        return f" {fold(former)} " in f" {fold(printed)} "

    def shipvault_candidates(self, imo: str) -> list[str]:
        """Page + unit-record URL of the shipvault record for an IMO (RF §6a.8)."""
        if not self.enabled or not re.fullmatch(r"\d{7}", str(imo or "").strip()):
            return []
        from imo_tracker import shipvault_search
        from shipvault_api_refs import api_url, page_unit_id, renders_blank
        wait = self.last.get("shipvault.com", 0) + DEFAULT_DELAY - time.monotonic()
        if wait > 0:
            self.sleep(wait)
        hits = shipvault_search(imo)
        self.last["shipvault.com"] = time.monotonic()
        out = []
        for h in hits[:1]:
            uid = page_unit_id(h["url"])
            out.append(h["url"])
            if uid and renders_blank(uid):           # the blank-page companion (RF §6a.8 rev 21)
                out.append(api_url(uid))
        return out

    def _skip(self, url: str, former: str, new: str = "") -> str | None:
        host = _host(url)
        if new and f" {fold(former)} " in f" {fold(new)} ":
            return "former name is part of the new name — a page printing the new name proves nothing"
        if any(u in url for u in UNGATEABLE):
            return "landing page, no per-vessel value"
        if host.endswith("vesselfinder.com") and not self.ask_vf:
            return "vesselfinder not asked (IP ban)"
        if is_placeholder(former) and any(host.endswith(t) for t in TRACKER_HOSTS):
            return "tracker pages do not print yard numbers"
        return None

    def passing(self, urls: list[str], former: str, where: str, new: str = "", imo: str = "") -> list[str]:
        from url_verifier import corroborates, url_ban_reason
        kept = []
        for url in dict.fromkeys(urls):
            why = url_ban_reason(url) or self._skip(url, former, new)
            if why or not self.enabled:
                self.log.append({"where": where, "url": url, "former": former,
                                 "verdict": f"not asked: {why or 'gate off'}"})
                continue
            host = _host(url)
            if url not in self.seen:
                gap = TRACKER_DELAY if any(host.endswith(t) for t in TRACKER_HOSTS) else DEFAULT_DELAY
                wait = self.last.get(host, 0) + gap - time.monotonic()
                if wait > 0:
                    self.sleep(wait)
            ok, reason = corroborates(url, former)
            if ok and "all tokens present" in reason:
                # the scattered-token fallback suits an owner string, not a vessel name:
                # 'Energy Frontier' would pass on any long report. The phrase or nothing —
                # except an IGU PDF, whose table wraps names: ask the coordinate extraction.
                if self._igu_prints(url, imo, former):
                    reason = "OK (IGU name cell for this IMO, coordinate extraction)"
                else:
                    ok, reason = False, "only scattered tokens, not the name"
            self.last[host], self.seen[url] = time.monotonic(), True
            self.log.append({"where": where, "url": url, "former": former,
                             "verdict": ("PASS" if reason == "OK" else f"PASS ({reason})") if ok
                             else f"no: {reason}"})
            if ok:
                kept.append(url)
        return kept


def load_igu_names() -> dict:
    """{edition: {imo: name as printed}} from the igu_fleet.py extractions in work/."""
    from paths import work_dir
    out = {}
    for f in sorted(work_dir().glob("igu_fleet_*.json")):
        d = json.loads(f.read_text())
        out[str(d.get("edition"))] = {str(r.get("imo")): str(r.get("name") or "")
                                      for key in ("fleet", "orderbook") for r in d.get(key, [])
                                      if r.get("imo")}
    return out


def name_cells(payload: dict):
    for corr in payload.get("corrections", []):
        for c in corr.get("cells", []):
            if c.get("field") == "Name":
                yield corr, c


def build_cells(payloads: list[tuple[str, dict]], be, gate: Gate, include=()) -> tuple[list, list]:
    """-> (proposals, skipped). A proposal = {row_id, source, name_cell, cell}."""
    rows, live = be.row_by_id(), be.sheet_row_map()
    hi = be.header_index
    include = {str(x) for x in include}
    # who is being given which name, to catch a name that was parked on the wrong row
    claimed = {}
    for _src, payload in payloads:
        for corr, c in name_cells(payload):
            claimed.setdefault(fold(c.get("new_value", "")), str(corr["row_id"]))

    proposals, skipped, done = [], [], set()
    for src, payload in payloads:
        for corr, c in name_cells(payload):
            rid, new = str(corr["row_id"]), str(c.get("new_value", "")).strip()
            row = rows.get(rid)
            if row is None:
                continue
            former = be.cell(row, hi.get("Name"))
            existing = be.cell(row, hi.get(FIELD))
            other = claimed.get(fold(former))
            claimed_by = f"live row {live.get(other)}" if other and other != rid else None
            why = classify(former, new, existing, claimed_by)
            if why and rid in include and why != "already in Other names":
                why = None
            if not why and (rid, fold(former)) in done:
                why = "proposed from an earlier batch in this run"
            c["former_name"] = f"skipped: {why}" if why else "proposed"
            rec = {"row_id": rid, "live_row": live.get(rid), "source": src,
                   "former": former, "new": new}
            if why:
                skipped.append({**rec, "reason": why})
                continue
            done.add((rid, fold(former)))
            cand = [r["url"] if isinstance(r, dict) else r for r in c.get("refs", [])]
            cand += _split_refs(be.cell(row, hi.get("Name [ref]")))
            imo = be.cell(row, hi.get("IMO number"))
            where = f"{rid}|{FIELD}"
            kept = gate.passing(cand, former, where, new, imo)
            if not kept and not is_placeholder(former):
                kept = gate.passing(gate.shipvault_candidates(imo), former, where, new, imo)
            conf = c.get("confidence", "Y") if kept else "Y"
            note = f"former Name {former!r}; the row is renamed {new!r}" + \
                   (f" by {src}" if src else "") + \
                   ("" if kept else " — no ref on hand prints the former name (backend's own "
                                    "published value); held")
            cell = {"field": FIELD, "new_value": SEP.join(split_names(existing) + [former]),
                    "gate_value": former, "append_ref": True, "confidence": conf,
                    "refs": [{"url": u, "soft": False} for u in kept], "note": note}
            proposals.append({**rec, "name_cell": c, "corr": corr, "cell": cell})
    return proposals, skipped


def patch_batch(batch: Path, be, gate: Gate, include=(), dry_run=False):
    path = batch if batch.is_file() else batch / "fix.json"   # a batch dir, or the fix.json itself
    payload = json.loads(path.read_text())
    for corr in payload.get("corrections", []):      # idempotent: drop our earlier cells
        corr["cells"] = [c for c in corr.get("cells", [])
                         if not (c.get("field") == FIELD and c.get("append_ref"))]
    proposals, skipped = build_cells([("", payload)], be, gate, include)
    for p in proposals:
        cells = p["corr"]["cells"]
        cells.insert(cells.index(p["name_cell"]) + 1, p["cell"])
    if not dry_run:
        path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")
    return proposals, skipped


def collect(batch_dirs: list[Path], be, gate: Gate, include=()):
    payloads = [(d.name, json.loads((d / "fix.json").read_text()))
                for d in batch_dirs if (d / "fix.json").exists()]
    proposals, skipped = build_cells(payloads, be, gate, include)
    # a former name rides with its Name line: held or rejected there -> held here
    for p in proposals:
        dec = {}
        dpath = next((d for d in batch_dirs if d.name == p["source"]), None)
        if dpath and (dpath / "decisions.csv").exists():
            with open(dpath / "decisions.csv", newline="", encoding="utf-8") as f:
                dec = {r["id"]: r["decision"] for r in csv.DictReader(f)}
        p["name_decision"] = dec.get(f"{p['row_id']}|Name", "")
    fix = {
        "batch_label": "Former names -> Other names (RF §4.16)",
        "reason": "Every Name change proposed by " + ", ".join(d.name for d in batch_dirs) +
                  " moves the row's former Name into Other names (appended; existing entries "
                  "and refs kept). Apply each line together with its Name line.",
        "corrections": [{"row_id": p["row_id"], "cells": [p["cell"]]} for p in proposals],
    }
    return fix, proposals, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--batch", help="fix batch dir (or a fix.json path): patch the fix.json in place")
    ap.add_argument("--collect", nargs="+", help="built fix batch dirs -> standalone fix.json")
    ap.add_argument("--out", help="with --collect: output fix.json path")
    ap.add_argument("--include", nargs="*", default=[], metavar="ROW_ID",
                    help="row_ids to propose even though classified as a spelling fix etc.")
    ap.add_argument("--no-gate", action="store_true", help="offline: propose with no refs")
    ap.add_argument("--ask-vesselfinder", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if bool(args.batch) == bool(args.collect) or (args.collect and not args.out):
        ap.error("give --batch <dir>, or --collect <dirs> --out <fix.json>")

    be = load_backend()
    gate = Gate(enabled=not args.no_gate, ask_vesselfinder=args.ask_vesselfinder)
    if args.batch:
        proposals, skipped = patch_batch(Path(args.batch), be, gate, args.include, args.dry_run)
        b = Path(args.batch)
        log_path = b.with_name(b.stem + "_other_names.json") if b.is_file() else b / "other_names.json"
    else:
        fix, proposals, skipped = collect([Path(d) for d in args.collect], be, gate, args.include)
        out = Path(args.out)
        if not args.dry_run:
            out.write_text(json.dumps(fix, indent=1, ensure_ascii=False) + "\n")
        log_path = out.with_name(out.stem + "_log.json")
    report = {"proposed": [{k: v for k, v in p.items() if k not in ("name_cell", "corr")}
                           for p in proposals],
              "skipped": skipped, "gate": gate.log}
    if not args.dry_run:
        log_path.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")

    with_ref = sum(1 for p in proposals if p["cell"]["refs"])
    print(f"other_names: {len(proposals)} former name(s) proposed "
          f"({with_ref} with a passing ref, {len(proposals) - with_ref} held without), "
          f"{len(skipped)} Name change(s) skipped", file=sys.stderr)
    for s in skipped:
        print(f"  skipped live row {s['live_row']}: {s['former']!r} -> {s['new']!r} — {s['reason']}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
