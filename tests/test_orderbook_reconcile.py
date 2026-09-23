"""Tests for scripts/orderbook_reconcile.py — the whole-orderbook completeness pass.

Two things here are load-bearing and both were live bugs during the 2026-09-23
build, which is why they are pinned:

  * the hull key. Every source writes the same hull differently ("Samsung 2808"
    / "Hull 2316 (SHI)" / "Jiangnan H2709" vs "Hull 2702"), and normalize_hull()
    only canonicalizes the CSB shape. Keying on it put all 286 CSB hulls in the
    residue — i.e. reported the entire orderbook as missing from the backend.
  * row identity. A stub row (columns A-E pasted by hand) has no column-A
    row_id, so keying the match sets on it collapsed all twelve stubs onto one
    identity and the first match claimed the lot.

Pure logic, no network.
"""
import csv
import json

import pytest
from normalize import hull_core
from orderbook_reconcile import backend_rows, enrich_stubs, reconcile, yard_tag

HEADER = [
    "id", "Name", "Name [ref]", "IMO number", "IMO number [ref]", "Status",
    "Shipowner", "Shipbuilder", "Hull number", "Contract date",
    "Capacity (cbm)", "Delivery year",
]
I = {h: i for i, h in enumerate(HEADER)}


def _row(**vals):
    r = [""] * len(HEADER)
    for k, v in vals.items():
        r[I[k]] = str(v)
    return r


def _backend(tmp_path, rows):
    path = tmp_path / "backend.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["" for _ in HEADER])       # preamble row, as the live sheet has
        w.writerow(HEADER)
        w.writerows(rows)
    (tmp_path / "backend.colmap.json").write_text(json.dumps({
        "_header_row_idx": 1, "_data_starts_at": 2,
        "row_id": I["id"], "name": I["Name"], "imo": I["IMO number"],
        "status": I["Status"], "shipowner": I["Shipowner"],
        "shipbuilder": I["Shipbuilder"], "hull": I["Hull number"],
        "contract_date": I["Contract date"], "capacity": I["Capacity (cbm)"],
        "delivery_year": I["Delivery year"],
    }))
    from backend_io import load_backend
    return load_backend(str(path))


def _csb(yard, hull, *, cap="174,000", owner="MISC Berhad", delivery="2029-06",
         assigned=True, kind="LNG Tanker"):
    return {"yard": yard, "hull": hull, "hull_assigned": assigned,
            "typecap": f"{kind}, {cap} cbm", "owner": owner,
            "delivery": delivery, "contract": "2026-01", "page": 1}


EMPTY_IGU = {"orderbook": []}


# --- the hull key ------------------------------------------------------------

@pytest.mark.parametrize("csb,backend", [
    ("Samsung 2808", "Hull 2808 (SHI)"),
    ("Hanwha 2628", "Hull 2628 (Hanwha)"),
    ("Daewoo 2558", "Hull 2558 (Hanwha)"),        # CSB still prints the old yard name
    ("Jiangnan H2709", "Hull 2709"),              # lone H on one side only
    ("Hudong Zhonghua H2017A", "Hull 2017A (Hudong)"),
    ("Hyundai Samho 8359", "Hull 8359 (HSHI)"),
    ("Zvezda 42", "Hull 042 (Zvezda)"),           # leading zeros
    ("Dalian G175k-4", "Hull G175K-04"),
])
def test_the_same_hull_written_two_ways_gets_one_key(csb, backend):
    assert hull_core(csb) == hull_core(backend) != ""


def test_a_yard_name_with_no_hull_number_has_no_key():
    # CSB prints the yard's own name until it indexes a hull; that must never
    # become a key, or every un-numbered slot at a yard would match every other.
    assert hull_core("Hanwha Ocean") == ""
    assert hull_core("Hudong Zhonghua") == ""
    assert hull_core("") == ""


