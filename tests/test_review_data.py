"""review_app/review_data.py: full values, keys across batches, linked pairs, live rows."""
import csv
import json

import review_data
from review_fixture import LONG_OTHER, make_batches


def _build(tmp_path):
    backend, b = make_batches(tmp_path)
    data = review_data.build(list(b.values()), backend)
    return data, b


def test_full_values_survive(tmp_path):
    data, b = _build(tmp_path)
    p = data["proposals"][f"{b['fix_b'].name}::10|Other names"]
    assert len(LONG_OTHER) > 300 and p["proposed"] == LONG_OTHER
    assert p["note"] == "former name " * 20
    dec = {r["id"]: r for r in csv.DictReader(open(b["fix_b"] / "decisions.csv"))}
    assert len(dec["10|Other names"]["proposed_value"]) == 80   # the csv is the lossy one


def test_same_id_two_batches_two_keys_linked(tmp_path):
    data, b = _build(tmp_path)
    ka, kb = f"{b['fix_a'].name}::10|Status", f"{b['fix_b'].name}::10|Status"
    pa, pb = data["proposals"][ka], data["proposals"][kb]
    assert kb in pa["links"] and ka in pb["links"]
    assert "overlaps_batch" in pa["flags"] and "overlaps_batch" in pb["flags"]


def test_linked_pairs_from_header_names(tmp_path):
    data, b = _build(tmp_path)
    P = data["proposals"]
    name, other = f"{b['fix_a'].name}::10|Name", f"{b['fix_b'].name}::10|Other names"
    assert other in P[name]["links"] and name in P[other]["links"]
    assert "strict_pair" in P[name]["flags"]
    price, cur = f"{b['fix_a'].name}::10|Price", f"{b['fix_a'].name}::10|Price currency"
    assert cur in P[price]["links"]
    cap, units = f"{b['data_fill'].name}::5|Capacity", f"{b['data_fill'].name}::5|Capacity units"
    assert units in P[cap]["links"]
    # X <-> X [ref]: the ref-fill line on row 7 has no value line, so link only on row 5 data
    ref7 = P[f"{b['ref_fill'].name}::7|Capacity [ref]"]
    assert ref7["kind"] == "ref" and ref7["links"] == []


def test_x_and_x_ref_link(tmp_path):
    backend, b = make_batches(tmp_path)
    # a second ref-fill batch proposing a ref for row 5's Capacity, which batch data_fill fills
    rf = b["ref_fill"].parent / "b6_ref_fill"
    rf.mkdir()
    (rf / "citations.json").write_text(json.dumps({"cells": [
        {"row_id": "5", "field": "capacity_ref", "url": "http://cap/5b", "confidence": "Y", "note": ""}]}))
    from review_fixture import _run_apply
    _run_apply(rf, backend)
    data = review_data.build(list(b.values()) + [rf], backend)
    k = f"{rf.name}::5|Capacity [ref]"
    assert f"{b['data_fill'].name}::5|Capacity" in data["proposals"][k]["links"]


def test_live_row_from_sheet_row_map(tmp_path):
    data, b = _build(tmp_path)
    live = {v["row_id"]: v["live_row"] for v in data["vessels"] if not v["new"]}
    assert live == {"10": 3, "5": 4, "7": 5}          # preamble + header, then line order
    new = [v for v in data["vessels"] if v["new"]]
    assert len(new) == 1 and new[0]["live_row"] is None and new[0]["name"] == "Samsung HI (Owner D 1)"


def test_decisions_counts_verdicts_and_items(tmp_path):
    data, b = _build(tmp_path)
    P = data["proposals"]
    assert P[f"{b['fix_a'].name}::10|Name"]["decision"] == "accept"          # G
    assert P[f"{b['fix_b'].name}::10|Other names"]["decision"] == "hold"     # Y
    assert P[f"{b['fix_a'].name}::10|Name"]["refs"] == [{"url": "http://ship/10", "verdict": "PASS (OK)"}]
    assert P[f"{b['fix_a'].name}::10|Status"]["refs"][0]["verdict"] is None  # never invented
    assert "preserve_ref" in P[f"{b['fix_a'].name}::10|Price"]["flags"]
    assert P[f"{b['fix_a'].name}::10|Price"]["current_refs"] == ["http://p"]
    assert "append_ref" in P[f"{b['fix_b'].name}::10|Other names"]["flags"]
    items = [i for i in data["items"] if i["type"] == "conflict"]
    assert len(items) == 1 and items[0]["live_rows"] == [5]
    total = sum(sum(x["counts"].values()) for x in data["batches"])
    assert total == len(P)


def test_deterministic(tmp_path):
    backend, b = make_batches(tmp_path)
    one = review_data.build(list(b.values()), backend)
    two = review_data.build(list(reversed(list(b.values()))), backend)
    for d in (one, two):
        d.pop("built")
    assert json.dumps(one) == json.dumps(two)


def test_refuses_without_backend(tmp_path):
    import pytest
    with pytest.raises(SystemExit):
        review_data.check_backend(tmp_path / "nope.csv")


