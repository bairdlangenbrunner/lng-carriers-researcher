# fix — unsourced Vessel type (2026-09-23 12:30 ET)

Baird 2026-09-23: every proposed value needs a ref that states it. A fresh pull found 16 live rows
with `Vessel type` = `conventional` and a blank or `inferred` `[ref]` — a class call no source made
(the same defect as the Sep-17 discovery batch's Dynagas / Tsakos rows, removed the same day).

**7 rows — ref added, value unchanged.** IGU 2026 prints `Conventional` in its Vessel Type column
for the IMO (`igu_refs.IguTable.check`), a sufficient sole source (IG §5.4); the report PDF replaces
the `inferred` ref. Live rows 838–842 (Atlantic Success, Hull 2393–2396 (SHI)), 944–945
(Mediterranean Success, Caribbean Success). G.

**9 rows — value cleared.** No page states `conventional` for these vessels, and neither IGU edition
lists the IMO. Checked: each row's existing refs and shipvault unit record, plus trade press found by
search (LNG Prime, Splash247, Riviera, Seatrade, Baird Maritime, PortNews, JoongAng, Offshore Energy,
BusinessKorea, SK Shipping). The only hits were "conventional marine fuels" and a Hellenic Shipping
News sidebar headline — neither is a vessel-type statement. The paired `[ref]` is already blank, so the
cells are `preserve_ref` (no gate to run). Live rows 487–488 (SK Serenity, SK Spica), 994 (Hull 8276
(Hanwha)), 1118 (Samsung HI (unknown shipowner 1)), 1169 (Hanwha Ocean (Knutsen)), 1179–1182
(Jiangnan (COSCO 1–4)).

Workbook built + recalced (zero errors, 0 refs dropped by the gate); `apply_batch.py`: 16 accept.
Apply by `apply_patch.csv` with `OVERWRITE_NONBLANK=true` (every line overwrites a non-blank cell).

## Applied — directed session write (2026-09-23, AP §2d)

Baird directed the write in-session ("go ahead and make sure this batch is reflected in the backend
directly now. edit the backend sheet."). Fresh pull → own plan (16 cells; the 7 `conventional`
values already in the sheet dropped as no-ops) → live old values checked (0 mismatches) → revert file
`directed_2026-09-23_revert.csv` → `gws-gem-write` `values.batchUpdate` (RAW) → re-pull: 16/16
landed; `verify_apply.py`: 23 landed, 0 mismatch, 0 missing. `push_log.jsonl` records each cell as
`claude session (directed)`; no `review_log.jsonl` entry was written.
`verify_apply.py` fixed in this batch: a cleared cell (blank accepted value) counted as `missing`;
it now counts as landed when the sheet cell is blank.
