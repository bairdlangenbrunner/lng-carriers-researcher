"""Tests for scripts/normalize.py — canonical builder/owner/hull resolution.

These guard the cluster-matching layer (Rule E): when a new variant spelling
of a known yard or owner appears in a batch, it must still resolve to the same
canonical tag so clusters don't silently split or over-merge. Pure logic, no
network — see tests/README.md.
"""
import normalize


class TestNormalizeBuilder:
    def test_samsung_variants_collapse(self):
        for variant in ("Samsung Heavy Industries", "Samsung HI", "SHI Geoje"):
            assert normalize.normalize_builder(variant) == "samsung"

    def test_hanwha_ocean_absorbs_legacy_dsme_daewoo(self):
        # The yard formerly known as DSME / Daewoo is now Hanwha Ocean; all
        # three must cluster together or historical rows split from new ones.
        for variant in ("Hanwha Ocean", "DSME", "Daewoo Shipbuilding"):
            assert normalize.normalize_builder(variant) == "hanwha-ocean"

    def test_hyundai_family_stays_distinct(self):
        # The HD Hyundai yards are separate facilities — they must NOT merge.
        assert normalize.normalize_builder("HD Hyundai Samho") == "hyundai-samho"
        assert normalize.normalize_builder("Hyundai Mipo Dockyard") == "hyundai-mipo"
        assert normalize.normalize_builder("Hyundai Heavy Industries") == "hyundai-ulsan"

    def test_parenthetical_is_stripped(self):
        assert normalize.normalize_builder("Hudong-Zhonghua (Shanghai)") == "hudong-zhonghua"

    def test_unknown_builder_returns_lowercased_stripped(self):
        # Unknown yards still cluster against themselves, lowercased.
        assert normalize.normalize_builder("  Some New Yard  ") == "some new yard"

    def test_empty_input(self):
        assert normalize.normalize_builder("") == ""
        assert normalize.normalize_builder(None) == ""


class TestNormalizeOwner:
    def test_maran_gas_variants_and_parent(self):
        for variant in ("Maran Gas Maritime", "Maran Gas", "Angelicoussis Group"):
            assert normalize.normalize_owner(variant) == "maran-gas"

    def test_cosco_shipping_energy_tag(self):
        assert normalize.normalize_owner("COSCO Shipping Energy") == "cosco-shipping-energy"

    def test_unknown_owner_returns_lowercased(self):
        assert normalize.normalize_owner("Brand New Owner Ltd") == "brand new owner ltd"


class TestDisplayOwner:
    def test_cosco_stylized_short_form(self):
        # SOP §4.14: write the backend's settled short form, not the legal name.
        assert normalize.display_owner("COSCO Shipping Energy Transportation") == "COSCO"

    def test_unmapped_owner_passes_through_unchanged(self):
        # No settled stylization -> write exactly what was researched.
        assert normalize.display_owner("Knutsen OAS Shipping") == "Knutsen OAS Shipping"


class TestOwnerCountry:
    OWNER_IDX, COUNTRY_IDX = 0, 1

    def test_unambiguous_sibling_country_is_returned(self):
        backend = [
            ["Maran Gas Maritime", "Greece"],
            ["Maran Gas", "Greece"],
        ]
        assert normalize.owner_country(
            "Maran Gas Maritime", backend, self.OWNER_IDX, self.COUNTRY_IDX
        ) == "Greece"

    def test_ambiguous_siblings_return_none(self):
        # 'mol' appears with both Japan and Türkiye -> must be researched, never copied.
        backend = [
            ["Mitsui OSK Lines", "Japan"],
            ["MOL", "Türkiye"],
        ]
        assert normalize.owner_country(
            "MOL", backend, self.OWNER_IDX, self.COUNTRY_IDX
        ) is None

    def test_no_sibling_country_returns_none(self):
        backend = [["Maran Gas", ""]]
        assert normalize.owner_country(
            "Maran Gas", backend, self.OWNER_IDX, self.COUNTRY_IDX
        ) is None

    def test_without_backend_returns_none(self):
        assert normalize.owner_country("Maran Gas") is None


class TestNormalizeHull:
    def test_samsung_prefix_stripped(self):
        tag = normalize.normalize_builder("Samsung Heavy Industries")
        assert normalize.normalize_hull(tag, "Samsung HI Geoje 2775") == "2775"

    def test_hyundai_samho_letter_prefix_lowercased(self):
        assert normalize.normalize_hull("hyundai-samho", "Hyundai Samho H8340") == "h8340"

    def test_bare_number_unchanged(self):
        assert normalize.normalize_hull("samsung", "2775") == "2775"

    def test_empty_hull(self):
        assert normalize.normalize_hull("samsung", "") == ""
        assert normalize.normalize_hull("samsung", None) == ""
