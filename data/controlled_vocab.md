# Controlled vocabularies — backend data columns

Several backend data columns use a tight, controlled set of values. `build_workbook.py`
writes proposed values **verbatim** (there is no normalization layer for these), so any
[ref]-fill / data-fill / discovery proposal for these columns **must use one of the exact
canonical values below** (case-sensitive). A novel value is not auto-written — it is flagged
to `QA_review` for a human vocab decision (Data-fill SOP §8).

The lists are derived from the live backend's existing values; counts are indicative
(2026-06-03). When a genuinely new value class appears, add it here in the same change set
and note it in the batch `notes.md`.

## Status

| Value | ~count |
|---|---|
| `active` | 822 |
| `on order` | 364 |
| `proposed` | 34 |
| `scrapped` | 0 (added 2026-09-17) |

Definitions are in `docs/inclusion_criteria.md`. `scrapped` = sold for demolition / broken up; the
row stays (rows are never deleted) and needs a verified ref for the demolition sale. The §3.8c gate
reads `scrapped` as completed-sale wording ("sold for demolition / recycling / scrap", "beached",
"broken up", a tracker's `SCRAPPED`) — never as the bare status word alone.

## Cargo type

| Value | ~count |
|---|---|
| `membrane` | 644 |
| `spherical` | 110 |
| `self-supporting prismatic` | 5 |
| `type C` | 4 |

## Vessel type

| Value | ~count |
|---|---|
| `conventional` | 627 |
| `FSRU` | 49 |
| `q-flex` | 31 |
| `icebreaker` | 29 |
| `q-max` | 14 |
| `qc-max` | 0 (added 2026-09-17 — the 271,000 cbm QatarEnergy class, IGU 2026 `QC-max`; 24 rows proposed) |
| `FSU` | 10 |
| `Supporting` | 5 |
| `small-scale` | 4 |
| `mid-scale` | 4 |

## Propulsion type

| Value | ~count |
|---|---|
| `X-DF` | 368 |
| `DFDE` | 212 |
| `steam` | 211 |
| `ME-GA` | 119 |
| `ME-GI` | 98 |
| `SSD` | 48 |
| `steam reheat` | 12 |
| `STaGE` | 8 |
| `prismatic conventional DFDE` | 4 |
| `prismatic small-scale DFDE` | 1 |

## Units / currency

- **Capacity units** — only `cbm` is used. A proposed Capacity always pairs with `cbm`.
- **Price currency** — `USD`, with Price in **full US dollars** (`250000000`, never `250` + `$m`;
  Baird 2026-09-17). `$m` is gone: the legacy rows were converted by the price-USD fix
  batch (applied 2026-09-18) and it is no longer in the vocabulary. A proposed Price must carry a currency (flag if a
  source gives KRW/another currency that would need conversion before entry).

## Delivery delayed

- `yes`, or blank (RF §4.19, Baird 2026-09-21). `yes` = the Delivery year has moved later at least
  once; the former years sit in `Previous delivery year(s)` (oldest first, `"; "`-joined). Derived by
  `scripts/delivery_history.py`, never researched; stays `yes` after the vessel delivers.

The canonical machine-readable copy is `CONTROLLED_VOCAB` in `scripts/lookups.py` — imported by
`build_workbook.py`'s data-fill validator AND by `qc_backend.py` (which uses it to detect a
controlled value sitting in the wrong column). This markdown is the human mirror; keep the two in
sync.
