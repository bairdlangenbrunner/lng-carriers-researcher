"""The §5 grade computed from the gate's own verdict (RF rev 28, Baird 2026-09-22).

The headline change: ONE live page that states the value is Green. What still holds a
cell at Yellow is the gate's own weakness — an archived-only pass, a value too generic
for a bare text hit to be this vessel's, or a carve-out (§4.18, DF §5a, a §3.8c conflict).
"""
import json

import confidence as C
import merge_fills

WAYBACK = "OK (via Wayback 20240612120000; live URL blocked, snapshot carries content)"
IGU = "OK (IGU 2026 prints '174000' for IMO 9123456, coordinate extraction)"


class TestPassKind:
    def test_plain_live_pass(self):
        assert C.pass_kind("OK") == "live_text"
        assert C.pass_kind("OK (all tokens present)") == "live_text"

    def test_archive_pass(self):
        assert C.pass_kind(WAYBACK) == "archive"

    def test_keyed_passes(self):
        assert C.pass_kind(IGU) == "live_keyed"
        assert C.pass_kind("OK (cf_clearance, shipvault_api)") == "live_keyed"
        assert C.pass_kind("OK (marinetraffic_api)") == "live_keyed"

    def test_blank_value_is_not_evidence(self):
        assert C.pass_kind("no value to corroborate") is None
        assert C.pass_kind("OK (no value to corroborate)") is None


class TestDistinctive:
    def test_specific_values(self):
        assert C.distinctive("Capacity", "174000")
        assert C.distinctive("Price", "250000000")
        assert C.distinctive("Name", "Gas Polaris")
        assert C.distinctive("Hull number", "Hull 2598 (Hanwha)")
        assert C.distinctive("IMO number", "9123456")
        assert C.distinctive("Contract date", "08-Jun-2026")

    def test_generic_values(self):
        assert not C.distinctive("Delivery year", "2027")
        assert not C.distinctive("Shipowner country/area", "Japan")
        assert not C.distinctive("Status", "active")
        assert not C.distinctive("Cargo type", "membrane")
        assert not C.distinctive("Yard location latitude", "34.88")
        assert not C.distinctive("Shipowner", "MOL")        # a 3-letter acronym is everywhere
        assert not C.distinctive("Capacity", "")

    def test_ref_column_reads_as_its_value_column(self):
        assert not C.distinctive("Status [ref]", "active")


class TestGrade:
    def test_one_live_page_is_green(self):
        """The rule change: a single trade-press page stating the figure is enough."""
        conf, why = C.grade([("https://splash247.com/a", "OK")], field="Capacity", value="174000")
        assert conf == C.GREEN and "live page" in why

    def test_keyed_record_is_green_even_for_a_generic_value(self):
        conf, _ = C.grade([("https://igu.org/r.pdf", IGU)], field="Delivery year", value="2027")
        assert conf == C.GREEN

    def test_generic_value_on_one_page_stays_yellow(self):
        conf, why = C.grade([("https://splash247.com/a", "OK")], field="Delivery year", value="2027")
        assert conf == C.YELLOW and "generic" in why

    def test_generic_value_on_two_hosts_is_green(self):
        conf, _ = C.grade([("https://splash247.com/a", "OK"), ("https://lngprime.com/b", "OK")],
                          field="Delivery year", value="2027")
        assert conf == C.GREEN

    def test_two_pages_on_the_same_host_are_one_source(self):
        conf, _ = C.grade([("https://splash247.com/a", "OK"), ("https://splash247.com/b", "OK")],
                          field="Delivery year", value="2027")
        assert conf == C.YELLOW

    def test_archive_only_is_yellow(self):
        conf, why = C.grade([("https://x.com/a", WAYBACK)], field="Capacity", value="174000")
        assert conf == C.YELLOW and "archived" in why

    def test_a_live_pass_beats_an_archived_one(self):
        conf, _ = C.grade([("https://x.com/a", WAYBACK), ("https://y.com/b", "OK")],
                          field="Capacity", value="174000")
        assert conf == C.GREEN

    def test_no_surviving_ref_is_red(self):
        assert C.grade([], field="Capacity", value="174000")[0] == C.RED

    def test_a_blank_value_pass_is_not_a_pass(self):
        assert C.grade([("https://x.com/a", "no value to corroborate")],
                       field="Capacity", value="174000")[0] == C.RED

    def test_a_cap_holds_an_otherwise_green_cell(self):
        conf, why = C.grade([("https://x.com/a", "OK")], field="Capacity", value="174000",
                            caps=[C.CAP_CONFLICT])
        assert conf == C.YELLOW and why == C.CAP_CONFLICT

    def test_a_cap_cannot_rescue_a_cell_with_no_refs(self):
        assert C.grade([], field="Capacity", value="174000", caps=[C.CAP_CONFLICT])[0] == C.RED


