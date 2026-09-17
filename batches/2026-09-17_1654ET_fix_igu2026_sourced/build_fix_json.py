"""Build fix.json for the IGU-2026-sourced fix batch.

Input : ../2026-09-17_1458ET_igu_reconciliation_igu2026/igu_reconcile.json (batch 7),
        work/backend.csv + colmap (same pull as batch 7), batch 4 data_fill.json (overlap check).
Output: fix.json + manual_review.json beside this file.

Rule (Baird, 2026-09-17): what the IGU World LNG Report 2026 prints is a sufficient sole
source for now — cite the report PDF alone. G = IGU prints the value for the named vessel and
there is no judgment call; Y (hold) = IGU prints it but a scope / vocabulary / cascade question
rides on it. Nothing is proposed from IGU's *silence* (dropped rows) or from `backend_differs`
fields where the backend was edited after the load, except the named load-corruption /
truncated-name rows.
"""
import csv, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
IGU_PDF = "https://www.datocms-assets.com/146580/1783403747-igu-world-lng-report-2026.pdf"
REC = json.loads((HERE.parent / "2026-09-17_1458ET_igu_reconciliation_igu2026" / "igu_reconcile.json").read_text())
B4 = json.loads((HERE.parent / "2026-09-17_0511ET_data_fill_on_order" / "data_fill.json").read_text())

rows = list(csv.reader(open(ROOT / "work" / "backend.csv", encoding="utf-8")))
colmap = json.loads((ROOT / "work" / "backend.colmap.json").read_text())
hdr = rows[colmap["_header_row_idx"]]
H = {h: i for i, h in enumerate(hdr)}
by_id = {r[colmap["row_id"]].strip(): r for r in rows[colmap["_header_row_idx"] + 1:] if r and r[colmap["row_id"]].strip()}

FIELD = {"vessel_type": "Vessel type", "cargo_type": "Cargo type", "propulsion": "Propulsion type",
         "capacity": "Capacity", "delivery_year": "Delivery year", "name": "Name",
         "status": "Status", "shipowner": "Shipowner", "shipbuilder": "Shipbuilder"}
for f in FIELD.values():
    assert f in H and f + " [ref]" in H, f

VT = {"conventional": "conventional", "fsru": "FSRU", "fsu": "FSU", "icebreaker": "icebreaker",
      "q-flex": "q-flex", "q-max": "q-max", "small-scale": "small-scale", "mid-scale": "mid-scale"}
CT = {"membrane": "membrane", "spherical": "spherical",
      "self-supporting prismatic": "self-supporting prismatic", "type c": "type C"}
PR = {"steam": "steam", "steam reheat": "steam reheat"}
OUT_OF_SCOPE_VT = {"FSU", "small-scale", "mid-scale"}


def norm(field, v):
    v = str(v).strip()
    if field == "vessel_type":
        return VT.get(v.lower())
    if field == "cargo_type":
        return CT.get(v.lower())
    if field == "propulsion":
        return PR.get(v.lower(), v)
    if field in ("capacity", "delivery_year"):
        return str(int(v))
    return v


def clean_name(n):
    n = re.sub(r"\s*\(ex-.*$", "", n).strip()
    n = re.sub(r"\s*\(\d+A?\)\s*$", "", n).strip()          # "Fath Al Khair (1799A)"
    if n.isupper():
        n = " ".join(w if w in ("SC", "LNG", "BW", "LNGT") else w.capitalize() for w in n.split())
    return n


b4 = {(f["row_id"], f["field"]): f for f in B4["fills"] if f.get("prev_state") != "corroborate"}
cells = {}       # row_id -> list of cells
manual = []
src = lambda x: f"IGU 2026 {'Appendix 3 fleet' if x['igu']['table']=='fleet' else 'Appendix 4 orderbook'} table, PDF p.{x['igu']['pdf_page']}"


