"""Tests for the former-name rule (RF §4.16): other_names.py + the append_ref fix cell.

A Name change moves the former Name into `Other names` — appended, never replacing —
while spelling fixes, wrong-vessel corrections and placeholder restylings do not.
Pure logic, no network (the gate is off or stubbed).
"""
import csv
import json
import sys

import apply_batch
import other_names
from backend_io import load_backend

HEADER = ["original order in sheet", "Name", "Name [ref]", "Other names", "Other names [ref]"]
COLMAP = {"_header_row_idx": 0, "_data_starts_at": 1, "row_id": 0}


def _backend(tmp_path, rows):
    csv_path = tmp_path / "backend.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
    (tmp_path / "backend.colmap.json").write_text(json.dumps(COLMAP))
    return csv_path


def _fix_batch(tmp_path, corrections):
    batch = tmp_path / "batch"
    batch.mkdir(exist_ok=True)
    (batch / "fix.json").write_text(json.dumps({"batch_label": "t", "corrections": corrections}))
    return batch


def _name(row_id, new, conf="G", refs=()):
    return {"row_id": row_id, "cells": [{"field": "Name", "new_value": new, "confidence": conf,
                                         "refs": [{"url": u, "soft": False} for u in refs]}]}


class TestClassify:
    def test_real_rename_and_placeholder_are_former_names(self):
        assert other_names.classify("Pioneer Spirit", "Arctic Pioneer", "LNG Pioneer", None) is None
        assert other_names.classify("Hull 2541 (Hanwha)", "Venture Pelican", "", None) is None
        assert other_names.classify("Dalian No 1 G175K-7", "Sea Charity", "", None) is None

    def test_spelling_and_truncation_are_not(self):
        for former, new in [("Greenenergy Wind", "Greenergy Wind"), ("Hoegh", "Hoegh Esperanza"),
                            ("Clean Srocco", "Clean Sirocco"), ("Al-Kheesha", "Al Kheesah")]:
            assert "spelling" in other_names.classify(former, new, "", None)

    def test_other_skips(self):
        assert "already" in other_names.classify("Condor LNG", "LNG Soars", "Condor LNG; X", None)
        assert "placeholder" in other_names.classify("Hanwha (Owner 1)", "Hanwha Ocean (Owner 1)", "", None)
        assert "another row" in other_names.classify("Puteri Sarawak", "Puteri Perlis", "", "live row 884")
        assert "same name" in other_names.classify("AL-NUAMAN", "Al Nuaman", "", None)


