# Fix batch — former Names → `Other names` (2026-09-17, sep-17-pass 10)

Retroactive application of the new former-name rule to the Name changes the sep-17-pass already
proposes (batches 1, 2 and 8). `fix` mode, QC §4 / Apply SOP. All row numbers are **live sheet
rows** (fresh pull 2026-09-17, 1,220 rows); `fix.json` and `apply_patch.csv` key on the column-A
`row_id`.

## The rule (Baird, 2026-09-17)

> whenever you propose a different name for a ship, propose the former name as an addition to the
> "Other names" column.

Codified as [ref]-Fill SOP **§4.16** (RF rev 23). *Addition* means append: the former Name joins
whatever is already in `Other names` with `"; "`, and its ref joins the existing `Other names [ref]`
with `", "` — nothing in either cell is replaced (row 114: `LNG Pioneer` → `LNG Pioneer; Pioneer
Spirit`; row 124: `Condor LNG` → `Condor LNG; CCH LNG`).

## What is proposed — 160 cells, 160 rows: 124 `G` accept, 1 `Y` accept, 35 `Y` hold

*Rebuilt 2026-09-18* with the IGU `(ex-…)` names (RF §4.17, below) and builder-tagged hulls; the
first build's 131 cells are unchanged except where an ex-name or a yard tag was added. The
breakdown below is the first build's; the §4.17 section covers what the rebuild added. Row 190
(Alto Acrux) is now `Y` / accept because its Name line was accepted in the review app (linked pair).

| source batch | Name changes | proposed here | skipped |
|---|---|---|---|
| 1 `0421ET_fix_delivery_rollforward` | 116 | 109 | 7 |
| 2 `0458ET_fix_delivery_confirmed` | 1 | 1 | 0 |
| 8 `1654ET_fix_igu2026_sourced` | 33 | 21 | 12 |

- **95 `G` / accept** — a ref passed the gate on the former name *and* the Name line is accepted:
  - real renames backed by the IGU 2026 PDF, which prints them as `(ex-…)`: rows 21 Puteri Intan,
    73 Metagas Everest, 91 LNG River Orashi, 114 Pioneer Spirit, 167 Methane Heather Sally,
    364 Golar Tundra, 563 SCF La Perouse;
  - real renames backed by shipvault only (looked up by IMO; its unit record lists former names):
    rows 62 Seapeak Hispania, 69 Energy Frontier (page only), 70 Golar Arctic, 365 Kool Baltic;
  - 84 hull placeholders (`Hull 2541 (Hanwha)` …) whose shipvault unit record carries the hull
    number — rows 838–1058, see `decisions.csv`.
- **14 `Y` / hold — Name accepted, but no ref on hand prints the former name** (blank ref proposed;
  every filled `Other names` cell in the backend has a ref, so these wait for one): rows 57 East
  Energy, 124 CCH LNG, 144 Stena Blue Sky, 190 Alto Acrux, 742 North Mountain (real renames — worth
  a follow-up ref search); 827, 909, 1031, 1032, 1034, 1035 (hull placeholders); 935, 1008, 1080
  (`Dalian No 1 G175K-N`).
- **15 `Y` / hold — Name held, no ref**: rows 11, 20, 29, 39 (Karadeniz restylings); 887, 988–991,
  1000, 1039 (hulls); 1007, 1012, 1079 (Dalian); 1014 Gdansk FSRU.
- **7 `Y` / hold — a shipvault ref passed, but the Name line itself is held**: rows 881, 944, 945,
  948, 961, 969, 970. They flip to accept the moment their Name line does.

**An `Other names` line is never more permissive than its Name line** — decide them together. If
a Name change is rejected, reject its line here too (the "former" name is then still the name).
Checked: no line here is `accept` where its Name line is not.

## Not proposed (19 Name changes, my judgement calls — overrule with `--include <row_id>`)