def add(x, field, value, conf, note):
    b = x["backend"]
    cells.setdefault(b["row_id"], {"_live_row": b["sheet_row"], "_name": b["name"], "cells": []})
    cells[b["row_id"]]["cells"].append({
        "field": FIELD[field], "new_value": value, "confidence": conf,
        "refs": [{"url": IGU_PDF, "soft": False}],
        "note": f"{note} [{src(x)}; IMO {x['igu']['imo']}; sole source per Baird ruling 2026-09-17]"})


matched = sorted(REC["matched"], key=lambda x: x["backend"]["sheet_row"])

# ---- A. blanks IGU can fill, C. filled values IGU agrees with whose [ref] is blank
for x in matched:
    b, g = x["backend"], x["igu"]
    raw = by_id[b["row_id"]]
    for f in ("vessel_type", "cargo_type", "propulsion", "capacity"):
        iv = g.get(f)
        if iv in (None, ""):
            continue
        bv = raw[H[FIELD[f]]].strip()
        ref = raw[H[FIELD[f] + " [ref]"]].strip()
        v = norm(f, iv)
        if v is None:                                   # IGU value outside the vocabulary (QC-max)
            if not bv or bv.lower() == "unknown":
                manual.append({"live_row": b["sheet_row"], "row_id": b["row_id"], "name": b["name"], "field": FIELD[f],
                               "igu": iv, "why": "IGU value is not in the controlled vocabulary — vocabulary decision"})
            continue
        if not bv or bv.lower() == "unknown":
            conf, note = "G", f"blank in backend; IGU prints {iv!r}"
            if f == "vessel_type" and v in OUT_OF_SCOPE_VT:
                conf, note = "Y", note + f" — {v} is out of scope for additions (inclusion criteria); row stays, type is a scope flag"
            p = b4.get((b["row_id"], FIELD[f]))
            if p:
                if str(p["proposed_value"]).strip().lower() == v.lower():
                    note += "; batch 4 (data-fill) proposes the same value — this adds the ref"
                else:
                    conf = "Y"
                    note += f"; CONFLICT with batch 4 (data-fill), which proposes {p['proposed_value']!r}"
            add(x, f, v, conf, note)
            if f == "capacity" and not raw[H["Capacity units"]].strip():
                cells[b["row_id"]]["cells"].append({"field": "Capacity units", "new_value": "cbm", "confidence": conf,
                                                    "preserve_ref": True, "note": "derivable companion of the Capacity fill (no [ref] column)"})
        elif f != "capacity" and bv.lower() == v.lower() and not ref:
            add(x, f, bv, "G", "value unchanged — Rule F ref-fill: backend value had no [ref]; IGU prints the same value")

# ---- B. corrections
SKIP_NAME_ROWS = {531, 347, 565, 813, 814, 815, 826, 938, 939, 1015, 1016, 1067, 1068, 1069, 873, 910}
HOLD_NAME_ROWS = {11: "IGU restyles the Karadeniz / Karmol powership names — a label choice, not a rename",
                  20: "IGU restyling of a Karadeniz name — label choice", 29: "IGU restyling of a Karadeniz name — label choice",
                  39: "IGU restyling of a Karadeniz name — label choice",
                  785: "spelling only (`Al-Kheesha` vs IGU `Al Kheesah`) — sources differ on the transliteration"}
