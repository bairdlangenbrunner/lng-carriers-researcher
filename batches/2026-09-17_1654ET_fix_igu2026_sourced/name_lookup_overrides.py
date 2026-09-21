"""IGU-sole-source Name changes checked against other databases by IMO (Baird 2026-09-21, IG §5.4).

Where shipvault / marinetraffic.org / vesseltracker do not explicitly agree with the name IGU 2026
prints, the Name is the databases' name (or the backend's, when they agree with it) and IGU's name
goes to `Other names` (batch 1737ET). Patches both batches' fix.json in place; idempotent.
`build_fix_json.py` would regenerate the IGU values — re-run this after it.

Run from the repo root: python batches/2026-09-17_1654ET_fix_igu2026_sourced/name_lookup_overrides.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
B8 = ROOT / "2026-09-17_1654ET_fix_igu2026_sourced" / "fix.json"
B10 = ROOT / "2026-09-17_1737ET_fix_other_names_former" / "fix.json"
IGU = "https://www.datocms-assets.com/146580/1783403747-igu-world-lng-report-2026.pdf"
VT = "https://www.vesseltracker.com/en/Ships/"
MT = "https://www.marinetraffic.org/ship-owner-manager-ism-data/"
SV = "https://www.shipvault.com/ships/"
SV_API = "https://shipvaultapi-gjb8c.ondigitalocean.app/api/units/"  # companion ref, RF §6a.8
RULE = "IGU 2026 was the sole source; databases checked by IMO (Baird 2026-09-21)"


def ref(url, gate=None):
    r = {"url": url, "soft": False}
    if gate:
        r["gate_value"] = gate
    return r


# row_id -> Name cell (None = drop the IGU Name change, the backend Name stands)
NAMES = {
    "811": ("KLNGTP Americas", "Y", "LNGT Americas", [ref(VT + "Klngtp-Americas-9045132.html")],
            "'LNGT Americas' -> 'KLNGTP Americas': vesseltracker.com (live AIS name, IMO 9045132), matching the "
            "backend's KLNGTP Black Sea / KLNGTP Marmara; shipvault prints 'Karadeniz LNGT P Americas', "
            "marinetraffic.org 'Karadeniz LNGT Powership Americas' — none prints IGU's 'Karadeniz LNGT Americas', "
            "which goes to Other names. No database prints the backend's 'LNGT Americas' — reject to keep it"),
    "726": None, "727": None, "729": None, "1100": None,
    "1004": ("Gas Polaris", "Y", "Seapeak Hispania",
             [ref(VT + "Gas-Polaris-9230048.html"), ref(MT + "GAS-POLARIS/9230048/525121118")],
             "'Seapeak Hispania' -> 'Gas Polaris': marinetraffic.org and vesseltracker.com (IMO 9230048, Indonesian "
             "flag) — renamed again since IGU 2026's 'Seapeak Jupiter', which goes to Other names; shipvault "
             "still prints 'Seapeak Hispania'"),
    "866": ("Arctic Metagaz", "G", "Metagas Everest",
            [ref(VT + "Arctic-Metagaz-9243148.html"), ref(MT + "ARCTIC-METAGAZ/9243148/1"), ref(SV + "115953")],
            "'Metagas Everest' -> 'Arctic Metagaz': shipvault, marinetraffic.org and vesseltracker.com all print "
            "'Arctic Metagaz' for IMO 9243148; IGU 2026's spelling 'Arctic Metagas' goes to Other names"),
    "459": ("LNG Scorpio", "Y", "CCH LNG",
            [ref(VT + "Lng-Scorpio-9307205.html"), ref(MT + "LNG-SCORPIO/9307205/352006648")],
            "'CCH LNG' -> 'LNG Scorpio': marinetraffic.org and vesseltracker.com (IMO 9307205); shipvault prints "
            "'CCH Gas'; IGU 2026's 'LNG Soars' goes to Other names — a sanctioned vessel, renamed often"),
    "263": ("Fat'h Al Khair", "G", "Hull H1799A", [ref(SV + "462938")],
            "'Hull H1799A' -> 'Fat'h Al Khair': shipvault and marinetraffic.org print the apostrophe form for "
            "IMO 9986623; IGU 2026's 'Fath Al Khair (1799A)' goes to Other names"),
}

# row_id -> Other names cell: (new_value, gate_value, confidence, refs, note)
OTHER = {
    "811": ("LNGT Americas; Karadeniz LNGT Americas; Northwest Stormpetrel", "LNGT Americas", "Y",
            [ref(IGU, "Karadeniz LNGT Americas"), ref(IGU, "Northwest Stormpetrel")],
            "former Name 'LNGT Americas' (no ref prints it — the backend's own published value); IGU 2026 prints "
            "'Karadeniz LNGT Americas (ex-Northwest Stormpetrel)' — IGU's name is carried here, not as the Name"),
    "726": ("Karadeniz LNGT Powership Black Sea; Portovenere; LNG Portovenere", "Karadeniz LNGT Powership Black Sea", "G",
            [ref(IGU, "Karadeniz LNGT Powership Black Sea"),
             ref(MT + "KARADENIZ-LNGT-POWERSHIP-BLACK-SEA/9064073/352004132", "Karadeniz LNGT Powership Black Sea"),
             ref(IGU, "Portovenere"), ref(IGU, "LNG Portovenere")],
            "Name stays 'KLNGTP Black Sea' (vesseltracker.com live AIS name); the long form IGU 2026 and "
            "marinetraffic.org print is carried here (Baird 2026-09-21), with IGU's (ex-…) names"),
    "727": ("Karadeniz LNGT Powership Marmara; Lerici; LNG Lerici", "Karadeniz LNGT Powership Marmara", "G",
            [ref(IGU, "Karadeniz LNGT Powership Marmara"),
             ref(MT + "KARADENIZ-LNGT-POWERSHIP-MARMARA/9064085/352004078", "Karadeniz LNGT Powership Marmara"),
             ref(IGU, "Lerici"), ref(IGU, "LNG Lerici")],
            "Name stays 'KLNGTP Marmara' (vesseltracker.com live AIS name); the long form IGU 2026 and "
            "marinetraffic.org print is carried here (Baird 2026-09-21), with IGU's (ex-…) names"),
    "1004": ("Seapeak Hispania; Seapeak Jupiter", "Seapeak Hispania", "Y",
             [ref(SV + "115017", "Seapeak Hispania"), ref(SV_API + "115017", "Seapeak Hispania"), ref(IGU, "Seapeak Jupiter")],
             "former Name 'Seapeak Hispania'; the row is renamed 'Gas Polaris'; IGU 2026's 'Seapeak Jupiter' carried here"),
    "866": ("Metagas Everest; Arctic Metagas", "Metagas Everest", "G",
            [ref(IGU, "Metagas Everest"), ref(IGU, "Arctic Metagas")],
            "former Name 'Metagas Everest'; the row is renamed 'Arctic Metagaz'; IGU 2026's spelling 'Arctic Metagas' carried here"),
    "459": ("Condor LNG; CCH LNG; LNG Soars; Methane Lydon Volney", "CCH LNG", "Y",
            [ref(IGU, "LNG Soars"), ref(IGU, "Methane Lydon Volney")],
            "former Name 'CCH LNG' (no ref prints it — the backend's own published value); the row is renamed "
            "'LNG Scorpio'; IGU 2026 prints 'LNG Soars (ex-Methane Lydon Volney)' — both carried here"),
    "729": ("Cool Baltic; SCF Melampus", "Cool Baltic", "Y",
            [ref(IGU, "Cool Baltic"), ref(IGU, "SCF Melampus")],
            "Name stays 'Kool Baltic' (shipvault, marinetraffic.org, vesseltracker.com); IGU 2026 prints "
            "'Cool Baltic (ex-SCF Melampus)' — probably IGU's misspelling; reject to leave it out"),
    "1100": ("Vivit City LNG", "Vivit City LNG", "Y", [ref(IGU, "Vivit City LNG")],
             "Name stays 'Vivirt City LNG' (shipvault, marinetraffic.org, vesseltracker.com); IGU 2026 prints "
             "'Vivit City LNG' — probably IGU's misspelling; reject to leave it out"),
    "263": ("Hull H1799A (Hudong); Fath Al Khair", "Hull H1799A", "Y", [ref(IGU, "Fath Al Khair")],
            "former Name 'Hull H1799A'; the row is named 'Fat'h Al Khair'; IGU 2026's spelling 'Fath Al Khair' carried here"),
    "686": ("Ergy", "Ergy", "Y", [ref(VT + "Ergy-9250725.html"), ref(SV + "116466")],
            "Name stays IGU's 'Hongkong Energy' (the trading name); every database prints the demolition-voyage "
            "name 'Ergy' for IMO 9250725 (shipvault: SCRAPPED) — carried here. Status is still `active`: needs a scrapped fix"),
}


def main():
    d = json.loads(B8.read_text())
    for row in d["corrections"]:
        rid = row["row_id"]
        if rid not in NAMES:
            continue
        cells = [c for c in row["cells"] if c["field"] != "Name"]
        if NAMES[rid]:
            value, conf, former, refs, note = NAMES[rid]
            cells.append({"field": "Name", "new_value": value, "confidence": conf, "refs": refs,
                          "note": f"{note} [{RULE}]", "former_name": former})
        row["cells"] = cells
    d["corrections"] = [r for r in d["corrections"] if r["cells"]]
    B8.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")

    d = json.loads(B10.read_text())
    by_id = {r["row_id"]: r for r in d["corrections"]}
    for rid, (value, gate, conf, refs, note) in OTHER.items():
        cell = {"field": "Other names", "new_value": value, "gate_value": gate, "append_ref": True,
                "confidence": conf, "refs": refs, "note": f"{note} [{RULE}]"}
        row = by_id.get(rid)
        if row is None:
            row = {"row_id": rid, "cells": []}
            d["corrections"].append(row)
        row["cells"] = [c for c in row["cells"] if c["field"] != "Other names"] + [cell]
    B10.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
