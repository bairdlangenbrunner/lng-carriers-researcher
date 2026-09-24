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

    @staticmethod
    def _igu_edition(url: str) -> str:
        m = re.search(r"igu-world-lng-report-(\d{4})", url.lower())
        return m.group(1) if m else ""

    def _names(self) -> dict:
        if self._igu is None:
            self._igu = load_igu_names()
        return self._igu

    def _igu_prints(self, url: str, imo: str, former: str) -> bool:
        """The IGU report's name cell for this IMO carries the former name (`(ex-…)`)."""
        ed = self._igu_edition(url)
        if not ed or not imo:
            return False
        return igu_prints_name(self._names().get(ed, {}).get(str(imo).strip(), ""), former)

    def igu_candidates(self, imo: str, former: str) -> list[str]:
        """The report PDF of every edition whose extraction prints the former name for this
        IMO. The backend was seeded from IGU 2025, so a bulk-loaded row's `Name [ref]` is the
        landing page — ungateable, but the same edition's PDF is the ref (IG §5.4)."""
        return [IGU_PDF[ed] for ed, names in sorted(self._names().items()) if ed in IGU_PDF
                and igu_prints_name(names.get(str(imo).strip(), ""), former)]

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
            return "landing page, no per-vessel value (no report PDF known for this edition)"
        if host.endswith("vesselfinder.com") and not self.ask_vf:
            return "vesselfinder not asked (IP ban)"
        if is_placeholder(former) and any(host.endswith(t) for t in TRACKER_HOSTS):
            return "tracker pages do not print yard numbers"
        return None

    def passing(self, urls: list[str], former: str, where: str, new: str = "", imo: str = "") -> list[str]:
        from url_verifier import corroborates, url_ban_reason
        kept = []
        for url in citable_forms(urls):       # an IGU landing page -> its edition's PDF
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
            ed = self._igu_edition(url)
            if ok and ed and imo and ed in self._names():
                # a 1,000-vessel table prints someone's 'Hull 3387' on any page: the IGU PDF
                # passes only on what it prints for THIS IMO (coordinate extraction)
                ok = self._igu_prints(url, imo, former)
                reason = (f"OK (IGU {ed} name cell for IMO {imo}, coordinate extraction)" if ok
                          else f"IGU {ed} does not print this name for IMO {imo}")
            elif ok and "all tokens present" in reason:
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


def igu_prints_name(printed: str, former: str) -> bool:
    """IGU's name cell carries the former name — as the phrase, or, for a hull placeholder,
    as the same hull number (IGU prints `Hull 3387`, the backend `Hull 3387 (HDHHI)`)."""
    if not printed or not former:
        return False
    if f" {fold(former)} " in f" {fold(printed)} ":
        return True
    h = hull_only(former)
    if not h:
        return False
    paren = _PAREN_HULL_RE.search(printed.split(" (ex-")[0])
    if same_hull(h, hull_only(printed)) or (paren and same_hull(h, hull_only(paren.group(1)))):
        return True
    # 'Hlaitan (ex-H1792A)', '… (ex-Victor Hugo (8107))': the hull sits in the ex-name chain
    return any(same_hull(h, hull_only(x)) for pair in igu_ex_names(printed) for x in pair if x)


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


_EX_RE = re.compile(r"\(ex-(.*)\)\s*$", re.I)
_PAREN_HULL_RE = re.compile(r"\s*\(([^()]*\d[^()]*)\)\s*$")   # 'Victor Hugo (8107)'
_YARD_WORDS = {"hull", "no", "hudong", "zhonghua", "hyundai", "ulsan", "samho", "samsung",
               "heavy", "industries", "shi", "hshi", "hdhhi", "hanwha", "jiangnan", "zvezda"}
_DUMMY_NAMES = {"abcde"}                          # IGU's own filler: 'ex-ABCDE (2537)'
# the citable report PDF per edition (IG §5.4; the landing page cannot pass §3.8c)
from url_verifier import IGU_PDF, citable_forms  # noqa: E402


def igu_ex_names(printed: str) -> list[tuple[str, str]]:
    """IGU `Name (ex-A / ex-B (8107))` -> [(ex name, hull number IGU adds in parentheses)]."""
    m = _EX_RE.search(printed or "")
    if not m:
        return []
    out = []
    for part in re.split(r"\s*/\s*ex-", m.group(1)):
        hull, pm = "", _PAREN_HULL_RE.search(part)
        if pm:
            hull, part = pm.group(1).strip(), part[:pm.start()]
        part = part.strip()
        if fold(part) in _DUMMY_NAMES:
            part, hull = hull, ""
        if part:
            out.append((part, hull))
    return out