class TestRollsForward:
    def test_later_year(self):
        assert C.rolls_forward("2027", "2026")

    def test_earlier_or_same(self):
        assert not C.rolls_forward("2025", "2026")
        assert not C.rolls_forward("2026", "2026")

    def test_non_numeric(self):
        assert not C.rolls_forward("2027", "")
        assert not C.rolls_forward("unknown", "2026")


class TestMergeFillsGrades:
    """The data-fill path: merge_fills grades from the gate, ignoring the researcher label."""

    def _run(self, tmp_path, monkeypatch, fill, passes):
        monkeypatch.setenv("LNGCT_WORK_DIR", str(tmp_path))
        (tmp_path / "data_fill.json").write_text(json.dumps({"fills": [fill]}))
        monkeypatch.setattr(merge_fills, "corroborates_cell",
                            lambda u, v, field="", imo="": passes.get(u, (False, "page does not contain value")))
        merge_fills.main()
        return json.loads((tmp_path / "data_fill.json").read_text())["fills"]

    def _fill(self, **kw):
        f = {"row_id": "274", "field": "Capacity", "ref_field": "Capacity [ref]",
             "proposed_value": "174000", "new_urls": ["https://splash247.com/a"],
             "confidence": "Y", "derivable": False, "prev_state": "blank", "note": ""}
        f.update(kw)
        return f

    def test_a_researcher_yellow_is_promoted_by_the_gate(self, tmp_path, monkeypatch):
        out = self._run(tmp_path, monkeypatch, self._fill(),
                        {"https://splash247.com/a": (True, "OK")})
        assert out[0]["confidence"] == "G"
        assert "live page" in out[0]["confidence_why"]

    def test_a_researcher_green_is_demoted_by_the_gate(self, tmp_path, monkeypatch):
        out = self._run(tmp_path, monkeypatch,
                        self._fill(field="Delivery year", proposed_value="2027", confidence="G"),
                        {"https://splash247.com/a": (True, "OK")})
        assert out[0]["confidence"] == "Y"

    def test_an_order_total_price_is_capped(self, tmp_path, monkeypatch):
        out = self._run(tmp_path, monkeypatch,
                        self._fill(field="Price", proposed_value="210000000",
                                   derived_from={"total": "1260000000", "n": 6}, confidence="G"),
                        {"https://splash247.com/a": (True, "OK")})
        assert out[0]["confidence"] == "Y"
        assert out[0]["confidence_why"] == C.CAP_DERIVED

    def test_a_derivable_autofill_is_left_alone(self, tmp_path, monkeypatch):
        out = self._run(tmp_path, monkeypatch,
                        self._fill(field="Capacity units", proposed_value="cbm",
                                   new_urls=[], derivable=True, confidence="G"), {})
        assert out[0]["confidence"] == "G" and "confidence_why" not in out[0]