def test_different_hulls_never_share_a_key():
    assert hull_core("Samsung 2808") != hull_core("Samsung 2809")
    assert hull_core("Hull 2017A (Hudong)") != hull_core("Hull 2017B (Hudong)")


# --- matching ----------------------------------------------------------------

def test_a_csb_hull_the_backend_holds_is_not_a_residue(tmp_path):
    be = _backend(tmp_path, [_row(id="1", Name="Hull 2808 (SHI)", Status="on order",
                                  Shipowner="Purus", Shipbuilder="Samsung Heavy Industries",
                                  **{"Hull number": "Hull 2808 (SHI)"})])
    r = reconcile([_csb("samsung", "Samsung 2808", owner="Purus Marine")],
                  backend_rows(be), EMPTY_IGU, 2026)
    assert r["csb_unmatched"] == []
    assert r["backend_only"] == []


def test_a_csb_hull_in_no_backend_row_is_a_residue(tmp_path):
    be = _backend(tmp_path, [_row(id="1", Name="Hull 2808 (SHI)", Status="on order",
                                  Shipbuilder="Samsung Heavy Industries",
                                  **{"Hull number": "Hull 2808 (SHI)"})])
    r = reconcile([_csb("samsung", "Samsung 2900", owner="Purus Marine")],
                  backend_rows(be), EMPTY_IGU, 2026)
    assert [c["hull"] for c in r["csb_unmatched"]] == ["Samsung 2900"]


def test_a_delivered_backend_row_is_not_a_missing_vessel(tmp_path):
    # CSB keeps a hull on its orderbook past handover. The backend row exists
    # and says `active` -- a status finding, never a discovery candidate.
    be = _backend(tmp_path, [_row(id="1", Name="Puteri Johor", Status="active",
                                  Shipbuilder="Hudong-Zhonghua Shipbuilding",
                                  **{"Hull number": "Hull 1894A (Hudong)"})])
    r = reconcile([_csb("hudong-zhonghua", "Hudong Zhonghua H1894A")],
                  backend_rows(be), EMPTY_IGU, 2026)
    assert r["csb_unmatched"] == []
    assert [c["backend"][0]["sheet_row"] for c in r["csb_status"]] == [3]


def test_an_unnumbered_csb_slot_is_counted_not_matched(tmp_path):
    be = _backend(tmp_path, [_row(id="1", Name="x", Status="on order",
                                  Shipbuilder="Hanwha Ocean")])
    r = reconcile([_csb("hanwha-ocean", "Hanwha Ocean", assigned=False)],
                  backend_rows(be), EMPTY_IGU, 2026)
    assert len(r["csb_no_hull"]) == 1
    assert r["csb_unmatched"] == []


def test_a_placeholder_row_takes_the_hull_rather_than_being_re_proposed(tmp_path):
    # The backend holds the order as "Hudong-Zhonghua (MISC 1)" with no hull.
    # CSB has indexed a hull for it. That is a hull number to propose for row 3,
    # not a thirteenth MISC vessel.
    be = _backend(tmp_path, [_row(id="1", Name="Hudong-Zhonghua (MISC 1)", Status="on order",
                                  Shipowner="MISC", Shipbuilder="Hudong-Zhonghua Shipbuilding",
                                  **{"Capacity (cbm)": "174000", "Delivery year": "2029"})])
    r = reconcile([_csb("hudong-zhonghua", "Hudong Zhonghua H2014A")],
                  backend_rows(be), EMPTY_IGU, 2026)
    assert r["csb_unmatched"] == []
    assert r["csb_hull_to_add"][0]["backend"]["sheet_row"] == 3