def hull_only(name: str) -> str:
    """The hull number when a name is nothing but one ('3341', 'Hudong-Zhonghua H1881A',
    'Hull 2563 (Hanwha)'); '' for a real name."""
    toks = [t for t in fold(name).split() if t not in _YARD_WORDS]
    return toks[0].upper() if len(toks) == 1 and re.search(r"\d", toks[0]) else ""


def same_hull(a: str, b: str) -> bool:
    """Hull numbers equal up to the yard's optional `H` prefix (Hudong `H1881A` = `1881A`)."""
    strip = lambda s: re.sub(r"^H(?=\d)", "", s.upper())
    return bool(a and b) and strip(a) == strip(b)


# Yards whose hull placeholders carry no tag in the backend yet (Baird 2026-09-18: a hull
# number always says whose hull it is). yard_tags() wins where the backend has a tag.
FALLBACK_YARD_TAGS = {"Hudong-Zhonghua Shipbuilding": "Hudong", "Jiangnan Shipyard": "Jiangnan",
                      "Hanwha Philly SY": "Hanwha Philly"}


def yard_tags(be) -> dict:
    """Shipbuilder -> the yard tag its `Hull NNNN (Tag)` placeholders use (QC §2)."""
    from collections import Counter
    hi, counts = be.header_index, {}
    for row in be.row_by_id().values():
        for n in [be.cell(row, hi.get("Name"))] + split_names(be.cell(row, hi.get(FIELD))):
            m = re.match(r"Hull\s+\S+\s+\(([^()]+)\)$", n.strip())
            if m:
                counts.setdefault(be.cell(row, hi.get("Shipbuilder")), Counter())[m.group(1)] += 1
    return {b: c.most_common(1)[0][0] for b, c in counts.items()}


def igu_ex_cells(be, gate: Gate, edition: str, proposals: list) -> tuple[list, list]:
    """RF §4.17: every `(ex-…)` name the IGU report prints for a row's IMO joins the row's
    `Other names` — whether or not any batch renames the row. Rows that already carry a
    §4.16 proposal get the ex-names appended to that cell (it stays coupled to its Name
    line); every other row gets a cell of its own. A bare hull number is written as the
    row's QC §2 placeholder (`Hull 3341 (HDHHI)`). -> (new proposals, skipped)."""
    from paths import work_dir
    ext = json.loads((work_dir() / f"igu_fleet_{edition}.json").read_text())
    pdf = IGU_PDF[edition]
    rows, live, hi = be.row_by_id(), be.sheet_row_map(), be.header_index
    by_imo = {}
    for rid, row in rows.items():
        imo = be.cell(row, hi.get("IMO number")).strip()
        if imo:
            by_imo.setdefault(imo, []).append(rid)
    tags, pending = yard_tags(be), {be.canonical_key(p["row_id"]): p for p in proposals}
    new, skipped, added = [], [], {}
    for rec in ext.get("fleet", []) + ext.get("orderbook", []):
        exes = igu_ex_names(rec.get("name", ""))
        imo = str(rec.get("imo") or "").strip()
        if not exes:
            continue
        if imo not in by_imo:
            skipped.append({"row_id": None, "live_row": None, "igu_name": rec["name"], "imo": imo,
                            "former": "; ".join(e for e, _ in exes),
                            "new": f"(IGU {edition} ex-name)", "reason": "IMO not in the backend (a discovery lead, not an Other name)"})
            continue
        for rid in by_imo[imo]:
            row, p = rows[rid], pending.get(rid)
            name = be.cell(row, hi.get("Name"))
            known = [name] + split_names(be.cell(row, hi.get(FIELD))) + \
                    ([p["former"]] if p else []) + added.get(rid, [])
            hull_cell = be.cell(row, hi.get("Hull number")).strip()
            hull_col = hull_only(hull_cell)
            for ex, paren in exes:
                h = hull_only(ex)
                builder = be.cell(row, hi.get("Shipbuilder"))
                tag = tags.get(builder) or FALLBACK_YARD_TAGS.get(builder) or builder
                if h and same_hull(h, hull_col) and re.search(r"\([^()]+\)\s*$", hull_cell):
                    value = hull_cell                # the row's own styled hull: 'Hull 3299 (HSHI)'
                elif h:                              # always name the yard (Baird 2026-09-18)
                    num = hull_col if same_hull(h, hull_col) else h
                    value = f"Hull {num} ({tag})"
                else:
                    value = ex
                known_f = {fold(k) for k in known}
                known_h = {hull_only(k) for k in known} - {""}
                row_h = known_h | ({hull_col} - {""})
                base = {"row_id": rid, "live_row": live.get(rid), "igu_name": rec["name"],
                        "imo": imo, "former": ex, "new": f"(IGU {edition} ex-name)"}
                why = None
                if fold(ex) == fold(name):
                    why = "is the row's current Name" + ("" if p else
                          f" — no batch renames it to IGU's {rec['name'].split(' (ex-')[0]!r}; check")
                elif fold(ex) in known_f or fold(value) in known_f:
                    why = "already on the row (Other names, or a pending former-Name line)"
                elif h and any(same_hull(h, k) for k in known_h):
                    why = f"same hull as a name already on the row ({h})"
                elif h and row_h and not any(same_hull(h, k) for k in row_h):
                    why = (f"IGU hull {h} differs from the row's hull "
                           f"({', '.join(sorted(row_h))}) — check")
                if why:
                    skipped.append({**base, "reason": why})
                    continue
                known.append(value)
                added.setdefault(rid, []).append(value)
                kept = gate.passing([pdf], ex, f"{rid}|{FIELD}", "", imo)
                refs = [{"url": u, "soft": False, "gate_value": ex} for u in kept]
                note = (f"IGU {edition} prints {rec['name']!r}" +
                        (f" — hull-number former name written as the QC §2 placeholder {value!r}"
                         if h else "") +
                        (f"; IGU's hull tag ({paren}) not checked against the row" if paren else ""))
                if p:                                  # ride on the §4.16 cell for this row
                    c = p["cell"]
                    for r in c["refs"]:
                        r.setdefault("gate_value", c["gate_value"])
                    c["new_value"] += SEP + value
                    c["refs"] += refs
                    c["note"] += "; plus " + note
                    p.setdefault("igu_ex", []).append(value)
                    continue
                q = next((x for x in new if be.canonical_key(x["row_id"]) == rid), None)
                if q:
                    q["cell"]["new_value"] += SEP + value
                    q["cell"]["refs"] += refs
                    q["cell"]["note"] += "; " + value
                    if not kept:
                        q["cell"]["confidence"] = "Y"
                    continue
                existing = be.cell(row, hi.get(FIELD))
                new.append({"row_id": rid, "live_row": live.get(rid), "source": f"IGU {edition} (ex-…)",
                            "former": ex, "new": name, "name_cell": None, "corr": None,
                            "cell": {"field": FIELD, "new_value": SEP.join(split_names(existing) + [value]),
                                     "gate_value": ex, "append_ref": True,
                                     "confidence": "G" if kept else "Y", "refs": refs,
                                     "note": note + ("" if kept else " — the PDF did not pass the gate; held")}})
    return new, skipped