DEFECT_NAME_ROWS = {88, 294, 446, 461, 584}                # backend truncated / mis-spelt, IGU unchanged
ARCTIC = {797, 799, 805, 812, 823, 806}
for x in matched:
    b, g = x["backend"], x["igu"]
    sr = b["sheet_row"]
    for d in x["diffs"]:
        f, kind = d["field"], d["kind"]
        if d.get("pending_agrees"):
            continue
        if f == "name":
            if sr in SKIP_NAME_ROWS:
                continue
            if kind == "backend_differs" and sr not in DEFECT_NAME_ROWS:
                continue
            v = clean_name(d["igu"])
            if sr in HOLD_NAME_ROWS:
                add(x, f, v, "Y", f"{d['backend']!r} -> {v!r}: {HOLD_NAME_ROWS[sr]}")
            elif sr in DEFECT_NAME_ROWS:
                add(x, f, v, "G", f"backend name defect {d['backend']!r}; IGU prints {d['igu']!r} in both editions")
            else:
                add(x, f, v, "G", f"renamed / restyled since the load: {d['backend']!r} -> IGU 2026 {d['igu']!r} (IGU 2025: {d['igu_prev']!r})")
        elif f == "delivery_year":
            if b["status"] != "active":
                continue                                  # on-order schedule diffs: reading list (IGU schedule is 9 months old)
            v = norm(f, d["igu"])
            if sr in ARCTIC or sr == 814:
                add(x, "status", "on order", "Y", "backend `active`, IGU 2026 still lists the vessel in the orderbook (shipvault lead agrees: not delivered)"
                    + (" — sanctioned Arctic LNG 2 hull, Status left untouched in batch 1" if sr in ARCTIC else ""))
                add(x, f, v, "Y", f"rides with the Status change: IGU orderbook delivery year {v} (backend {d['backend']})")
            else:
                add(x, f, v, "G", f"backend {d['backend']} cannot be right — IGU 2026 (fleet at end-2025) still had the vessel on order, delivery {v}"
                    + ("; Status `active` is a separate stream 0 item for this row" if sr == 800 else ""))
        elif f == "vessel_type":
            v = norm(f, d["igu"])
            if b["vessel_type"] == "Supporting":
                add(x, f, v, "G", "load corruption (`Supporting` bled from the wrapped 'Self-Supporting Prismatic' cargo cell); IGU prints "
                    + repr(d["igu"]) + (" — small-scale is out of scope for additions; row stays" if v == "small-scale" else ""))
            else:
                add(x, f, v, "Y", f"{d['backend']!r} -> {v!r} per IGU 2026 ({kind}; IGU 2025: {d['igu_prev']!r})"
                    + (" — FSU is out of scope for additions; row stays, scope flag" if v == "FSU" else ""))
        elif f == "propulsion":
            v = norm(f, d["igu"])
            if b["propulsion"].startswith("prismatic"):
                add(x, f, v, "G", f"load corruption ({d['backend']!r}); IGU prints {d['igu']!r} in both editions")
            elif kind == "backend_differs":
                continue
            elif v == "TFDE":
                add(x, f, v, "Y", f"{d['backend']!r} -> 'TFDE' per IGU 2026 — TFDE is not a value the backend uses today (DFDE covers it?)")
            else:
                add(x, f, v, "G", f"{d['backend']!r} -> {v!r}: IGU changed its own value this edition (IGU 2025: {d['igu_prev']!r})")
        elif f == "capacity" and kind == "igu_changed":
            add(x, f, norm(f, d["igu"]), "G", f"{d['backend']} -> {d['igu']}: IGU changed its own value this edition")
        elif f == "cargo_type" and kind == "igu_changed":
            add(x, f, norm(f, d["igu"]), "G", f"{d['backend']!r} -> {d['igu']!r}: IGU changed its own value this edition")
        elif f in ("shipowner", "shipbuilder") and kind != "backend_differs":
            manual.append({"live_row": sr, "row_id": b["row_id"], "name": b["name"], "field": FIELD[f],
                           "backend": d["backend"], "igu": d["igu"], "igu_prev": d["igu_prev"],
                           "why": ("IGU prints a short / group label — the canonical backend stylization and, for a builder, "
                                   "the yard-location columns that cascade from it need a human pick")})
    sf = x.get("status_finding")
    if sf and sf["finding"] == "delivered_per_igu" and not sf["pending_agrees"]:
        add(x, "status", "active", "G", f"backend `{b['status']}`; IGU 2026 lists the vessel in the active fleet table (delivered {g.get('delivery_year')})")
        if str(g.get("delivery_year")) != b["delivery_year"].strip():
            add(x, "delivery_year", norm("delivery_year", g["delivery_year"]), "G",
                f"backend {b['delivery_year'] or 'blank'} -> {g['delivery_year']} (IGU fleet table delivery year)")