def test_two_csb_hulls_never_claim_the_same_placeholder_row(tmp_path):
    be = _backend(tmp_path, [_row(id="1", Name="Hudong-Zhonghua (MISC 1)", Status="on order",
                                  Shipowner="MISC", Shipbuilder="Hudong-Zhonghua Shipbuilding",
                                  **{"Capacity (cbm)": "174000", "Delivery year": "2029"})])
    r = reconcile([_csb("hudong-zhonghua", "Hudong Zhonghua H2014A"),
                   _csb("hudong-zhonghua", "Hudong Zhonghua H2015A")],
                  backend_rows(be), EMPTY_IGU, 2026)
    assert len(r["csb_hull_to_add"]) == 1
    assert len(r["csb_unmatched"]) == 1


def test_a_residue_says_which_field_kept_it_one(tmp_path):
    be = _backend(tmp_path, [_row(id="1", Name="Samsung HI (MISC FSRU)", Status="on order",
                                  Shipowner="MISC", Shipbuilder="Samsung Heavy Industries",
                                  **{"Capacity (cbm)": "170000", "Delivery year": "2029"})])
    r = reconcile([_csb("samsung", "Samsung 2797", cap="300,000", delivery="2029-02")],
                  backend_rows(be), EMPTY_IGU, 2026)
    near = r["csb_unmatched"][0]["near"]
    assert near[0]["sheet_row"] == 3 and "capacity" in near[0]["differs"]


def test_a_vessel_delivered_years_ago_is_not_a_near_miss(tmp_path):
    be = _backend(tmp_path, [_row(id="1", Name="La Mancha Knutsen", Status="active",
                                  Shipowner="Knutsen", Shipbuilder="HD Hyundai Heavy Industries",
                                  **{"Delivery year": "2016"})])
    r = reconcile([_csb("hyundai-ulsan", "Hyundai Ulsan 3644", owner="Knutsen OAS Shipping",
                        delivery="2029-01")], backend_rows(be), EMPTY_IGU, 2026)
    assert r["csb_unmatched"][0]["near"] == []


# --- stub rows ---------------------------------------------------------------

STUBS = [_row(id="", Name="Hull H2706"), _row(id="", Name="Hull H2707"),
         _row(id="", Name="HD Hyundai HI (HDHHI) Ulsan (Tsakos 2)")]


def _batch(tmp_path, cands):
    d = tmp_path / "batch"
    d.mkdir()
    (d / "candidates.json").write_text(json.dumps({"candidates": [
        {"cluster_id": f"C{i}", "row_data": rd} for i, rd in enumerate(cands)]}))
    return str(d)


def test_a_stub_row_is_matched_by_the_hull_in_its_name(tmp_path):
    # No Shipbuilder to key on, but the hull is sitting in the Name.
    r = reconcile([_csb("jiangnan", "Jiangnan H2706", owner="ADNOC")],
                  backend_rows(_backend(tmp_path, STUBS)), EMPTY_IGU, 2026)
    assert r["csb_unmatched"] == []
    assert r["csb_stub"][0]["backend"][0]["sheet_row"] == 3


def test_every_stub_keeps_its_own_identity(tmp_path):
    # All three stubs have a blank column-A row_id. Keyed on that they are one
    # row, and the second CSB hull matches nothing.
    r = reconcile([_csb("jiangnan", "Jiangnan H2706", owner="ADNOC"),
                   _csb("jiangnan", "Jiangnan H2707", owner="ADNOC")],
                  backend_rows(_backend(tmp_path, STUBS)), EMPTY_IGU, 2026)
    assert sorted(c["backend"][0]["sheet_row"] for c in r["csb_stub"]) == [3, 4]


def test_a_stub_gets_its_batch_attributes_back_and_stops_being_a_candidate(tmp_path):
    rows = backend_rows(_backend(tmp_path, STUBS))
    batch = _batch(tmp_path, [{"Name": "HD Hyundai HI (HHI) Ulsan (Tsakos 2)",
                               "Shipbuilder": "HD Hyundai Heavy Industries",
                               "Shipowner": "Tsakos", "Delivery year": "2029"}])
    assert enrich_stubs(rows, [batch]) == 1          # (HHI) in the batch, (HDHHI) in the sheet
    r = reconcile([_csb("hyundai-ulsan", "Hyundai Ulsan 3644", owner="Tsakos Group",
                        delivery="2029-01")], rows, EMPTY_IGU, 2026)
    assert r["csb_unmatched"] == []
    assert r["csb_hull_to_add"][0]["backend"]["sheet_row"] == 5