def name_cells(payload: dict):
    for corr in payload.get("corrections", []):
        for c in corr.get("cells", []):
            if c.get("field") == "Name":
                yield corr, c


def build_cells(payloads: list[tuple[str, dict]], be, gate: Gate, include=()) -> tuple[list, list]:
    """-> (proposals, skipped). A proposal = {row_id, source, name_cell, cell}."""
    rows, live = be.row_by_id(), be.sheet_row_map()
    hi = be.header_index
    include = {be.canonical_key(x) for x in include}
    # who is being given which name, to catch a name that was parked on the wrong row
    claimed = {}
    for _src, payload in payloads:
        for corr, c in name_cells(payload):
            claimed.setdefault(fold(c.get("new_value", "")), be.canonical_key(corr["row_id"]))

    proposals, skipped, done, tags = [], [], set(), yard_tags(be)
    for src, payload in payloads:
        for corr, c in name_cells(payload):
            rid, new = be.canonical_key(corr["row_id"]), str(c.get("new_value", "")).strip()
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
            cand += gate.igu_candidates(imo, former)
            where = f"{rid}|{FIELD}"
            kept = gate.passing(cand, former, where, new, imo)
            if not kept and not is_placeholder(former):
                kept = gate.passing(gate.shipvault_candidates(imo), former, where, new, imo)
            conf = c.get("confidence", "Y") if kept else "Y"
            note = f"former Name {former!r}; the row is renamed {new!r}" + \
                   (f" by {src}" if src else "") + \
                   ("" if kept else " — no ref on hand prints the former name (backend's own "
                                    "published value); held")
            value = former                  # a bare hull placeholder gains its yard tag
            if hull_only(former) and not re.search(r"\([^()]+\)\s*$", former):
                b = be.cell(row, hi.get("Shipbuilder"))
                value = f"{former} ({tags.get(b) or FALLBACK_YARD_TAGS.get(b) or b})"
            cell = {"field": FIELD, "new_value": SEP.join(split_names(existing) + [value]),
                    "gate_value": former, "append_ref": True, "confidence": conf,
                    "refs": [{"url": u, "soft": False} for u in kept], "note": note}
            proposals.append({**rec, "name_cell": c, "corr": corr, "cell": cell})
    return proposals, skipped


