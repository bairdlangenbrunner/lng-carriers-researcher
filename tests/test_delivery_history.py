"""delivery_history.py — a later Delivery year carries the former year along (RF §4.19)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import delivery_history as dh  # noqa: E402

HDR = ["row_id", "IMO", "Delivery year", "Delivery year [ref]", dh.FLAG, dh.PREV, dh.PREV + " [ref]"]
CM = {"imo": 1}


def _get(row, h):
    return row[HDR.index(h)].strip()


def _corr(new, conf="Y"):
    return {"row_id": "7", "cells": [{"field": "Delivery year", "new_value": new, "confidence": conf, "refs": []}]}


def test_later_year_adds_both_cells_with_the_igu_ref():
    row = ["7", "9918779", "2026", "https://www.igu.org/igu-reports/2025-world-lng-report", "", "", ""]
    corr = _corr("2027", "G")
    cells, why = dh.history_cells(corr, row, _get, CM, {"2026": {"9918779": 2026}}, gate=False)
    assert why is None
    prev, flag = cells
    assert (prev["field"], prev["new_value"], prev["gate_value"], prev["append_ref"]) == (dh.PREV, "2026", "2026", True)
    assert [r["url"] for r in prev["refs"]] == [dh.IGU_PDF["2026"]]        # landing page never asked
    assert (flag["field"], flag["new_value"], flag["refs"]) == (dh.FLAG, "yes", [])
    assert prev["confidence"] == flag["confidence"] == "G"
    assert corr["cells"][0]["former_year"] == "2026"


def test_second_delay_appends_oldest_first_and_never_twice():
    row = ["7", "1", "2027", "", "yes", "2025; 2026", "x"]
    cells, _ = dh.history_cells(_corr("2028"), row, _get, CM, {}, gate=False)
    assert cells[0]["new_value"] == "2025; 2026; 2027"
    row[5] = "2026; 2027"
    cells, _ = dh.history_cells(_corr("2028"), row, _get, CM, {}, gate=False)
    assert cells[0]["new_value"] == "2026; 2027"
    assert "left blank" in cells[0]["note"]


def test_earlier_or_same_year_is_not_a_delay():
    row = ["7", "1", "2026", "", "", "", ""]
    assert dh.history_cells(_corr("2025"), row, _get, CM, {}, gate=False) == ([], None)
    assert dh.history_cells(_corr("2026"), row, _get, CM, {}, gate=False) == ([], None)
    assert dh.history_cells(_corr("TBD"), row, _get, CM, {}, gate=False) == ([], "non-numeric year")


def test_idempotent():
    row = ["7", "1", "2026", "", "", "", ""]
    corr = _corr("2027")
    cells, _ = dh.history_cells(corr, row, _get, CM, {}, gate=False)
    corr["cells"].extend(cells)
    assert dh.history_cells(corr, row, _get, CM, {}, gate=False) == ([], None)


def test_a_sidebar_date_is_not_a_delivery_year(monkeypatch):
    import url_verifier
    from fetch import Page
    url_verifier._CACHE.clear()
    url_verifier._CACHE["https://ex.com/a"] = Page(status="200", text="<p>Seminar delivers guidance ... Floating energy 24 Feb 2026</p>")
    url_verifier._CACHE["https://ex.com/b"] = Page(status="200", text="<p>The vessel is scheduled for delivery in 2026 from Zvezda</p>")
    assert dh.states_delivery_year("https://ex.com/a", "2026")[0] is False
    assert dh.states_delivery_year("https://ex.com/b", "2026")[0] is True
    url_verifier._CACHE.clear()
