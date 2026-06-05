# Fix batch — Name placeholder normalization (pre-release QC)

**Date:** 2026-06-05 1807 ET
**Mode:** `build_workbook.py --mode fix`
**Scope:** 18 rows, `Name` column only. Cosmetic/derived-name normalization ahead of the data release.
**Trigger:** Pre-release QC pass over the `Name` column (no row research; backend pull + cross-row consistency scan).

## What this fixes

The `Name` column uses two placeholder conventions for un-christened hulls:
`Hull NNNN (Yard)` when the hull number is known, and `Shipbuilder (Owner N)` when only
the owner is known. The `Shipbuilder (Owner N)` set had the **same yard spelled several
ways** across sibling rows, plus two owner-portion defects. All edits are to the placeholder
*string* only — the underlying builder/owner/order is unchanged.

### Builder-label drift (unify per yard)

| row_id | was | now |
|---|---|---|
| 1193–1195 | `Hyundai Samho HI (Capital Clean ECC 1–3)` | `HD Hyundai Samho Yeongam (Capital Clean ECC 1–3)` |
| 1196–1200 | `Hudong-Zhonghua Shanghai (MISC 1–5)` | `Hudong-Zhonghua (MISC 1–5)` |
| 1152–1155 | `HD Hyundai HI (HHI) Ulsan 3635–3638` | `HD Hyundai HI Ulsan 3635–3638` |
| 1201–1204 | `HD Hyundai HI (HHI) Ulsan (NYK, Ocean Yield 1–4)` | `HD Hyundai HI Ulsan (NYK, Ocean Yield 1–4)` |

- **Samho** → unified to `HD Hyundai Samho Yeongam` (the form its hull rows 1143/1144 and other placeholders already use).
- **Hudong-Zhonghua** → dropped the redundant `Shanghai` (all H-Z yards are in Shanghai; every other H-Z placeholder omits it).
- **HHI Ulsan** → dropped the `(HHI)` parenthetical **cluster-wide** (user decision), so the label is a clean single-token `HD Hyundai HI Ulsan`. This is why the hull-number rows 1152–1155 (real names, not placeholders) are also in scope — they carried `(HHI)` too. The Hayfin placeholders (row_id 1214/1215) were already in the target form and needed no change.

### Owner-portion fixes

| row_id | was | now | why |
|---|---|---|---|
| 1219 | `Hanwha Ocean (Knutsen)` | `Hanwha Ocean (Knutsen OAS 2)` | canonical owner form (`Knutsen OAS`, per `owner_charterer_map.md`) + missing ordinal; it is the sister of `(Knutsen OAS 1)` (row_id 1196 / sheet 1200) |
| 1218 | `Samsung HI Geoje (shipowner unknown)` | `Samsung HI Geoje (owner unknown)` | trim the one-off verbose phrasing; owner is genuinely `unknown`, so no ordinal |

### Deliberately left as-is (confirmed with user)

- `Samsung HI Geoje (MISC FSRU)` — `FSRU` descriptor kept (it's the lone FSRU in the cluster).
- `Hudong-Zhonghua (CNOOC, CMES, NYK 3/4/5/6)` — ordinals start at 3 by design; #1/#2 are the
  two identified hulls in the same cluster (`Hull H1889A` / `H1890A`).

## Ref handling

Every affected row carries a non-blank `Name [ref]` (CSB orderbook, trade press, DART). Those refs
document the **order**, not the literal placeholder string, so the §3.8c value↔ref gate does **not**
apply — running it would wrongly drop them (no page contains the synthetic name). Each cell was
emitted with `preserve_ref: true` (new flag, see below): the value is rewritten, the `[ref]` cell is
left **byte-for-byte untouched**, the gate is skipped, and a `PRESERVED` line is logged to QA_review.
Verified post-build: all 18 `Name [ref]` cells match the backend exactly; **0 refs dropped**.

## Tooling changes (committed with this batch)

- **`scripts/build_workbook.py`** — added the `preserve_ref: true` per-cell flag to fix mode for
  cosmetic / derived-value edits (changes the value, preserves the paired `[ref]`, skips the §3.8c gate).
- **`scripts/qc_backend.py`** — added two advisory (LOW) cross-row Name checks, run on every pull:
  - `name-builder-drift` — same yard (normalized Shipbuilder) written with different builder labels
    across its `Builder (Owner N)` placeholders.
  - `name-ordinal-gap` — a placeholder missing its sequence number while its `(Shipbuilder, Shipowner)`
    cluster siblings are numbered. Singletons and descriptor tails (`owner unknown`, `MISC FSRU`) are
    never flagged.

  On the current backend these flag exactly this batch's rows (28 drift + 1 gap). Simulating the apply
  drives both checks to **0** findings.

## Verification

- `recalc.py` → zero formula errors.
- Name values corrected + all `Name [ref]` preserved (programmatic diff vs backend): PASS.
- `qc_backend.py` simulated post-fix: 0 name findings.

## Apply

Name-only, additive-to-placeholder, no conflicts expected. Route through the normal apply path
(`batch_digest.py` → `apply_batch.py` → paste `apply_rows.csv` / `apply_patch.gs` → `verify_apply.py`).
Do **not** push without approval.