def patch_batch(batch: Path, be, gate: Gate, include=(), dry_run=False, igu_ex=None):
    path = batch if batch.is_file() else batch / "fix.json"   # a batch dir, or the fix.json itself
    payload = json.loads(path.read_text())
    for corr in payload.get("corrections", []):      # idempotent: drop our earlier cells
        corr["cells"] = [c for c in corr.get("cells", [])
                         if not (c.get("field") == FIELD and c.get("append_ref"))]
    payload["corrections"] = [c for c in payload.get("corrections", []) if c["cells"]]
    proposals, skipped = build_cells([("", payload)], be, gate, include)
    if igu_ex:
        extra, skipped_ex = igu_ex_cells(be, gate, igu_ex, proposals)
        proposals, skipped = proposals + extra, skipped + skipped_ex
    for p in proposals:
        if p["corr"] is None:                        # an ex-name row the batch does not touch
            corr = next((c for c in payload["corrections"]
                         if be.canonical_key(c["row_id"]) == be.canonical_key(p["row_id"])), None)
            if corr is None:
                payload["corrections"].append({"row_id": p["row_id"], "cells": [p["cell"]]})
            else:
                corr["cells"].append(p["cell"])
            continue
        cells = p["corr"]["cells"]
        cells.insert(cells.index(p["name_cell"]) + 1, p["cell"])
    if not dry_run:
        path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")
    return proposals, skipped


def collect(batch_dirs: list[Path], be, gate: Gate, include=(), igu_ex=None):
    payloads = [(d.name, json.loads((d / "fix.json").read_text()))
                for d in batch_dirs if (d / "fix.json").exists()]
    proposals, skipped = build_cells(payloads, be, gate, include)
    if igu_ex:
        extra, skipped_ex = igu_ex_cells(be, gate, igu_ex, proposals)
        proposals, skipped = proposals + extra, skipped + skipped_ex
    # a former name rides with its Name line: held or rejected there -> held here
    for p in proposals:
        if p["name_cell"] is None:
            continue
        dec = {}
        dpath = next((d for d in batch_dirs if d.name == p["source"]), None)
        if dpath and (dpath / "decisions.csv").exists():
            with open(dpath / "decisions.csv", newline="", encoding="utf-8") as f:
                dec = {be.canonical_item_id(r["id"]): r["decision"] for r in csv.DictReader(f)}
        p["name_decision"] = dec.get(be.canonical_item_id(f"{p['row_id']}|Name"), "")
    fix = {
        "batch_label": "Former names -> Other names (RF §4.16" + (", §4.17" if igu_ex else "") + ")",
        "reason": "Every Name change proposed by " + ", ".join(d.name for d in batch_dirs) +
                  " moves the row's former Name into Other names (appended; existing entries "
                  "and refs kept). Apply each line together with its Name line." +
                  (f" Every (ex-…) name the IGU {igu_ex} report prints for a row's IMO is "
                   "added too (on its own where no batch renames the row)." if igu_ex else ""),
        "corrections": [{"row_id": p["row_id"], "cells": [p["cell"]]} for p in proposals],
    }
    return fix, proposals, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--batch", help="fix batch dir (or a fix.json path): patch the fix.json in place")
    ap.add_argument("--collect", nargs="+", help="built fix batch dirs -> standalone fix.json")
    ap.add_argument("--out", help="with --collect: output fix.json path")
    ap.add_argument("--include", nargs="*", default=[], metavar="ROW_KEY",
                    help="row keys (UUID or legacy id) to propose even though classified as a spelling fix etc.")
    ap.add_argument("--no-gate", action="store_true", help="offline: propose with no refs")
    ap.add_argument("--ask-vesselfinder", action="store_true")
    ap.add_argument("--igu-ex", metavar="EDITION",
                    help="also add every (ex-…) name the IGU report of this edition prints "
                         "for a row's IMO (RF §4.17; needs work/igu_fleet_<EDITION>.json)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if bool(args.batch) == bool(args.collect) or (args.collect and not args.out):
        ap.error("give --batch <dir>, or --collect <dirs> --out <fix.json>")

    be = load_backend()
    gate = Gate(enabled=not args.no_gate, ask_vesselfinder=args.ask_vesselfinder)
    if args.batch:
        proposals, skipped = patch_batch(Path(args.batch), be, gate, args.include, args.dry_run,
                                         args.igu_ex)
        b = Path(args.batch)
        log_path = b.with_name(b.stem + "_other_names.json") if b.is_file() else b / "other_names.json"
    else:
        fix, proposals, skipped = collect([Path(d) for d in args.collect], be, gate, args.include,
                                          args.igu_ex)
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
