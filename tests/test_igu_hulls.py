"""Tests for igu_hulls.py (RF §4.17): IGU `Name (hull)` parsing and the yard check."""
import igu_hulls


def test_igu_hull_parses_the_printed_forms():
    assert igu_hulls.igu_hull("Al Sailiya (2641)") == ("Al Sailiya", "2641", "2641")
    assert igu_hulls.igu_hull("North Way (Hull 2583)")[1] == "2583"
    assert igu_hulls.igu_hull("Kool Tiger (HSHI-8196)")[1] == "8196"
    assert igu_hulls.igu_hull("Al Reef (Jiangnan H2702)")[1] == "H2702"
    assert igu_hulls.igu_hull("Rex Tillerson (1790A)")[1] == "1790A"


def test_igu_hull_ignores_ex_names_and_dalian_series():
    assert igu_hulls.igu_hull("Shafallah (ex-QatarGas LNG 37 (2564))") == ("", "", "")
    assert igu_hulls.igu_hull("Sea Spirit (Dalian No 1 G175K-1)") == ("", "", "")
    assert igu_hulls.igu_hull("Aamira") == ("", "", "")


def test_yard_conflict():
    assert not igu_hulls.yard_conflict("Samsung Heavy Industries", "Samsung", "2583")
    assert igu_hulls.yard_conflict("Hanwha Ocean", "Samsung", "Hull 2583")          # overlapping series
    assert not igu_hulls.yard_conflict("HD Hyundai Heavy Industries", "HD Hyundai", "8100")  # ambiguous label
    assert igu_hulls.yard_conflict("HD Hyundai Heavy Industries", "HD Hyundai", "Hyundai Samho 8049")