def test_a_dropped_ordinal_still_finds_its_candidate(tmp_path):
    # The workbook numbers a one-vessel cluster; the paste drops the "1".
    rows = backend_rows(_backend(tmp_path, [
        _row(id="", Name="HD Hyundai HI (HDHHI) Ulsan (unknown shipowner)")]))
    batch = _batch(tmp_path, [{"Name": "HD Hyundai HI (HHI) Ulsan (unknown shipowner 1)",
                               "Shipbuilder": "HD Hyundai Heavy Industries",
                               "Delivery year": "2029"}])
    assert enrich_stubs(rows, [batch]) == 1
    assert rows[0]["builder_tag"] == yard_tag("hyundai-ulsan")


def test_an_ambiguous_ordinal_is_left_alone(tmp_path):
    # Four numbered sisters share one ordinal-free base -- guessing which is
    # which would be a coin flip, so nothing is enriched.
    rows = backend_rows(_backend(tmp_path, [_row(id="", Name="Samsung HI (Dynagas)")]))
    batch = _batch(tmp_path, [{"Name": f"Samsung HI (Dynagas {i})",
                               "Shipbuilder": "Samsung Heavy Industries"} for i in (1, 2)])
    assert enrich_stubs(rows, [batch]) == 0


# --- IGU side ----------------------------------------------------------------

def test_an_igu_orderbook_imo_the_backend_holds_is_not_a_residue(tmp_path):
    be = _backend(tmp_path, [_row(id="1", Name="X", Status="on order",
                                  **{"IMO number": "9900001"},
                                  Shipbuilder="Samsung Heavy Industries")])
    igu = {"orderbook": [{"imo": "9900001", "name": "X",
                          "shipbuilder": "Samsung Heavy Industries"}]}
    r = reconcile([], backend_rows(be), igu, 2026)
    assert r["igu_unmatched"] == [] and r["igu_status"] == []


def test_igu_no_imo_rows_are_compared_as_counts(tmp_path):
    be = _backend(tmp_path, [_row(id=str(i), Name=f"Hull {i}", Status="on order",
                                  Shipowner="Knutsen", Shipbuilder="Hanwha Ocean",
                                  **{"Capacity (cbm)": "174000", "Delivery year": "2029"})
                             for i in (1, 2)])
    igu = {"orderbook": [{"imo": "", "name": f"TBN {i}", "shipowner": "Knutsen",
                          "shipbuilder": "Hanwha Ocean", "capacity": 174000,
                          "delivery_year": 2029} for i in range(3)]}
    c = reconcile([], backend_rows(be), igu, 2026)["igu_no_imo_clusters"][0]
    assert (c["igu_count"], c["backend_count"], c["delta"]) == (3, 2, 1)


# --- the ship-detail page's IMO ----------------------------------------------
# csb_fetch parses the yard ORDERBOOK LIST, which has no IMO column, so a hull
# key is the only thing the first three passes can match on. On 2026-09-23 that
# put nine vessels in the residue that the backend held all along -- under a
# NAME, with the hull cell blank (Hanwha 2593-2596 = rows 1031/1032/1034/1035,
# Qatar 9/10 = rows 888/889, Dalian G175K-5 = row 814 "Sea Energy"). The ship
# DETAIL page does print the IMO; these pin the pass that uses it.

