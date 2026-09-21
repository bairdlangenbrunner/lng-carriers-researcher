"""Second ref for the rolled-forward Delivery years (Baird, 2026-09-21).

A proposed delivery delay wants at least one source besides shipvault. For every Y
`Delivery year` roll-forward in fix.json, look the IMO up in the IGU World LNG Report 2026
extraction (work/igu_fleet_2026.json): where IGU prints the same year, the report PDF goes in
as a second ref and the cell moves Y -> G; where IGU prints another year the note says so and
the cell stays Y. Idempotent. Run from the repo root, before build_workbook.py.
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
IGU_PDF = "https://www.datocms-assets.com/146580/1783403747-igu-world-lng-report-2026.pdf"

fix = json.loads((HERE / "fix.json").read_text())
igu = json.loads((ROOT / "work" / "igu_fleet_2026.json").read_text())
by_imo = {}
for table in ("fleet", "orderbook"):
    for x in igu[table]:
        if x.get("imo"):
            by_imo.setdefault(x["imo"], []).append(x)

cm = json.loads((ROOT / "work" / "backend.colmap.json").read_text())
rows = list(csv.reader(open(ROOT / "work" / "backend.csv")))
imo_of = {r[cm["row_id"]]: r[cm["imo"]] for r in rows[cm["_data_starts_at"]:]}

agree, differ, absent = [], [], []
for corr in fix["corrections"]:
    for c in corr["cells"]:
        if c["field"] != "Delivery year" or "not delivered as of" not in c.get("note", ""):
            continue
        if "IGU 2026" in c["note"]:                       # already done
            continue
        hits = by_imo.get(imo_of[corr["row_id"]], [])
        if len(hits) != 1:
            absent.append(corr["_live_row"])
            continue
        g = hits[0]
        src = f"IGU 2026 Appendix 4 orderbook, PDF p.{g['pdf_page']}, IMO {g['imo']}"
        if str(g["delivery_year"]) == c["new_value"]:
            c["refs"].append({"url": IGU_PDF, "soft": False})
            c["confidence"] = "G"
            c["note"] += f"; second source: {src} prints {g['delivery_year']}"
            agree.append(corr["_live_row"])
        else:
            c["note"] += f"; {src} prints {g['delivery_year']} — no second source for {c['new_value']} yet"
            differ.append(corr["_live_row"])

(HERE / "fix.json").write_text(json.dumps(fix, indent=1, ensure_ascii=False) + "\n")
print(f"IGU agrees (Y -> G, PDF added): {len(agree)} {agree}")
print(f"IGU prints another year (stays Y): {len(differ)} {differ}")
print(f"not in IGU / ambiguous: {len(absent)} {absent}")
