"""igu_refs: an IGU report PDF is a ref only for what it prints for the row's IMO."""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import igu_refs  # noqa: E402
import url_verifier  # noqa: E402

PDF = url_verifier.IGU_PDF["2025"]
REC = {"imo": "9981427", "name": "Al Nigyan (3387)", "shipowner": "QatarEnergy",
       "shipbuilder": "Hyundai", "capacity": 174000, "cargo_type": "Membrane",
       "vessel_type": "Conventional", "propulsion": "ME-GA", "delivery_year": 2025,
       "table": "orderbook"}


def table(*recs):
    by = {}
    for r in recs or (REC,):
        by.setdefault(r["imo"], []).append(r)
    return igu_refs.IguTable(records={"2025": by}, pairs=Counter())


def test_edition_and_field():
    assert igu_refs.edition_of(PDF) == "2025"
    assert igu_refs.edition_of("https://example.com/a.pdf") == ""
    assert igu_refs.field_of("Capacity [ref]") == "Capacity"


def test_value_is_checked_against_the_rows_own_record():
    t = table()
    assert t.check("2025", "9981427", "Capacity", "174000")[0] is True
    assert t.check("2025", "9981427", "Capacity", "174,000")[0] is True
    assert t.check("2025", "9981427", "Capacity", "180000")[0] is False
    assert t.check("2025", "9981427", "Delivery year", "2026")[0] is False
    assert t.check("2025", "9981427", "Propulsion type", "ME-GA")[0] is True
    assert t.check("2025", "9981427", "Status", "on order")[0] is True
    assert t.check("2025", "9981427", "Status", "active")[0] is False
    assert t.check("2025", "9981427", "Previous delivery year(s)", "2025")[0] is True


def test_a_column_igu_does_not_print_is_never_corroborated():
    ok, why = table().check("2025", "9981427", "Shipowner country/area", "China")
    assert ok is False and "no Shipowner country/area column" in why


def test_unknown_vessel_blank_imo_and_missing_extraction():
    t = table()
    assert t.check("2025", "1234567", "Capacity", "174000")[0] is False
    assert t.check("2025", "", "Capacity", "174000")[0] is False       # no IMO: a text match is not this vessel
    assert t.check("2031", "9981427", "Capacity", "174000")[0] is None


def test_hull_forms():
    t = table(REC,
              {**REC, "imo": "1018676", "name": "Hull CMHI-282-01"},
              {**REC, "imo": "1040693", "name": "Hull No.YZJ2022-1475"},
              {**REC, "imo": "9948700", "name": "Energy Fortitude (ex-Victor Hugo (8107)"})
    assert t.check("2025", "9981427", "Hull number", "Hull 3387 (HDHHI)")[0] is True
    assert t.check("2025", "9981427", "Hull number", "Hull 3388 (HDHHI)")[0] is False
    assert t.check("2025", "9981427", "Hull number", "Al Nigyan")[0] is False     # a name is not a hull
    assert t.check("2025", "1018676", "Hull number", "Hull CMHI-282-01")[0] is True
    assert t.check("2025", "1040693", "Hull number", "Hull YZJ2022-1475")[0] is True
    assert t.check("2025", "9948700", "Hull number", "Hull 8107")[0] is True
    assert t.check("2025", "9981427", "Other names", "Foo; Hull 3387 (HDHHI)")[0] is True
    assert t.check("2025", "9981427", "Name", "Al Nigyan")[0] is True


def test_corroborates_cell_overrides_a_text_match(monkeypatch):
    monkeypatch.setattr(url_verifier, "corroborates", lambda u, v, **k: (True, "OK"))
    t = table()
    # 'China' is somewhere in a 1,000-vessel PDF; it is not this vessel's anything
    assert igu_refs.corroborates_cell(PDF, "China", "Shipowner country/area", "9981427", t)[0] is False
    assert igu_refs.corroborates_cell(PDF, "180000", "Capacity", "9981427", t)[0] is False
    assert igu_refs.corroborates_cell(PDF, "174000", "Capacity", "9981427", t)[0] is True
    # any other URL: the text gate stands; no IMO to look up: not a ref
    assert igu_refs.corroborates_cell("https://example.com/x", "China", "Shipowner country/area", "9981427", t) == (True, "OK")
    assert igu_refs.corroborates_cell(PDF, "174000", "Capacity", "", t)[0] is False


def test_corroborates_cell_keeps_dead_and_blocked(monkeypatch):
    monkeypatch.setattr(url_verifier, "corroborates", lambda u, v, **k: (False, "HTTP 404"))
    assert igu_refs.corroborates_cell(PDF, "174000", "Capacity", "9981427", table()) == (False, "HTTP 404")
