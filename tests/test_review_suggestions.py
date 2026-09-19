"""review_app/suggestions.py: latest suggest record per key -> a standard fix.json."""
import json

import pytest

import review_data
import store
import suggestions
from review_fixture import make_batches


@pytest.fixture
def env(tmp_path):
    backend, b = make_batches(tmp_path)
    data = review_data.build(list(b.values()), backend)
    dirs = {d.name: d for d in b.values()}

    def suggest(bkey, pid, value, kind="value", note="n"):
        store.decide([{"key": f"{b[bkey].name}::{pid}", "decision": "suggest", "suggested_value": value,
                       "suggest_kind": kind, "note": note}], data, dirs, "tester")

    def run():
        return suggestions.collect(list(b.values()), backend)
    return b, data, dirs, suggest, run


def cells(fix):
    return {(c["row_id"], x["field"]): x for c in fix["corrections"] for x in c["cells"]}


def test_value_suggestion_keeps_original_refs_and_confidence(env):
    b, _, _, suggest, run = env
    suggest("fix_a", "10|Name", "Atlantic Star II", note="class register spelling")
    fix, reports = run()
    c = cells(fix)[("10", "Name")]
    assert c["new_value"] == "Atlantic Star II" and c["confidence"] == "G"
    assert c["refs"] == [{"url": "http://ship/10"}] and "preserve_ref" not in c
    assert "tester" in c["note"] and "class register spelling" in c["note"]
    assert fix["corrections"][0]["_live_row"] == 3          # row_id 10 is live sheet row 3
    assert not reports


def test_cosmetic_preserves_ref(env):
    _, _, _, suggest, run = env
    suggest("fix_a", "10|Status", "Active", kind="cosmetic")
    c = cells(run()[0])[("10", "Status")]
    assert c["preserve_ref"] is True and "refs" not in c


def test_cosmetic_on_a_cell_with_no_ref_is_gated(env):
    _, _, _, suggest, run = env
    suggest("data_fill", "5|Capacity", "174,000", kind="cosmetic")
    fix, reports = run()
    c = cells(fix)[("5", "Capacity")]
    assert "preserve_ref" not in c and c["refs"] == [{"url": "http://cap/5"}]
    assert [r[0] for r in reports] == ["cosmetic_gated"]


def test_other_names_suggestion_gates_the_added_element(env):
    _, _, _, suggest, run = env
    suggest("fix_b", "10|Other names", "Hull 1 (SHI)")
    c = cells(run()[0])[("10", "Other names")]
    assert c["append_ref"] is True and c["gate_value"] == "Hull 1 (SHI)"
    suggest("fix_b", "10|Other names", "A; B")               # two new elements: hand-build
    fix, reports = run()
    assert ("10", "Other names") not in cells(fix)
    assert reports[0][0] == "not_emitted"


def test_discovery_and_ref_lines_are_reported_not_emitted(env):
    b, data, dirs, _, run = env
    for p in data["proposals"].values():
        if p["kind"] in ("new_row", "ref"):
            store.decide([{"key": f"{p['batch']}::{p['id']}", "decision": "suggest",
                           "suggested_value": "x", "note": "n"}], data, dirs, "tester")
    fix, reports = run()
    assert fix["corrections"] == []
    assert sorted(r[1]["kind"] for r in reports) == ["new_row", "ref"]
    assert all(r[0] == "not_emitted" for r in reports)


def test_same_cell_in_two_batches_keeps_the_later(env):
    _, _, _, suggest, run = env
    suggest("fix_a", "10|Status", "in service")
    suggest("fix_b", "10|Status", "active (2026)")
    fix, reports = run()
    assert cells(fix)[("10", "Status")]["new_value"] == "active (2026)"
    assert [r[0] for r in reports] == ["duplicate"] and reports[0][1]["batch"] == "b1_fix"


def test_later_decision_or_hand_edit_supersedes(env):
    b, data, dirs, suggest, run = env
    suggest("fix_a", "10|Name", "Atlantic Star II")
    store.decide([{"key": f"{b['fix_a'].name}::10|Name", "decision": "accept"}], data, dirs, "tester")
    assert run()[0]["corrections"] == []
    suggest("fix_a", "10|Status", "in service")
    path = b["fix_a"] / "decisions.csv"                      # a hand edit of the csv
    path.write_text(store.plan_csv(path, {"10|Status": "accept"}), encoding="utf-8")
    fix, reports = run()
    assert fix["corrections"] == [] and [r[0] for r in reports] == ["superseded"]


def test_main_writes_only_out(env, tmp_path, capsys):
    b, _, _, suggest, _ = env
    suggest("fix_a", "10|Name", "Atlantic Star II")
    before = {p: p.read_bytes() for d in b.values() for p in d.iterdir()}
    out = tmp_path / "sugg.json"
    assert suggestions.main(["--batches", *map(str, b.values()), "--backend", str(tmp_path / "backend.csv"),
                             "--out", str(out)]) == 0
    assert {p: p.read_bytes() for d in b.values() for p in d.iterdir()} == before
    fix = json.loads(out.read_text())
    assert fix["corrections"][0]["cells"][0]["field"] == "Name"
    assert "other_names.py --batch" in capsys.readouterr().out
