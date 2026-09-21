"""merge_fills guards: the DF §5 derivable whitelist and the DF §5a order-total Price gate.

Regression for the 2026-09-17 data-fill batch, where research fills carrying a mis-set
`derivable: true` kept a per-vessel Price after the gate dropped its only URL.
"""
import json

import merge_fills

URL = "https://example.com/six-carriers-for-1-26bn"


def _fill(**kw):
    f = {"row_id": "274", "field": "Price", "ref_field": "Price [ref]",
         "proposed_value": "210000000", "new_urls": [URL], "confidence": "Y",
         "derivable": False, "prev_state": "blank", "note": ""}
    f.update(kw)
    return f


def _run(tmp_path, monkeypatch, fills, page_values):
    """Run main() against a fake gate: a URL corroborates only `page_values`."""
    monkeypatch.setenv("LNGCT_WORK_DIR", str(tmp_path))
    (tmp_path / "data_fill.json").write_text(json.dumps({"fills": fills}))
    monkeypatch.setattr(
        merge_fills, "corroborates_cell",
        lambda u, v, field="", imo="": (True, "OK") if str(v) in page_values
        else (False, "none of expected content found"))
    merge_fills.main()
    return json.loads((tmp_path / "data_fill.json").read_text())


class TestOrderTotal:
    def test_valid(self):
        assert merge_fills.order_total(_fill(derived_from={"total": "1260000000", "n": 6})) \
            == ("1260000000", None)

    def test_rounded_quotient(self):
        f = _fill(proposed_value="214285714", derived_from={"total": 1500000000, "n": 7})
        assert merge_fills.order_total(f) == ("1500000000", None)

    def test_absent(self):
        assert merge_fills.order_total(_fill()) == (None, None)

    def test_wrong_arithmetic(self):
        total, problem = merge_fills.order_total(_fill(derived_from={"total": "1260000000", "n": 5}))
        assert total is None and "!=" in problem

    def test_price_only(self):
        f = _fill(field="Capacity", derived_from={"total": "1260000000", "n": 6})
        assert merge_fills.order_total(f)[0] is None

    def test_single_vessel_is_not_derived(self):
        f = _fill(derived_from={"total": "210000000", "n": 1})
        assert merge_fills.order_total(f)[0] is None


class TestDerivableWhitelist:
    def test_fields(self):
        assert merge_fills.is_derivable_field("Shipowner country/area")
        assert merge_fills.is_derivable_field("Yard location latitude")
        assert merge_fills.is_derivable_field("Price currency")
        assert not merge_fills.is_derivable_field("Price")

    def test_research_fill_cannot_ride_derivable(self, tmp_path, monkeypatch):
        out = _run(tmp_path, monkeypatch, [_fill(derivable=True)], {"1260000000"})
        assert out["fills"] == []
        assert out["documented_blanks"][0]["row_id"] == "274"

    def test_true_derivable_keeps_value_without_url(self, tmp_path, monkeypatch):
        f = _fill(field="Shipowner country/area", ref_field="Shipowner country/area [ref]",
                  proposed_value="Japan", derivable=True, confidence="G")
        out = _run(tmp_path, monkeypatch, [f], set())
        assert out["fills"][0]["new_urls"] == [] and out["fills"][0]["derivable"] is True

    def test_research_fill_with_no_url_is_demoted(self, tmp_path, monkeypatch):
        out = _run(tmp_path, monkeypatch, [_fill(new_urls=[])], {"210000000"})
        assert out["fills"] == []


class TestOrderTotalGate:
    def test_total_url_is_kept_and_capped_at_yellow(self, tmp_path, monkeypatch):
        f = _fill(confidence="G", derived_from={"total": "1260000000", "n": 6})
        out = _run(tmp_path, monkeypatch, [f], {"1260000000"})
        (kept,) = out["fills"]
        assert kept["new_urls"] == [URL]
        assert kept["confidence"] == "Y"
        assert kept["proposed_value"] == "210000000"

    def test_page_with_a_different_total_is_dropped(self, tmp_path, monkeypatch):
        f = _fill(derived_from={"total": "1260000000", "n": 6})
        out = _run(tmp_path, monkeypatch, [f], {"1300000000"})
        assert out["fills"] == []
        assert out["candidate_findings"][0]["url"] == URL

    def test_bad_derived_from_falls_back_to_the_cell_value(self, tmp_path, monkeypatch):
        f = _fill(derived_from={"total": "1260000000", "n": 5})
        out = _run(tmp_path, monkeypatch, [f], {"1260000000"})
        assert out["fills"] == []
