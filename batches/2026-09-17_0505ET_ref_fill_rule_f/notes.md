# Rule-F [ref]-fill — whole backend (2026-09-17, sep-17-pass)

Scope: every cell in the fresh 2026-09-17 pull where a data value is filled but the paired
`[ref]` is blank (RF §4.13 Rule F). 19 such cells: Vessel type 10, Capacity 5, Hull number 3,
Shipowner country/area 1. Sourcing was mechanical (shipvault unit record for the row's IMO,
then refs already cited elsewhere on the row), every URL through the §3.8c value↔ref gate.

## Proposed (8 cells, all Y — single-source shipvault)

| live row | row_id | cell | value | ref |
|---|---|---|---|---|
| 6 | 415 | Capacity [ref] | 126750 | shipvault.com/ships/73086 |
| 7 | 663 | Capacity [ref] | 126750 | shipvault.com/ships/73085 |
| 61 | 969 | Capacity [ref] | 135000 | shipvault.com/ships/113754 |
| 487 | 1044 | Capacity [ref] | 174000 | shipvault.com/ships/373877 |
| 488 | 1045 | Capacity [ref] | 174000 | shipvault.com/ships/373876 |
| 771 | 121 | Hull number [ref] | Hull 2651 (SHI) | shipvault.com/ships/450944 |
| 775 | 226 | Hull number [ref] | Hull 8102 (HDHHI) | shipvault.com/ships/448545 |
| 776 | 230 | Hull number [ref] | Hull 8181 (HDHHI) | shipvault.com/ships/461187 |

Y, not G: one source each. The workbook sheet holds only these 8 rows (built against a
filtered copy of the pull so the sheet is reviewable); `citations.json` is keyed by row_id.

## Negative results (11 cells, still Rule-F orphans) — `unfilled_negative_results.json`

- **Vessel type = `conventional`, 10 cells** (live rows 61, 487, 488, 994, 1118, 1172,
  1182–1185). No page says "conventional" — it is a tracker classification inferred from
  capacity, not a sourced fact, so the hard corroboration gate can never pass it. Needs a
  rule decision (same open question as the cargo/vessel-type derivation rule): either allow
  a capacity-derived Vessel type to stand on the Capacity ref, or leave these unreffed.
- **Shipowner country/area = `China`, live row 652** — the only passing refs were the IGU
  report landing page and a shipyards.gr yard page, which mention China generically, not the
  owner's domicile. Dropped as too weak; needs an owner profile page.

## Gate

67 URL checks logged in `citations.json` → `qa_log`. Recalc: zero formula errors.
