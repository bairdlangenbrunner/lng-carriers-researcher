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

## What is proposed — 131 cells, 131 rows: 95 `G` accept, 36 `Y` hold

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

Build: 0 refs dropped by the gate, zero formula errors. 102 of the 131 cells carry a ref.

## Apply — `apply_patch.csv` only, after batches 1, 2 and 8

`apply_rows.csv` holds full rows built from the *live* backend, so pasting it would revert the
Name (and everything else) batches 1, 2 and 8 change on the same rows. Use the by-name patch
(`tools/apply_patch.gs`; 190 lines = the 95 accepted values + their 95 `[ref]` cells — re-run
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

## Lead, not acted on

IGU 2026 prints 55 `(ex-…)` names, and several are not in the backend's `Other names` (e.g.
`Northwest Stormpetrel` for row 20). A separate data-fill if wanted — this batch only carries
names the backend itself published.