class TestFixModeGrades:
    """The fix path: build_workbook grades each cell and stamps the grade back into fix.json."""

    def _build(self, tmp_path, monkeypatch, cells, passes):
        import argparse

        import build_workbook
        import igu_refs
        from review_fixture import write_backend

        backend = write_backend(tmp_path)
        fix = tmp_path / "fix.json"
        fix.write_text(json.dumps({"batch_label": "t", "reason": "t", "corrections": [
            {"row_id": "10", "cells": cells}]}))
        monkeypatch.setattr(igu_refs, "corroborates_cell",
                            lambda u, v, field="", imo="": passes.get(u, (False, "page does not contain value")))
        out = tmp_path / "out"
        out.mkdir()
        build_workbook.build_fix(argparse.Namespace(
            fix=str(fix), backend=str(backend), base=None, out=str(out)))
        return {c["field"]: c for c in json.loads(fix.read_text())["corrections"][0]["cells"]}

    def test_one_live_page_makes_a_name_green(self, tmp_path, monkeypatch):
        cells = self._build(tmp_path, monkeypatch, [
            {"field": "Name", "new_value": "Atlantic Star", "confidence": "Y",
             "refs": [{"url": "https://splash247.com/a"}]}],
            {"https://splash247.com/a": (True, "OK")})
        assert cells["Name"]["confidence"] == "G"

    def test_a_roll_forward_needs_a_second_source(self, tmp_path, monkeypatch):
        cells = self._build(tmp_path, monkeypatch, [
            {"field": "Delivery year", "new_value": "2027", "confidence": "G",
             "former_year": "2026", "refs": [{"url": "https://shipvault.com/ships/1"}]}],
            {"https://shipvault.com/ships/1": (True, "OK (shipvault_api)")})
        assert cells["Delivery year"]["confidence"] == "Y"
        assert cells["Delivery year"]["confidence_why"] == C.CAP_ROLL_FORWARD

    def test_a_roll_forward_with_two_live_sources_is_green(self, tmp_path, monkeypatch):
        cells = self._build(tmp_path, monkeypatch, [
            {"field": "Delivery year", "new_value": "2027", "confidence": "Y",
             "former_year": "2026", "refs": [{"url": "https://shipvault.com/ships/1"},
                                             {"url": "https://lngprime.com/b"}]}],
            {"https://shipvault.com/ships/1": (True, "OK (shipvault_api)"),
             "https://lngprime.com/b": (True, "OK")})
        assert cells["Delivery year"]["confidence"] == "G"

    def test_companion_lines_follow_their_parent(self, tmp_path, monkeypatch):
        """RF §4.16 / §4.19: the former value is the backend's own — never red, never
        above the line it was split off from."""
        cells = self._build(tmp_path, monkeypatch, [
            {"field": "Delivery year", "new_value": "2027", "confidence": "Y",
             "former_year": "2026", "refs": [{"url": "https://shipvault.com/ships/1"},
                                             {"url": "https://lngprime.com/b"}]},
            {"field": "Previous delivery year(s)", "new_value": "2026", "append_ref": True,
             "gate_value": "2026", "confidence": "Y", "refs": []},
            {"field": "Delivery delayed", "new_value": "yes", "confidence": "Y", "refs": []}],
            {"https://shipvault.com/ships/1": (True, "OK (shipvault_api)"),
             "https://lngprime.com/b": (True, "OK")})
        assert cells["Delivery year"]["confidence"] == "G"
        assert cells["Previous delivery year(s)"]["confidence"] == "G"
        assert cells["Delivery delayed"]["confidence"] == "G"

    def test_a_preserve_ref_cell_keeps_its_declared_grade(self, tmp_path, monkeypatch):
        cells = self._build(tmp_path, monkeypatch, [
            {"field": "Name", "new_value": "Hudong-Zhonghua (MISC 1)", "confidence": "G",
             "preserve_ref": True}], {})
        assert cells["Name"]["confidence"] == "G"
        assert "confidence_why" not in cells["Name"]