class TestBuildCells:
    def test_append_gate_value_and_wrong_vessel(self, tmp_path):
        be = load_backend(_backend(tmp_path, [
            ["1", "Pioneer Spirit", "http://old", "LNG Pioneer", "http://lp"],
            ["2", "Puteri Sarawak", "", "", ""],
            ["3", "Hull 9 (Yard)", "", "", ""],
        ]))
        payload = {"corrections": [_name("1", "Arctic Pioneer", refs=["http://igu"]),
                                   _name("2", "Puteri Perlis"),
                                   _name("3", "Puteri Sarawak")]}
        gate = other_names.Gate(enabled=False)
        proposals, skipped = other_names.build_cells([("b", payload)], be, gate)

        by_row = {p["row_id"]: p["cell"] for p in proposals}
        assert set(by_row) == {"1", "3"}
        assert by_row["1"]["new_value"] == "LNG Pioneer; Pioneer Spirit"
        assert by_row["1"]["gate_value"] == "Pioneer Spirit"
        assert by_row["1"]["append_ref"] is True
        assert by_row["1"]["confidence"] == "Y" and by_row["1"]["refs"] == []   # nothing gated
        assert [s["row_id"] for s in skipped] == ["2"]
        assert "another row" in skipped[0]["reason"]
        # candidates = the new name's refs + the row's existing Name [ref]
        assert [g["url"] for g in gate.log if g["where"].startswith("1|")] == ["http://igu", "http://old"]

    def test_passing_ref_inherits_name_confidence(self, tmp_path, monkeypatch):
        be = load_backend(_backend(tmp_path, [["1", "Golar Tundra", "", "", ""]]))
        gate = other_names.Gate(sleep=lambda s: None)
        monkeypatch.setattr(other_names.Gate, "passing", lambda self, urls, former, where, new="", imo="": urls[:1])
        proposals, _ = other_names.build_cells(
            [("b", {"corrections": [_name("1", "Italis LNG", refs=["http://igu"])]})], be, gate)
        assert proposals[0]["cell"]["confidence"] == "G"
        assert proposals[0]["cell"]["refs"] == [{"url": "http://igu", "soft": False}]

    def test_scattered_tokens_do_not_pass(self, monkeypatch):
        import url_verifier
        monkeypatch.setattr(url_verifier, "corroborates", lambda u, v: (True, "OK (all tokens present)"))
        gate = other_names.Gate(sleep=lambda s: None)
        assert gate.passing(["https://example.org/report.pdf"], "Energy Frontier", "1|Other names") == []

    def test_igu_name_cell_rescues_a_wrapped_ex_name(self, monkeypatch):
        import url_verifier
        monkeypatch.setattr(url_verifier, "corroborates", lambda u, v: (True, "OK (all tokens present)"))
        gate = other_names.Gate(sleep=lambda s: None, igu_names={
            "2026": {"9256602": "Arctic Pioneer (ex-LNG Pioneer / ex-Pioneer Spirit)"}})
        url = "https://www.datocms-assets.com/146580/1-igu-world-lng-report-2026.pdf"
        assert gate.passing([url], "Pioneer Spirit", "1|Other names", "Arctic Pioneer", "9256602") == [url]
        assert gate.passing([url], "Energy Frontier", "2|Other names", "Arunika Jaya", "9245720") == []

    def test_igu_landing_page_is_swapped_for_its_pdf_and_keyed_by_imo(self, monkeypatch):
        # the backend was seeded from IGU 2025: a bulk-loaded row's Name [ref] is the landing
        # page. It is never skipped — the edition's PDF is gated and cited in its place, on
        # what the extraction prints for THIS IMO (any long table prints someone's 3387).
        import url_verifier
        asked = []
        monkeypatch.setattr(url_verifier, "corroborates", lambda u, v: (asked.append(u), (True, "OK"))[1])
        gate = other_names.Gate(sleep=lambda s: None, igu_names={"2025": {"9981427": "Hull 3387"}})
        landing, pdf = "https://www.igu.org/igu-reports/2025-world-lng-report", other_names.IGU_PDF["2025"]
        assert gate.passing([landing], "Hull 3387 (HDHHI)", "186|Other names", "Al Nigyan", "9981427") == [pdf]
        assert asked == [pdf]
        assert gate.passing([landing], "Hull 3387 (HDHHI)", "9|Other names", "Other", "9999999") == []
        assert gate.igu_candidates("9981427", "Hull 3387 (HDHHI)") == [pdf]

    def test_igu_prints_name_hull_forms(self):
        assert other_names.igu_prints_name("Hull 3387", "Hull 3387 (HDHHI)")
        assert other_names.igu_prints_name("Al Nigyan (3387)", "Hull 3387 (HDHHI)")
        assert not other_names.igu_prints_name("Hull 3388", "Hull 3387 (HDHHI)")
        assert not other_names.igu_prints_name("", "Hull 3387 (HDHHI)")

    def test_former_name_inside_the_new_name_is_not_gated(self):
        gate = other_names.Gate(sleep=lambda s: None)
        assert gate.passing(["https://example.org/a"], "LNGT Americas", "1|Other names",
                            "Karadeniz LNGT Americas") == []
        assert "part of the new name" in gate.log[0]["verdict"]

    def test_trackers_not_asked_about_hull_placeholders(self):
        gate = other_names.Gate(sleep=lambda s: None)
        assert gate._skip("https://www.marinetraffic.org/x", "Hull 2541 (Hanwha)")
        assert gate._skip("https://www.vesselfinder.com/x", "Golar Tundra")
        assert gate._skip("https://shipvault.com/ships/1", "Hull 2541 (Hanwha)") is None


