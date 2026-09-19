# Fix batch — hull numbers from IGU 2026 `Name (hull)` entries (2026-09-18, sep-17-pass 13)

`fix` mode, QC §4 / Apply SOP. Built by `scripts/igu_hulls.py` (RF §4.17, rev 24). Row numbers are
**live sheet rows** from the fresh pull on 2026-09-18. `fix.json` and `apply_patch.csv` key on the column-A `row_id`.

## The rule (Baird, 2026-09-18)

> "Al Sailiya (2641)" is the hull number for that ship … check for 2641 in that row and if it's
> not there, suggest it … make sure the hull numbers have an indication of the builder so it's
> clear where the hull is.

> if a ship used to be identified BY its hull number (like row 843, Hull 2541 (Hanwha)) … this
> hull number can be compared to the hull numbers in the IGU 2026 report when it is in the form
> "Name (hull)"

IGU 2026 prints a parenthetical hull on 63 names (`(2641)`, `(1790A)`, `(Hull 2583)`,
`(HSHI-8196)`, `(Jiangnan H2702)`). Rows are joined by IMO, and hull placeholders by hull
number plus builder family. Each join is checked against the yard. Hanwha and SHI hull numbers
overlap, so `Hull 2583 (Hanwha)` is **not** `North Way (Hull 2583)`, which Samsung built.

## What is proposed — 41 cells, 41 rows, all `G`, all accept

- **13 blank `Hull number` cells filled**, each citing the IGU 2026 PDF (sole-source ruling, IG §5.4),
  gated on the hull as IGU prints it: 791 Gail Sagar `Hull 8197 (HSHI)`, 792 HL Alyssa Warner
  `Hull 2607 (SHI)`, 793 HL Edward Austin `Hull 2608 (SHI)`, 795 HL Sea Eagle `Hull 2609 (SHI)`,
  798 Lebrethah `Hull 2548 (Hanwha)`, 801 Mareekh `Hull 3380 (HDHHI)`, 802 Mesaieed
  `Hull 3381 (HDHHI)`, 807 North Valley `Hull 2526 (Hanwha)`, 810 Orion Sirius `Hull 2595 (SHI)`,
  817 Umm Swayyah `Hull 2547 (Hanwha)`, 819 Venture Creole `Hull 2531 (Hanwha)`, 820 Wadi Al Syl
  `Hull 3382 (HDHHI)`, 822 Woodside Jirrubakura `Hull 2534 (Hanwha)`.
- **28 untagged hulls restyled with their yard tag** (`preserve_ref`: value only, `[ref]` kept,
  no gate — the hull number itself is unchanged and IGU confirms it). Examples: 685
  `Hull 1790A` → `Hull 1790A (Hudong)`, 693 `Hull 2473` → `Hull 2473 (SHI)`, 725 `Hull 8196` →
  `Hull 8196 (HSHI)`, 749/750 `Hull H2701`/`H2702` → `(Jiangnan)`. Full list in `decisions.csv`.
  **`Hudong` and `Jiangnan` are new tags**, because the backend had no tagged placeholder for either yard.

## Names for hull-placeholder rows (request E): nothing new

IGU gives a `Name (hull)` for seven rows that are still named by their hull, and
an earlier batch already proposes the same name on every one:
843 Venture Pelican (2541), 846 Al Kharrarah (2549), 870 Qtaifan (2640), 890 Al Zuwair (3395),
900 Puteri Selangor (8188) and 901 Puteri Terengganu (8189) in batch 1 (`0421ET`), and 909 Fath Al
Khair (1799A) in batch 8 (`1654ET`). Their former hull placeholders go to `Other names` through batch 10.
No IGU hull points at an IMO that already sits on a different row (the duplicate check).

## Flagged, not proposed (in `fix.json` → `flagged`)

- **Samho vs Ulsan.** IGU names Hyundai Samho for four rows the backend has as HD Hyundai Heavy
  Industries: 733 Elisa Ardea (`Hyundai Samho 8049`), 775 Zoe Knutsen (8102, already
  `Hull 8102 (HDHHI)`), 796 Ignacy Jan Paderewski (8180) and 940 Josef Pilsudski (8179). 8xxx hull
  numbers are Samho's series. This is probably a Shipbuilder correction, and the hull tag
  follows the Shipbuilder. The 8xxx rows restyled here as `(HDHHI)` (721 Nantes Knutsen 8100, 723
  Woodside Scarlet Ibis 8170, 724 Marvel Dove 8173) are the same question: IGU prints only
  `HD Hyundai`, which covers both yards, so the tag follows the backend's builder.
- **941 Puteri Perak (2632).** IGU says Samsung Heavy Industries, but the backend says HD Hyundai Samho.
- **936 HL Puffin (2610).** The on-order data-fill batch (`0511ET`) already proposes the same `Hull 2610 (SHI)`
  with shipvault refs, so it is not proposed twice.

## Not in this batch — offered

69 other SHI rows carry an untagged `Hull NNNN`, and there are more untagged Hudong rows. IGU does not print their
hull, so they are outside this batch's scope. The same `preserve_ref` restyle can cover the whole
column if wanted.

## Apply

Patch path (`tools/apply_patch.gs` on `apply_patch.csv`, `OVERWRITE_NONBLANK=true` for the
restyles), then `python scripts/verify_apply.py --batch batches/2026-09-18_2005ET_fix_igu2026_hulls --pull`.
No other pending batch proposes `Hull number` on these rows. Build: 0 refs dropped by the gate,
zero formula errors.