class TestRegrade:
    """The retroactive pass: held lines re-gated live, promoted only upward."""

    def _setup(self, tmp_path, monkeypatch, passes, decisions=None, log=None):
        import csv as _csv

        import regrade_confidence as R
        from review_fixture import make_batches

        monkeypatch.setenv("LNGCT_WORK_DIR", str(tmp_path / "work"))
        (tmp_path / "work").mkdir()
        backend, batches = make_batches(tmp_path)
        batch = batches["fix_a"]

        dec = batch / "decisions.csv"
        with open(dec, encoding="utf-8", newline="") as f:
            rows, fields = list(_csv.DictReader(f)), _csv.DictReader(open(dec, encoding="utf-8")).fieldnames
        for r in rows:
            r["decision"] = (decisions or {}).get(r["id"], r["decision"])
        with open(dec, "w", encoding="utf-8", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        if log:
            (batch / "review_log.jsonl").write_text(
                "\n".join(json.dumps(r) for r in log) + "\n")

        monkeypatch.setattr(R, "corroborates_cell",
                            lambda u, v, field="", imo="": passes.get(u, (False, "page does not contain value")))
        return R, backend, batch

    def _run(self, R, backend, batch, monkeypatch, apply=True):
        import csv as _csv
        import sys

        argv = ["regrade_confidence", "--batch", str(batch), "--backend", str(backend)]
        monkeypatch.setattr(sys, "argv", argv + (["--apply"] if apply else []))
        R.main()
        with open(batch / "decisions.csv", encoding="utf-8", newline="") as f:
            return {r["id"]: r for r in _csv.DictReader(f)}

    def test_a_held_line_whose_ref_passes_live_is_promoted(self, tmp_path, monkeypatch):
        R, backend, batch = self._setup(
            tmp_path, monkeypatch, {"http://ship/10": (True, "OK")},
            decisions={"10|Name": "hold", "10|Status": "hold"})
        out = self._run(R, backend, batch, monkeypatch)
        assert out["10|Name"]["decision"] == "accept"
        assert out["10|Name"]["confidence"] == "G"
        cells = {c["field"]: c for c in
                 json.loads((batch / "fix.json").read_text())["corrections"][0]["cells"]}
        assert cells["Name"]["confidence"] == "G"
        rec = [json.loads(l) for l in (batch / "review_log.jsonl").read_text().splitlines()]
        assert rec[-1]["reviewer"] == R.REVIEWER and rec[-1]["decision"] == "accept"

    def test_a_generic_value_stays_held(self, tmp_path, monkeypatch):
        """Status 'active' is vocabulary — one bare text hit does not promote it."""
        R, backend, batch = self._setup(
            tmp_path, monkeypatch, {"http://ship/10": (True, "OK")},
            decisions={"10|Name": "hold", "10|Status": "hold"})
        out = self._run(R, backend, batch, monkeypatch)
        assert out["10|Status"]["decision"] == "hold"

    def test_nothing_is_ever_demoted_or_rejected(self, tmp_path, monkeypatch):
        """An accepted line whose ref now fails is left exactly as the reviewer left it."""
        R, backend, batch = self._setup(tmp_path, monkeypatch, {},
                                        decisions={"10|Name": "accept"})
        out = self._run(R, backend, batch, monkeypatch)
        assert out["10|Name"]["decision"] == "accept"
        assert out["10|Name"]["confidence"] == "G"

    def test_a_line_a_person_decided_is_left_alone(self, tmp_path, monkeypatch):
        R, backend, batch = self._setup(
            tmp_path, monkeypatch, {"http://ship/10": (True, "OK")},
            decisions={"10|Name": "hold"},
            log=[{"key": "b1_fix::10|Name", "decision": "hold", "reviewer": "baird",
                  "note": "want a second source", "ts": "2026-09-20T10:00:00-04:00"}])
        out = self._run(R, backend, batch, monkeypatch)
        assert out["10|Name"]["decision"] == "hold"

    def test_a_machine_record_does_not_take_a_line_out_of_scope(self, tmp_path, monkeypatch):
        R, backend, batch = self._setup(
            tmp_path, monkeypatch, {"http://ship/10": (True, "OK")},
            decisions={"10|Name": "hold"},
            log=[{"key": "b1_fix::10|Name", "decision": "hold", "reviewer": "backend sync",
                  "note": "", "ts": "2026-09-20T10:00:00-04:00"}])
        out = self._run(R, backend, batch, monkeypatch)
        assert out["10|Name"]["decision"] == "accept"

    def test_an_undo_back_to_undecided_does_not_take_a_line_out_of_scope(self, tmp_path, monkeypatch):
        R, backend, batch = self._setup(
            tmp_path, monkeypatch, {"http://ship/10": (True, "OK")},
            decisions={"10|Name": "hold"},
            log=[{"key": "b1_fix::10|Name", "decision": "accept", "reviewer": "baird",
                  "note": "", "ts": "2026-09-20T10:00:00-04:00"},
                 {"key": "b1_fix::10|Name", "decision": "hold", "reviewer": "baird",
                  "via": "undo", "undecided": True, "note": "", "ts": "2026-09-20T10:01:00-04:00"}])
        out = self._run(R, backend, batch, monkeypatch)
        assert out["10|Name"]["decision"] == "accept"

    def test_dry_run_writes_nothing(self, tmp_path, monkeypatch):
        R, backend, batch = self._setup(
            tmp_path, monkeypatch, {"http://ship/10": (True, "OK")},
            decisions={"10|Name": "hold"})
        out = self._run(R, backend, batch, monkeypatch, apply=False)
        assert out["10|Name"]["decision"] == "hold"
        assert (tmp_path / "work" / "regrade_report.csv").exists()

    def test_a_preserve_ref_line_is_out_of_scope(self, tmp_path, monkeypatch):
        """Cosmetic cells never ran the gate; there is nothing to re-grade."""
        R, backend, batch = self._setup(
            tmp_path, monkeypatch, {"http://ship/10": (True, "OK")},
            decisions={"10|Price": "hold"})
        out = self._run(R, backend, batch, monkeypatch)
        assert out["10|Price"]["decision"] == "hold"


class TestNoteCap:
    """A research note that documents doubt is the pre-`cap_reason` way of capping."""

    def test_a_documented_discrepancy_caps(self):
        assert C.note_cap("PARTIAL (1 domain). OWNER DISCREPANCY: databases say COSCO.")
        assert C.note_cap("Human review of owner stylization recommended.")
        assert C.note_cap("entity-level only; not confirmed by a second domain")

    def test_an_ordinary_note_does_not(self):
        assert C.note_cap("LNG Prime reports the 174,000-cbm order at Hanwha.") is None
        assert C.note_cap("") is None

    def test_it_holds_an_otherwise_green_cell(self):
        conf, why = C.grade([("https://x.com/a", "OK")], field="Capacity", value="174000",
                            caps=[C.note_cap("capacity DISCREPANCY across sources")])
        assert conf == C.YELLOW and "doubt" in why
