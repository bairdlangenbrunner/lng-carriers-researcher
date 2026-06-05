# Controlled vocabularies — backend data columns

Several backend data columns use a tight, controlled set of values. `build_workbook.py`
writes proposed values **verbatim** (there is no normalization layer for these), so any
[ref]-fill / data-fill / discovery proposal for these columns **must use one of the exact
canonical values below** (case-sensitive). A novel value is not auto-written — it is flagged
to `QA_review` for a human vocab decision (Data-fill SOP §8).

The lists are derived from the live backend's existing values; counts are indicative
(2026-06-03). When a genuinely new value class appears, add it here in the same change set
and note it in the batch `notes.md`.

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
- **Price currency** — `$m` (most rows) or `USD`. A proposed Price must carry a currency;
  follow whatever the cited source states (flag if a source gives KRW/another currency that
  would need conversion before entry).

The canonical mirror used by `build_workbook.py`'s data-fill validator is `_DATA_FILL_VOCAB`
in `scripts/build_workbook.py` — keep the two in sync.
