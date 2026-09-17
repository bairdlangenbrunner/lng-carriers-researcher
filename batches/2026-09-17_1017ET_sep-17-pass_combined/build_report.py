"""Render the shareable report page for the sep-17-pass (2026-09-17).

Reads report_data.json + the combined workbook (both written by build_combined.py) and
writes one self-contained HTML file (the workbook rides along base64-encoded so the page
can offer it as a download).
Usage: python batches/2026-09-17_1017ET_sep-17-pass_combined/build_report.py <out.html>
"""
import base64
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
data = json.loads((HERE / "report_data.json").read_text(encoding="utf-8"))
P = data["proposals"]

rows = [[p["apply order"], p["live sheet row"], p["vessel name (backend)"], p["shipbuilder"], p["shipowner"],
         p["column"], p["current backend value"], p["proposed value"],
         (p["source URL(s)"] or "").replace(", ", "\n").split("\n")[0], p["confidence"], p["decision"],
         (p["note"] or "")[:320]] for p in P]

b4 = Counter((p["column"], p["decision"]) for p in P if p["apply order"] == 4)
cols = sorted({c for c, _ in b4}, key=lambda c: -(b4[(c, "accept")] + b4[(c, "hold")]))
main = [c for c in cols if not c.startswith("Yard location") and c != "Shipowner"]
chart = [[c, b4[(c, "accept")], b4[(c, "hold")]] for c in main]
rest = [c for c in cols if c not in main]
chart.append(["Yard location, other", sum(b4[(c, "accept")] for c in rest), sum(b4[(c, "hold")] for c in rest)])


def js(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


html = (HERE / "report_template.html").read_text(encoding="utf-8")
html = (html.replace("/*ROWS*/[]", js(rows)).replace("/*CHART*/[]", js(chart))
        .replace("/*XLSX*/", base64.b64encode((HERE / "lng_carrier_sep-17-pass_results.xlsx").read_bytes()).decode()))
out = Path(sys.argv[1])
out.write_text(html, encoding="utf-8")
print("wrote", out, f"{out.stat().st_size / 1e6:.2f} MB", "| rows:", len(rows), "| chart:", chart)
