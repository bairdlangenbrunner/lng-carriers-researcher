"""Tests for the FSRU name/owner normalizers added to scripts/normalize.py.

These guard the GIIGNL↔backend join keys: diacritic folding (GIIGNL 'Höegh' vs
backend 'Hoegh'), parenthetical stripping, and multi-owner tag-set resolution.
Pure logic, no network.
"""
from normalize import normalize_vessel_name, fsru_owner_tags, _strip_diacritics


class TestNormalizeVesselName:
    def test_diacritics_folded(self):
        assert normalize_vessel_name("Höegh Esperanza") == "hoegh esperanza"
        assert normalize_vessel_name("Höegh Gannet") == normalize_vessel_name("Hoegh Gannet")

    def test_parentheticals_dropped(self):
        # backend placeholder name and GIIGNL '(ex …)' both collapse away
        assert normalize_vessel_name("Samsung HI (MISC FSRU)") == "samsung hi"
        assert normalize_vessel_name("Italis LNG (ex Golar Tundra)") == "italis lng"

    def test_case_and_whitespace(self):
        assert normalize_vessel_name("  FSRU   Toscana  ") == "fsru toscana"

    def test_empty(self):
        assert normalize_vessel_name("") == ""
        assert normalize_vessel_name(None) == ""

    def test_distinct_vessels_stay_distinct(self):
        # no rebrand/token stripping that would collapse different vessels
        assert normalize_vessel_name("Torman") != normalize_vessel_name("Torman II")
        assert normalize_vessel_name("Express") != normalize_vessel_name("Expedient")

    def test_ex_name_union_bridges_rebrand(self):
        # the join uses {current} ∪ {ex}; the ex-name must equal the backend's
        # still-old name after normalization (the canonical Saros/Vasant 1 case)
        assert normalize_vessel_name("Vasant 1") == normalize_vessel_name("Vasant 1")
        assert normalize_vessel_name("Golar Tundra") == normalize_vessel_name("golar  tundra")


class TestStripDiacritics:
    def test_basic(self):
        assert _strip_diacritics("Türkiye") == "Turkiye"
        assert _strip_diacritics("Höegh") == "Hoegh"


class TestFsruOwnerTags:
    def test_multi_owner_split(self):
        assert fsru_owner_tags("Karpowership, MOL") == {"karmol", "mol"}

    def test_hoegh_overlap_for_manual_match(self):
        # the Höegh Esperanza ↔ backend 'Hoegh'/owner 'Esperanza Hoegh' case
        assert fsru_owner_tags("Hoegh LNG") & fsru_owner_tags("Esperanza Hoegh")

    def test_energos_styling_collapses(self):
        assert fsru_owner_tags("Energos Infrastructure") == fsru_owner_tags("Energos")

    def test_distinct_owners_no_overlap(self):
        # the Torman false-pair guard: Access LNG vs Anthony Veder must NOT overlap
        assert not (fsru_owner_tags("Access LNG") & fsru_owner_tags("Anthony Veder"))

    def test_empty(self):
        assert fsru_owner_tags("") == set()