# ---- presentation: why / detail / sources ------------------------------------------------

def test_split_note_moves_provenance_and_restatement():
    note = ("'LNGT Americas' -> 'Karadeniz LNGT Americas': IGU restyling of a Karadeniz name "
            "[IGU 2026 Appendix 3 fleet table, PDF p.71; IMO 9045132; sole source per Baird ruling]")
    why, detail = review_data.split_note(note, "LNGT Americas", "Karadeniz LNGT Americas")
    assert why == "IGU restyling of a Karadeniz name"
    assert detail == ["IGU 2026 Appendix 3 fleet table, PDF p.71; IMO 9045132; "
                      "sole source per Baird ruling"]
    # a restatement of other values stays; a bracketed reason is not provenance
    assert review_data.split_note("'A' -> 'B': x", "A", "C")[0] == "'A' -> 'B': x"
    why, detail = review_data.split_note("sourced [charterer = owner; held for review]")
    assert why.endswith("held for review]") and detail == []


def test_split_note_long_note_loses_nothing():
    head = "Splash247: six 174,000 cu m vessels worth a combined $1.26bn; per-vessel = 210,000,000"
    aside = "DF 5a - derived from the reported order total, " + "equal split " * 20
    why, detail = review_data.split_note(f"{head} ({aside}).")
    assert why == head and detail == [aside]
    quote = "LNG Prime: '" + "word " * 30 + "end. Then " + "more " * 30 + "close.' tail"
    why, detail = review_data.split_note(quote)          # never cut inside a quotation
    assert "".join([why] + detail).replace(" ", "") == quote.replace(" ", "")
    assert why.count("'") % 2 == 0
    assert review_data.split_note("batches-dir-x says so", labels={"batches-dir-x": "8"})[0] \
        == "batch 8 says so"


def test_ref_status_and_label():
    assert review_data.ref_status("PASS (OK (cf_impersonate))") == ("verified", "")
    assert review_data.ref_status("FAIL (uncorroborated, not used) (URL log)")[0] == "failed"
    assert review_data.ref_status("READ")[0] == "read"
    assert review_data.ref_status(None) == ("unchecked", "")
    assert review_data.ref_label("https://shipvault.com/ships/501596", None) == "shipvault record"
    assert review_data.ref_label(
        "https://www.datocms-assets.com/1/igu-world-lng-report-2026.pdf", "71") \
        == "IGU World LNG Report 2026, p.71"


def test_present_refs_pdf_page_and_shipvault_merge():
    pdf = "https://www.datocms-assets.com/1/igu-world-lng-report-2026.pdf"
    (s,) = review_data.present_refs([{"url": pdf, "verdict": "PASS (OK)"}], "x [PDF p.71; IMO 9045132]")
    assert s["href"] == pdf + "#page=71" and s["status"] == "verified"
    page = "https://shipvault.com/ships/42"
    api = "https://shipvaultapi-x.azurewebsites.net/api/units/42"
    (s,) = review_data.present_refs([{"url": page, "verdict": "FAIL (uncorroborated)"},
                                     {"url": api, "verdict": "PASS (companion record corroborates)"}], "")
    assert s["url"] == page and s["companion"] == api and s["status"] == "verified"
    assert len(s["verdicts"]) == 2


def test_shipvault_companion_verdict(tmp_path):
    api = "https://shipvaultapi-x.azurewebsites.net/api/units/42"
    added = [{"where": "10|Hull number", "value": "8206", "url": api, "result": "ADDED"},
             {"where": "live row 7 (row_id 11) | Status [ref]", "value": "on order",
              "url": api, "result": "ADDED"},
             {"where": "12|Status", "value": "", "url": api, "result": "ADDED"}]
    (tmp_path / "shipvault_api_refs.json").write_text(json.dumps({"added": added}))
    by_cell, _ = review_data.gate_verdicts(tmp_path, {})
    assert by_cell[("10", "Hull number", api)].startswith("PASS")
    assert ("11", "Status", api) in by_cell
    assert ("12", "Status", api) not in by_cell          # logged without a value: not gated
    (tmp_path / "shipvault_api_refs.json").write_text(json.dumps({"added": 3}))
    assert review_data.gate_verdicts(tmp_path, {}) == ({}, {})


def test_backend_state():
    st = review_data.backend_state
    assert st("fill", "165000000.00", "165000000", [], [], keep_ref=True) == "in_backend"
    assert st("fill", "active", "active", ["http://a"], ["http://a", "http://b"]) == "in_backend"
    assert st("fill", "active", "active", ["http://a"], []) == "value_in_backend"
    assert st("fill", "on order", "active", [], []) == "" and st("fill", "", "", [], []) == ""
    assert st("fill", "Old One; Hull 1 (SHI)", "Hull 1 (SHI)", [], [], append=True) == "in_backend"
    assert st("ref", "", "", ["http://a"], ["http://a"]) == "in_backend"
    assert st("ref", "", "", ["http://a"], ["http://b"]) == ""
