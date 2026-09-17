# 2026-09-17 18:10 ET — fix: Price in full US dollars (sep-17-pass batch 12)

Baird ruling 2026-09-17: **Price is always entered in full US dollars, Price currency `USD`** —
`250000000`, never `250` + `$m`. The backend carried both forms (29 rows `$m`, 17 rows `USD`).

- 58 cells / 29 rows: `Price` × 1,000,000 and `Price currency` `$m` → `USD`, all G / accept.
  Live sheet rows: 61, 487, 488, 946, 948, 950, 953, 954, 964, 965, 994, 1004, 1025–1028,
  1049–1054, 1059, 1075–1078, 1083, 1203. Fractions convert exactly (261.5 → 261500000,
  259.25 → 259250000, 266.1 → 266100000).
- A unit conversion, not a new value: every cell is `preserve_ref` (QC §4) — the existing
  `Price [ref]` stays and the §3.8c gate is skipped.
- No pending batch proposes a Price on these rows (data-fill is additive to blanks), so there is
  no ordering constraint; use `apply_patch.csv` once other batches have landed.
- After it is applied: drop `$m` from `CONTROLLED_VOCAB["Price currency"]` (`scripts/lookups.py`)
  and `data/controlled_vocab.md`, so `qc_backend.py` flags any `$m` that comes back.
- **Sheet display, not in this batch:** the pull shows existing USD prices as `2.53E+08` /
  `3.30E+08` — the Price column renders large numbers in scientific notation, and the formatted
  pull loses digits (252,500,000 reads back as 2.53E+08). Setting the column's number format to
  plain `0` in the sheet fixes it; until then `verify_apply.py` may report these cells as a
  mismatch on display form alone.
