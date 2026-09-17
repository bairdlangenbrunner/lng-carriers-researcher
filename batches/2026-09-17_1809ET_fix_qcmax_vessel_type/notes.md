# 2026-09-17 18:09 ET — fix: Vessel type `qc-max` (sep-17-pass batch 11)

Baird added `qc-max` as a Vessel type value on 2026-09-17 (it is in the sheet's Vessel type
dropdown, lowercase like `q-flex` / `q-max`). IGU World LNG Report 2026 types the 24 × 271,000 cbm
QatarEnergy ships `QC-max`; batch 8 (`1654ET_fix_igu2026_sourced`) had left their blank Vessel
type unproposed in `manual_review.json` because the vocabulary had no such value. This batch
proposes them.

- 24 cells / 24 rows, all `Vessel type` blank → `qc-max`, all G / accept. Live sheet rows (pull of
  2026-09-17 ~18:00 ET): 1070–1074, 1119–1129, 1171–1173, 1176–1178, 1201–1202.
- Ref: the IGU 2026 report PDF alone — same interim sole-source rule as batch 8 (IG §5.4); the
  open "second ref at ref-validation?" decision covers these cells too. 0 refs dropped by the
  §3.8c gate.
- `fix.json` was built from batch 7's `igu_reconcile.json` (IGU page + IMO in each cell note).
- Vocabulary: `qc-max` added to `scripts/lookups.py` and `data/controlled_vocab.md`. Batch 8's
  `manual_review.json` drops the 24 entries (32 → 8) and its generator now skips `QC-max`.
- Apply: any order relative to the other batches (no other batch touches Vessel type on these
  rows); `apply_rows.csv` was built from the live backend, so after batches 1 / 4 / 8 / 10 have
  landed use `apply_patch.csv`.
