"""Tests for scripts/qc_backend.py — the column-offset / misplaced-value scanner.

The load-bearing guarantee: a clean row produces NO findings (low false-positive
rate, so the check stays trusted), and a row reproducing the real 1216/1217
offset corruption is caught loudly (the misplaced-value + column-offset signals).
Pure logic, no network.
"""
import pytest
import qc_backend as qc

# A compact but realistic header covering every column the checks touch.
HEADER = [
    "id", "IMO number", "IMO number [ref]", "Shipowner", "Shipbuilder",
    "Capacity", "Capacity units",
    "Cargo type", "Cargo type [ref]", "Vessel type", "Vessel type [ref]",
    "Propulsion type", "Propulsion type [ref]",
    "Yard location latitude", "Yard location longitude", "Yard location plus code",
    "Yard location accuracy", "Yard location lat/lon [ref]",
    "Delivery year", "Delivery year [ref]", "[Original source]",
    "Operator/charterer", "Operator/charterer [ref]",
    "Contract date", "Contract date [ref]",
    "Price", "Price currency", "Price [ref]",
    "Shipbuilder yard country/area", "Shipowner country/area",
]
I = {h: i for i, h in enumerate(HEADER)}
URL = "https://example.com/x"


def _row(**vals):
    r = [""] * len(HEADER)
    for k, v in vals.items():
        r[I[k]] = v
    return r


def _clean_row():
    return _row(
        id="1", Shipowner="Celsius Shipping",
        Shipbuilder="China Merchants Heavy Industries",
        Capacity="176400", **{"Capacity units": "cbm"},
        **{"Cargo type": "membrane", "Cargo type [ref]": URL,
           "Vessel type": "conventional", "Vessel type [ref]": URL,
           "Propulsion type": "ME-GA", "Propulsion type [ref]": URL,
           "Yard location latitude": "22.3", "Yard location longitude": "114.0",
           "Yard location plus code": "83QV+H7", "Yard location accuracy": "exact",
           "Delivery year": "2028", "Delivery year [ref]": URL,
           "[Original source]": "IGU",
           "Operator/charterer": "Clearlake Shipping", "Operator/charterer [ref]": URL,
           "Contract date": "01-May-2024", "Contract date [ref]": URL,
           "Shipbuilder yard country/area": "China", "Shipowner country/area": "Denmark"},
    )


def _offset_row():
    # The 1216/1217 signature: capacity/cargo block shoved 5 cols left into the
    # yard-location columns, and the tail shifted into the wrong columns.
    return _row(
        id="2", Shipowner="Celsius Shipping",
        Shipbuilder="China Merchants Heavy Industries",
        **{"Yard location latitude": "176400",          # capacity in latitude
           "Yard location longitude": "cbm",            # units in longitude
           "Yard location plus code": URL,              # a [ref] in plus code
           "Yard location accuracy": "membrane",        # cargo in accuracy
           "Delivery year [ref]": "conventional",       # vessel type in a [ref]
           "[Original source]": URL,                    # a URL in the source-name col
           "Operator/charterer": "ME-GA",               # propulsion in operator
           "Contract date": "2028",                     # delivery year in contract date
           "Price": "Claude - agentic workflow",        # source tag in price
           "Price currency": "Clearlake Shipping"},     # operator in price currency
    )


@pytest.fixture(autouse=True)
def _no_facts(monkeypatch):
    # Keep tests hermetic: don't consult the live refdata facts CSVs.
    monkeypatch.setattr(qc, "load_builder_facts", lambda: {})
    monkeypatch.setattr(qc, "load_owner_facts", lambda: {})


def _scan(rows):
    findings, _, _ = qc.scan(HEADER, rows, rid_idx=0)
    return findings


class TestCleanRow:
    def test_clean_row_has_no_findings(self):
        assert _scan([_clean_row()]) == []


class TestOffsetRow:
    def setup_method(self):
        self.f = _scan([_offset_row()])
        self.pairs = {(x["check"], x["column"]) for x in self.f}

    def test_flags_column_offset(self):
        assert any(x["check"] == "column-offset" for x in self.f)

    def test_misplaced_units_and_propulsion(self):
        assert ("misplaced-vocab", "Yard location longitude") in self.pairs   # cbm
        assert ("misplaced-vocab", "Operator/charterer") in self.pairs        # ME-GA

    def test_capacity_in_latitude_is_bad_shape(self):
        assert ("bad-shape", "Yard location latitude") in self.pairs

    def test_vessel_type_token_in_ref(self):
        assert ("misplaced-in-ref", "Delivery year [ref]") in self.pairs

    def test_url_in_source_name_column(self):
        assert ("url-in-value", "[Original source]") in self.pairs


class TestProvenanceTokensNotFlagged:
    def test_clarkson_and_inferred_refs_are_allowed(self):
        # Non-URL provenance tokens are a backend convention, not corruption.
        row = _clean_row()
        row[I["Cargo type [ref]"]] = "clarkson"
        row[I["Vessel type [ref]"]] = "inferred"
        assert _scan([row]) == []