# `Greenenergy` -> `Greenergy` on rows IGU prints under that name but the join did not diff
for x in matched:
    b = x["backend"]
    if "greenenergy" in b["name"].lower() and "greenergy" in x["igu"]["name"].lower() \
            and not any(c["field"] == "Name" for c in cells.get(b["row_id"], {}).get("cells", [])):
        add(x, "name", clean_name(x["igu"]["name"]), "G", f"spelling: {b['name']!r} -> IGU {x['igu']['name']!r}")

# ---- D. Vessel type on rows IGU does not list (orders after the end-2025 cut-off, Clarkson-sourced
# ships). Baird 2026-09-17: the IGU report is the citable source for the Vessel type classification
# itself (it defines the size classes: conventional / Q-Flex 210-217k / Q-Max / QC-max 271k), so a
# capacity-derived type cites the report even though the vessel is not in its tables.
sheet_row = {r[colmap["row_id"]].strip(): i + 1 for i, r in enumerate(rows) if i > colmap["_header_row_idx"] and r and r[colmap["row_id"]].strip()}
assert all(sheet_row[x["backend"]["row_id"]] == x["backend"]["sheet_row"] for x in matched)
matched_ids = {x["backend"]["row_id"] for x in matched}


def add_class(rid, value, conf, note):
    raw = by_id[rid]
    cap = raw[H["Capacity"]].strip() or "blank"
    if cap == "blank" and conf == "G":
        conf, note = "Y", note + " — HOLD: no backend Capacity, so the size class cannot be derived"
    cells.setdefault(rid, {"_live_row": sheet_row[rid], "_name": raw[H["Name"]], "cells": []})
    cells[rid]["cells"].append({
        "field": "Vessel type", "new_value": value, "confidence": conf,
        "refs": [{"url": IGU_PDF, "soft": False}],
        "note": f"{note} [vessel not listed in IGU 2026; the report is cited as the source of the Vessel type "
                f"classification (size classes), capacity {cap} cbm; per Baird ruling 2026-09-17]"})


for rid, raw in by_id.items():
    if rid in matched_ids:
        continue
    bv, ref = raw[H["Vessel type"]].strip(), raw[H["Vessel type [ref]"]].strip()
    p = b4.get((rid, "Vessel type"))
    if bv and bv.lower() != "unknown" and not ref:
        hold = sheet_row[rid] == 61
        add_class(rid, bv, "Y" if hold else "G",
                  "value unchanged — Rule F ref-fill: backend Vessel type had no [ref]"
                  + (" — HOLD: this row's FSU-conversion question (batch 5) is still open" if hold else ""))
    elif (not bv or bv.lower() == "unknown") and p:
        add_class(rid, str(p["proposed_value"]).strip(), "G",
                  f"blank in backend; batch 4 (data-fill) proposes {p['proposed_value']!r} unreffed (was Y for want of a citable ref) — this adds the ref")

corrections = [{"row_id": rid, "_live_row": c["_live_row"], "_name": c["_name"], "cells": c["cells"]}
               for rid, c in sorted(cells.items(), key=lambda kv: kv[1]["_live_row"])]
payload = {
    "batch_label": "Fix — values sourced from the IGU World LNG Report 2026 (2026-09-17, sep-17-pass batch 8)",
    "reason": ("Promotes the batch 7 IGU 2026 intercomparison into proposals. Baird ruling 2026-09-17: what IGU 2026 "
               "prints is a sufficient sole source for now, Vessel type included — every cell cites the report PDF. "
               "OPEN decision: whether these cells get a second ref at the ref-validation step."),
    "igu_ref": IGU_PDF,
    "corrections": corrections,
}
(HERE / "fix.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")
(HERE / "manual_review.json").write_text(json.dumps(manual, indent=1, ensure_ascii=False) + "\n")

from collections import Counter
c = Counter((cell["field"], cell["confidence"], "ref-only" if "value unchanged" in cell["note"] else
             ("blank" if cell["note"].startswith("blank") else "correction")) for r in corrections for cell in r["cells"])
for k, v in sorted(c.items()):
    print(f"{v:>4}  {k}")
print(len(corrections), "rows,", sum(c.values()), "cells;", len(manual), "manual-review items")