- **Spelling / truncation corrections** — the old string was never a name the ship carried:
  rows 912, 914, 915, 916, 780, 781 (`Greenenergy` → `Greenergy`; 915 and 916 are proposed by both
  batch 1 and batch 8), 929 (`Alexey` → `Aleksey Kosygin`), 1013 (`Elisa Halycon` → `Halcyon`),
  88 (`Hongkong` → `Hongkong Energy`), 294 (`BW ENN Crystal` → `… Crystal Sky`), 446 (`Cesi` →
  `Cesi Lianyungang`), 461 (`Hoegh` → `Hoegh Esperanza`), 584 (`Energy Endeavor` → `Endeavour`),
  624 (`Vivirt` → `Vivit City LNG`), 785 (`Al-Kheesha` → `Al Kheesah`), 790 (`Clean Srocco` →
  `Clean Sirocco`).
- **A name that belongs to another vessel** — row 942 `Puteri Sarawak` → `Puteri Perlis`: the
  backend had the wrong ship's name on the row; `Puteri Sarawak` is what batch 1 names row 884.
- Row 365 `Kool Baltic` → `Cool Baltic` trips the spelling test but is a real former name
  (shipvault lists it), so it was forced in with `--include 729`.

## Refs

Candidates for each former name: the refs of the proposed Name cell, the row's existing
`Name [ref]`, then — for real names with nothing passing — a shipvault lookup by IMO. Each went
through the §3.8c gate on the **former name** (`gate_value`), not on the joined cell. Three guards
beyond the stock gate, all in `other_names.py` (`other_names.json` logs every verdict):

- a multi-word name passing only as *scattered tokens* on a long document is rejected (the IGU PDF
  contains "Energy" and "Frontier" somewhere) — unless the IGU coordinate extraction
  (`work/igu_fleet_2026.json`) prints the former name in that IMO's own name cell, which is how
  the line-wrapped `(ex-Pioneer Spirit)` and `(ex-Metagas Everest)` were kept;
- a former name contained in the new name is not gated at all (`LNGT Americas` "passed" on a page
  that says `Karadeniz LNGT Americas`);
- vesselfinder is never asked (IP ban, 2026-09-17), marinetraffic is not asked about hull
  placeholders, and the IGU landing page is ungateable.

Build (2026-09-18 rebuild): 0 refs dropped by the gate, zero formula errors. 136 of the 160 cells carry a ref.

## Apply — `apply_patch.csv` only, after batches 1, 2 and 8

`apply_rows.csv` holds full rows built from the *live* backend, so pasting it would revert the
Name (and everything else) batches 1, 2 and 8 change on the same rows. Use the by-name patch
(`tools/apply_patch.gs`; one line per accepted value + one per `[ref]` cell — re-run
`apply_batch.py` after editing `decisions.csv` to pick up released holds), which touches only
`Other names` and `Other names [ref]`. No other pending batch proposes either column (checked across all
`apply_patch.csv` files), and `conflicts.csv` is empty.

## Tooling added with this batch

- `scripts/other_names.py` — `--batch <dir|fix.json>` patches a fix batch in place before
  `build_workbook.py` (idempotent; stamps each Name cell `former_name`); `--collect <dirs> --out`
  builds a standalone batch like this one. `--include`, `--no-gate`, `--dry-run`.
- `build_workbook.py` fix mode: `append_ref` + `gate_value` cell kind; warns when a Name change
  was never checked for a former name. `apply_batch.py`: `append_ref` cells append to the paired
  `[ref]` instead of replacing it.
- `tests/test_other_names.py` (11 tests).
- Docs: RF §4.16 (rev 23), QC §4, `docs/pointers.md`, `CLAUDE.md`.

## IGU 2026 `(ex-…)` names → `Other names` (RF §4.17, Baird 2026-09-18)

> when there's an "ex-", I want that old name to be included in other names.

`other_names.py --igu-ex 2026` reads every `(ex-…)` the IGU 2026 PDF prints (from
`work/igu_fleet_2026.json`), joins it to the backend by IMO, and gates the IGU PDF on the verbatim
ex text. 38 cells carry one:

- **appended to a §4.16 line on the same row (9)**, so it stays coupled to that Name line: rows 11
  `Northwest Sanderling`, 20 `Northwest Stormpetrel`, 29 `LNG Portovenere`, 39 `LNG Lerici`, 124
  `Methane Lydon Volney`, 365 `SCF Melampus`, 856 `QatarGas LNG 37`, 910 `QatarGas LNG 36`, 911
  `QatarGas LNG 52`;
- **a cell of their own (29, all `G`)**: rows 14 `Northwest Shearwater`, 18 `Dwiputra`, 131
  `Provalys`, 367 `SCF Mitre`, 555 `SCF Barents`, and 24 rows where IGU's ex-name is a bare hull
  number (rows 687–821, e.g. row 720 `Hull 3341 (HDHHI)`).

**Hull numbers always name their yard** (Baird 2026-09-18). A hull written into `Other names`,
whether an IGU ex-name or a former hull-placeholder Name, takes the QC §2 form `Hull NNNN (Tag)`.
The tag is the one the backend already uses for that builder (SHI, Hanwha, HDHHI, HSHI, Zvezda).
**`Hudong` and `Jiangnan` are new tags**, because the backend has no tagged Hudong or Jiangnan
placeholder yet. Rows 910/911 and the other Hudong former Names therefore read `Hull H1800A (Hudong)`.
`Hull YZJ2022-1475` already carries its yard and is left alone. The gate still runs on the
untagged text the source prints.

Not proposed; the reviewer should check these (`other_names.json` → `skipped`):
- row 711: IGU prints ex-`Jiangnan H2700`, but the row's hull is 2702;
- row 855: IGU prints ex-`2653`, but the row is `Hull 2563 (Hanwha)` (a typo on one side);
- row 910: IGU's parenthetical hull `(2563)` on Mizhem does not match the row's `H1800A`, which is
  noted on the cell;
- rows 21, 73, 91, 114, 167, 364, 563: the ex-name is still the row's current Name, and batch 8
  renames each row, which carries it as its §4.16 former name;
- IMOs not in the backend: discovery leads, not Other names.

## Update 2026-09-18 — row 721 (live row 11) `Other names`

Now `Karmol LNGT Powership Antarctica; Karadeniz LNGT Antarctica; Northwest Sanderling` (Baird's
ruling; the row's Name becomes `LNGT Antarctica` in batch `1654ET`). Refs, each gated on its own
name: lngindustry.com 2025-05-28 (the Karmol name) and the IGU 2026 PDF (`Karadeniz LNGT
Antarctica (ex-Northwest Sanderling)`). Was `Y` / hold with no ref for the former name; now `G`,
accepted. Rebuilt: 0 refs dropped, zero formula errors; 126 accept / 34 hold.

## Update 2026-09-21 — IGU names carried here where the databases do not back them (IG §5.4 rev 3)

Companion to the same-day update in batch `1654ET` (`name_lookup_overrides.py` there patches this
`fix.json`). `Other names` now carries IGU 2026's name on live rows 20 (`Karadeniz LNGT Americas`),
29 / 39 (`Karadeniz LNGT Powership Black Sea` / `Marmara` — G, also on marinetraffic.org; these
replace the `KLNGTP …` former-name entries, since those rows are no longer renamed), 62 (`Seapeak
Jupiter`), 73 (`Arctic Metagas`), 124 (`LNG Soars`), 365 (`Cool Baltic`), 624 (`Vivit City LNG`,
new line) and 909 (`Fath Al Khair`); live row 88 gains the demolition name `Ergy` (new line).
`Cool Baltic` and `Vivit City LNG` are probably IGU misspellings — Y, reject to leave them out.
Each ref is gated on its own name. Rebuilt: 0 refs dropped, zero formula errors; 126 accept / 36 hold.

Later the same day: live row 20's line accepted with its Name line (`KLNGTP Americas`); 127 accept / 35 hold.
