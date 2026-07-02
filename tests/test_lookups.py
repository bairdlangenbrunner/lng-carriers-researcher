"""Tests for scripts/lookups.py + the table-first yard-location autofill.

These guard the authoritative builder/owner facts layer: that the loaders resolve
raw names through normalize, drop blank/AMBIGUOUS facts so they're never
auto-applied, and that the data table wins over the backend-sibling scan.
Pure logic, no network — see tests/README.md.
"""
import lookups
from lookups import CONTROLLED_VOCAB, AMBIGUOUS, builder_facts, owner_facts, _usable


class TestControlledVocab:
    def test_core_columns_present(self):
        for col in ("Cargo type", "Vessel type", "Propulsion type",
                    "Capacity units", "Price currency"):
            assert col in CONTROLLED_VOCAB

    def test_known_tokens(self):
        assert "membrane" in CONTROLLED_VOCAB["Cargo type"]
        assert "ME-GA" in CONTROLLED_VOCAB["Propulsion type"]
        assert CONTROLLED_VOCAB["Capacity units"] == {"cbm"}


class TestUsable:
    def test_drops_blank_and_ambiguous(self):
        block = {"a": "x", "b": "", "c": AMBIGUOUS}
        assert _usable(block) == {"a": "x"}


class TestOwnerFacts:
    def test_resolves_via_normalize(self):
        # 'Celsius Tankers' must normalize to the same tag as the seeded 'celsius'.
        facts = {"celsius": {"Shipowner country/area": "Denmark",
                             "Shipowner country/area [ref]": "http://example.com"}}
        assert owner_facts("Celsius Tankers", facts)["Shipowner country/area"] == "Denmark"

    def test_ambiguous_owner_is_not_applied(self):
        facts = {"mol": {"Shipowner country/area": AMBIGUOUS,
                         "Shipowner country/area [ref]": ""}}
        assert owner_facts("Mitsui OSK Lines", facts) == {}

    def test_unknown_owner_returns_empty(self):
        assert owner_facts("Totally New Owner Ltd", {}) == {}


class TestBuilderFacts:
    def test_resolves_via_normalize(self):
        facts = {"cmhi": {"Shipbuilder yard country/area": "China"}}
        got = builder_facts("China Merchants Heavy Industries", facts)
        assert got["Shipbuilder yard country/area"] == "China"


class TestYardMapTableFirst:
    def test_table_overrides_sibling_but_keeps_blanks(self, monkeypatch):
        import build_workbook as bw
        header = ["Shipbuilder", "Shipbuilder yard country/area", "Yard location latitude"]
        # backend sibling has an OLD country and a latitude the table omits
        data = [["China Merchants Heavy Industries", "OldCountry", "11.0"]]
        monkeypatch.setattr(bw, "load_builder_facts",
                            lambda: {"cmhi": {"Shipbuilder yard country/area": "China"}})
        m = bw._yard_location_map_table_first(data, header)
        assert m["cmhi"]["Shipbuilder yard country/area"] == "China"   # table wins
        assert m["cmhi"]["Yard location latitude"] == "11.0"           # sibling kept where table blank

    def test_builder_absent_from_table_falls_back_to_sibling(self, monkeypatch):
        import build_workbook as bw
        header = ["Shipbuilder", "Shipbuilder yard country/area"]
        data = [["Some New Yard", "Freedonia"]]
        monkeypatch.setattr(bw, "load_builder_facts", lambda: {})
        m = bw._yard_location_map_table_first(data, header)
        assert m["some new yard"]["Shipbuilder yard country/area"] == "Freedonia"
