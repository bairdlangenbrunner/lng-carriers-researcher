"""Tests for scripts/fsru_reconcile.py — the GIIGNL↔backend FSRU bucketing.

The load-bearing guarantees: a name/ex-name hit on an FSRU-typed backend row is
'matched'; a hit on a non-FSRU row is 'reclassify' (a typing finding, not a gap);
a GIIGNL FSRU absent from the backend is a 'candidate' (small ones flagged); and a
no-name suggestion requires owner overlap (so coincidental capacity matches don't
mis-pair distinct vessels). Pure logic, no network.
"""
import fsru_reconcile as fr


def _be(sheet_row, name, vtype, cap, owner="", builder="", delivery=None):
    return {"sheet_row": sheet_row, "name": name,
            "norm": fr.normalize_vessel_name(name),
            "imo": "", "capacity": cap, "builder": builder, "owner": owner,
            "delivery_year": delivery, "vessel_type": vtype}


def _g(name, storage, ex=None, owner="", builder="", built=None, ccs="Membrane"):
    return {"vessel_name": name, "ex_names": ex or [], "storage_m3": storage,
            "ccs": ccs, "sendout_mtpa": None, "vessel_owner": owner,
            "builder": builder, "built_year": built,
            "location_raw": "", "location_status": "deployed"}


class TestCapAgree:
    def test_within_abs_band(self):
        assert fr.cap_agree(170000, 170200) is True       # 200 m³ apart

    def test_within_frac_band(self):
        assert fr.cap_agree(135000, 136967) is True       # ~1.5%

    def test_outside(self):
        assert fr.cap_agree(125000, 170000) is False

    def test_missing(self):
        assert fr.cap_agree(None, 170000) is None


class TestBuckets:
    def _run(self, fleet_vessels, backend, orderbook=None):
        fleet = {"edition_year": 2025, "vessels": fleet_vessels,
                 "orderbook": orderbook or []}
        return fr.reconcile(fleet, backend)

    def test_name_hit_on_fsru_is_matched(self):
        be = [_be(100, "PGN FSRU Lampung", "FSRU", 170000)]
        r = self._run([_g("PGN FSRU Lampung", 170000)], be)
        assert r["summary"]["matched"] == 1 and r["summary"]["reclassify"] == 0

    def test_ex_name_hit_matches_backend_old_name(self):
        # GIIGNL 'Saros (ex Vasant 1)' must match backend still-named 'Vasant 1'
        be = [_be(1089, "Vasant 1", "FSRU", 180000)]
        r = self._run([_g("Saros", 180000, ex=["Vasant 1"])], be)
        assert r["summary"]["matched"] == 1
        assert r["matched"][0]["backend"]["sheet_row"] == 1089

    def test_name_hit_on_nonfsru_is_reclassify(self):
        be = [_be(376, "Alexandroupolis", "conventional", 153000)]
        r = self._run([_g("Alexandroupolis", 153000, ex=["Gaslog Chelsea"])], be)
        assert r["summary"]["reclassify"] == 1 and r["summary"]["matched"] == 0

    def test_absent_small_unit_is_flagged_candidate(self):
        r = self._run([_g("EDN 1", 14000, ccs="Other")], [])
        assert r["summary"]["candidates"] == 1
        assert r["candidates"][0]["small_scale_review"] is True

    def test_absent_fullsize_is_unflagged_candidate(self):
        r = self._run([_g("Some New FSRU", 170000, ccs="Membrane")], [])
        assert r["candidates"][0]["small_scale_review"] is False

    def test_manual_requires_owner_overlap(self):
        # capacity + delivery coincide but owners differ -> NOT a suggestion;
        # falls through to candidate (the Torman/Coral Encanto false-pair guard)
        be = [_be(503, "Coral Encanto", "small-scale", 30000,
                  owner="Anthony Veder", delivery=2019)]
        r = self._run([_g("Torman", 28000, owner="Access LNG", built=2020, ccs="Other")], be)
        assert r["summary"]["manual"] == 0
        assert r["summary"]["candidates"] == 1

    def test_manual_match_on_owner_overlap(self):
        # the Höegh Esperanza ↔ backend 'Hoegh' name-defect case
        be = [_be(676, "Hoegh", "FSRU", 170000, owner="Esperanza Hoegh", delivery=2018)]
        r = self._run([_g("Höegh Esperanza", 170000, owner="Hoegh LNG", built=2018)], be)
        assert r["summary"]["manual"] == 1
        assert r["manual"][0]["suggested_backend"]["sheet_row"] == 676

    def test_backend_only_fsru_reported(self):
        be = [_be(1201, "Samsung HI (MISC FSRU)", "FSRU", 170000)]
        r = self._run([], be)
        assert r["summary"]["backend_only"] == 1