def test_a_named_backend_row_is_found_by_the_ship_pages_imo(tmp_path):
    be = _backend(tmp_path, [_row(id="1", Name="Al Ghafat", **{"IMO number": "1069950"},
                                  Status="on order", Shipowner="Nakilat",
                                  Shipbuilder="Hanwha Ocean",
                                  **{"Capacity (cbm)": "170520", "Delivery year": "2027"})])
    c = _csb("hanwha-ocean", "Hanwha Ocean 2593", cap="170,520",
             owner="Unknown", delivery="2027-02")
    c["ship_url"] = "http://csb/ship?2593"
    r = reconcile([c], backend_rows(be), EMPTY_IGU, 2026,
                  ship_imo={"http://csb/ship?2593": "1069950"})
    assert r["csb_unmatched"] == []
    add = r["csb_hull_to_add"][0]
    assert add["matched_by"] == "ship-page imo"
    assert add["backend"]["sheet_row"] == 3 and add["backend"]["name"] == "Al Ghafat"


def test_an_imo_the_backend_does_not_hold_stays_a_residue_and_carries_it(tmp_path):
    be = _backend(tmp_path, [_row(id="1", Name="Somebody Else",
                                  **{"IMO number": "9000001"}, Status="on order")])
    c = _csb("samsung", "Samsung 2797", cap="300,000", delivery="2029-02")
    c["ship_url"] = "http://csb/ship?2797"
    r = reconcile([c], backend_rows(be), EMPTY_IGU, 2026,
                  ship_imo={"http://csb/ship?2797": "1180364"})
    assert len(r["csb_unmatched"]) == 1
    assert r["csb_unmatched"][0]["ship_page_imo"] == "1180364"


def test_the_imo_pass_routes_a_delivered_row_to_status_not_hull_to_add(tmp_path):
    be = _backend(tmp_path, [_row(id="1", Name="Puteri Johor", **{"IMO number": "9800001"},
                                  Status="active", Shipowner="MISC",
                                  Shipbuilder="Hudong-Zhonghua Shipbuilding")])
    c = _csb("hudong-zhonghua", "Hudong Zhonghua H1894A")
    c["ship_url"] = "http://csb/ship?1894"
    r = reconcile([c], backend_rows(be), EMPTY_IGU, 2026,
                  ship_imo={"http://csb/ship?1894": "9800001"})
    assert r["csb_unmatched"] == [] and r["csb_hull_to_add"] == []
    assert r["csb_status"][0]["backend"][0]["sheet_row"] == 3


def test_no_ship_imo_map_leaves_the_pass_a_no_op(tmp_path):
    """Purity: the fourth pass must change nothing when it has nothing to say."""
    be = _backend(tmp_path, [_row(id="1", Name="Al Ghafat", **{"IMO number": "1069950"},
                                  Status="on order", Shipbuilder="Hanwha Ocean")])
    c = _csb("hanwha-ocean", "Hanwha Ocean 2593", cap="170,520", owner="Unknown")
    c["ship_url"] = "http://csb/ship?2593"
    rows = backend_rows(be)
    assert (reconcile([c], rows, EMPTY_IGU, 2026)["csb_unmatched"]
            == reconcile([c], rows, EMPTY_IGU, 2026, ship_imo={})["csb_unmatched"])


class TestParseShipImo:
    def test_reads_the_imo_the_detail_page_prints(self):
        from orderbook_reconcile import _parse_ship_imo
        html = ("<div>Ship's Name / Hull No. <b>Dalian G175K-5</b> (Under Construction)"
                " Ship Type: LNG Tanker, 171,500 cbm IMO: 1013494 Owner: CMES</div>")
        assert _parse_ship_imo(html) == "1013494"

    def test_a_number_outside_the_ship_block_is_not_its_imo(self):
        from orderbook_reconcile import _parse_ship_imo
        assert _parse_ship_imo("<p>IMO: 9999999</p>") == ""

    def test_no_imo_on_the_page(self):
        from orderbook_reconcile import _parse_ship_imo
        assert _parse_ship_imo("<div>Ship's Name / Hull No. Hanwha Ocean 2700</div>") == ""
