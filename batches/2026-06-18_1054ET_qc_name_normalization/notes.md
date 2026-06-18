# QC fix batch — pre-release Name normalization + orphan-ref cleanup

**Date:** 2026-06-18 1054 ET
**Mode:** `fix` (qc_release.md rev 1)
**Trigger:** pre-release QC pass of the whole backend.

## Scan result

Fresh pull (`pull_backend.py`, 1,479 data rows) + whole-backend `qc_backend.py`.
**No corruption** — zero `column-offset` / `misplaced-vocab` / `url-in-value` /
`bad-shape` findings. 31 findings total, all LOW/MED and mechanical:

| Check | Count | Severity |
|---|---|---|
| `name-builder-drift` | 28 | LOW |
| `name-ordinal-gap` | 1 | LOW |
| `orphan-ref` (Rule F) | 2 | MED |

This batch corrects all 31 (the drift groups collapse to 14 renamed rows once the
already-correct sibling rows are excluded).

## Canonical forms (confirmed with user 2026-06-18)

| Yard | Winning label | Rule | Rows renamed (row_id) |
|---|---|---|---|
| hudong-zhonghua | `Hudong-Zhonghua` (drop "Shanghai") | B1 | 1196–1200 |
| hyundai-samho | `HD Hyundai Samho` (drop "Yeongam", drop "HI") | B1 | 1189, 1193, 1194, 1195, 1212, 1213 |
| hyundai-ulsan | `HD Hyundai HI (HHI) Ulsan` (keep "(HHI)") | B1 | 1214, 1215 |

Rows already on the winning label (e.g. the 11 `Hudong-Zhonghua` rows, the four
`HD Hyundai HI (HHI) Ulsan (NYK, Ocean Yield N)` rows) were left untouched.

## Rename table

| row_id | sheet row | old Name | new Name |
|---|---|---|---|
| 1196 | 1191 | Hudong-Zhonghua Shanghai (MISC 1) | Hudong-Zhonghua (MISC 1) |
| 1197 | 1192 | Hudong-Zhonghua Shanghai (MISC 2) | Hudong-Zhonghua (MISC 2) |
| 1198 | 1193 | Hudong-Zhonghua Shanghai (MISC 3) | Hudong-Zhonghua (MISC 3) |
| 1199 | 1194 | Hudong-Zhonghua Shanghai (MISC 4) | Hudong-Zhonghua (MISC 4) |
| 1200 | 1195 | Hudong-Zhonghua Shanghai (MISC 5) | Hudong-Zhonghua (MISC 5) |
| 1189 | 1184 | HD Hyundai Samho Yeongam (Hyundai Glovis 1) | HD Hyundai Samho (Hyundai Glovis 1) |
| 1193 | 1188 | Hyundai Samho HI (Capital Clean ECC 1) | HD Hyundai Samho (Capital Clean ECC 1) |
| 1194 | 1189 | Hyundai Samho HI (Capital Clean ECC 2) | HD Hyundai Samho (Capital Clean ECC 2) |
| 1195 | 1190 | Hyundai Samho HI (Capital Clean ECC 3) | HD Hyundai Samho (Capital Clean ECC 3) |
| 1212 | 1207 | HD Hyundai Samho Yeongam (BW LNG 1) | HD Hyundai Samho (BW LNG 1) |
| 1213 | 1208 | HD Hyundai Samho Yeongam (BW LNG 2) | HD Hyundai Samho (BW LNG 2) |
| 1214 | 1209 | HD Hyundai HI Ulsan (Hayfin 1) | HD Hyundai HI (HHI) Ulsan (Hayfin 1) |
| 1215 | 1210 | HD Hyundai HI Ulsan (Hayfin 2) | HD Hyundai HI (HHI) Ulsan (Hayfin 2) |
| 1219 | 1214 | Hanwha Ocean (Knutsen) | Hanwha Ocean (Knutsen OAS 2) |

Row 1219 fixes both the `name-ordinal-gap` (sibling row_id 1205 is
`Hanwha Ocean (Knutsen OAS 1)`, so this is `2`) and the owner form (B2: canonical
`Knutsen OAS`, not bare `Knutsen`).

## Ref handling

- **All 14 Name edits use `preserve_ref: true`** — cosmetic/derived placeholder
  rewrites. The paired Name `[ref]` documents the underlying order (builder / owner /
  contract), not the literal synthetic string, so the §3.8c gate is correctly skipped
  and each ref is left byte-for-byte untouched (14 `PRESERVED` lines in QA_review).
- **2 orphan-ref drops** (Rule F — `[ref]` populated, paired value blank):
  - row_id 1041 (`Singapore FSRU`, sheet 1036): blank IMO, stray blanket IGU citation
    on the IMO `[ref]` → dropped. (FSRU on order, no IMO assigned.)
  - row_id 1206 (`Samsung HI Geoje (MISC FSRU)`, sheet 1201): blank Cargo type, three
    blanket citations on the Cargo type `[ref]` → dropped.
  - 4 `REMOVED` lines in QA_review. These were intentional `drop_refs`, not gate
    failures.

## Verification

- `recalc.py` → **zero formula errors**.
- Workbook spot-check: 16 corrected full rows, Names as in the table above, both
  orphan `[ref]` cells now blank, preserved Name `[ref]`s intact, QA_review =
  14 PRESERVED + 4 REMOVED.
- Release gate (per QC §5) runs after apply: land via the Apply SOP, then re-pull +
  re-run `qc_backend.py` — expect `name-builder-drift` / `name-ordinal-gap` /
  `orphan-ref` all at zero.

## Notes / advisories (not in this batch)

- `qc_backend.py` coverage warning: 108 owner tags absent from
  `shipowner_facts.csv`, so the `lookup-mismatch` (owner-country) check could not run
  for them. Not a release blocker; worth a `seed_lookups.py` refresh later.

## Tooling

No script changes this batch.