class TestPatchBatch:
    def test_idempotent_and_stamped(self, tmp_path):
        be = load_backend(_backend(tmp_path, [["1", "Golar Tundra", "", "", ""],
                                              ["2", "Hoegh", "", "", ""]]))
        batch = _fix_batch(tmp_path, [_name("1", "Italis LNG"), _name("2", "Hoegh Esperanza")])
        for _ in range(2):
            other_names.patch_batch(batch, be, other_names.Gate(enabled=False))
        corrs = json.loads((batch / "fix.json").read_text())["corrections"]
        assert [c["field"] for c in corrs[0]["cells"]] == ["Name", "Other names"]
        assert [c["field"] for c in corrs[1]["cells"]] == ["Name"]
        assert corrs[0]["cells"][0]["former_name"] == "proposed"
        assert corrs[1]["cells"][0]["former_name"].startswith("skipped: spelling")


class TestApplyAppendRef:
    def test_append_ref_joins_existing_ref_and_name_replaces(self, tmp_path, monkeypatch):
        backend = _backend(tmp_path, [["1", "Pioneer Spirit", "http://old", "LNG Pioneer", "http://lp"]])
        batch = _fix_batch(tmp_path, [{"row_id": "1", "cells": [
            {"field": "Name", "new_value": "Arctic Pioneer", "confidence": "G",
             "refs": [{"url": "http://igu", "soft": False}]},
            {"field": "Other names", "new_value": "LNG Pioneer; Pioneer Spirit",
             "gate_value": "Pioneer Spirit", "append_ref": True, "confidence": "G",
             "refs": [{"url": "http://igu", "soft": False}]},
        ]}])
        monkeypatch.setattr(sys, "argv", ["apply_batch", "--batch", str(batch),
                                          "--backend", str(backend)])
        apply_batch.main()
        rows = list(csv.reader(open(batch / "apply_rows.csv")))
        H = {h: i for i, h in enumerate(rows[0])}
        r = rows[1]
        assert r[H["Name"]] == "Arctic Pioneer" and r[H["Name [ref]"]] == "http://igu"
        assert r[H["Other names"]] == "LNG Pioneer; Pioneer Spirit"
        assert r[H["Other names [ref]"]] == "http://lp, http://igu"


# --- RF §4.17: IGU (ex-…) names and yard-tagged hulls ---------------------------------

def test_igu_ex_names_splits_chains_and_hulls():
    assert other_names.igu_ex_names("Karadeniz LNGT Antarctica (ex-Northwest Sanderling)") == \
        [("Northwest Sanderling", "")]
    exes = [e for e, _ in other_names.igu_ex_names("KLNGTP Black Sea (ex-Portovenere / ex-LNG Portovenere)")]
    assert exes == ["Portovenere", "LNG Portovenere"]
    assert other_names.igu_ex_names("Al Sailiya (2641)") == []


def test_hull_only_and_same_hull():
    assert other_names.hull_only("Hull 2563 (Hanwha)") == "2563"
    assert other_names.hull_only("Hudong-Zhonghua H1881A") == "H1881A"
    assert other_names.hull_only("Northwest Sanderling") == ""
    assert other_names.same_hull("H1881A", "1881A")
    assert not other_names.same_hull("2653", "2563")


def test_fallback_yard_tags_cover_untagged_yards():
    assert other_names.FALLBACK_YARD_TAGS["Hudong-Zhonghua Shipbuilding"] == "Hudong"
    assert other_names.FALLBACK_YARD_TAGS["Jiangnan Shipyard"] == "Jiangnan"
