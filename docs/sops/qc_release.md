# LNG Carrier Tracker — Pre-release QC SOP

**Document purpose:** Operating manual for the **pre-release QC pass** — a sweep of the
live backend for consistency/corruption defects ahead of a data release, and (where a
defect is mechanical) packaging the corrections as a `fix`-mode candidate batch for human
review. It complements the [ref]-Fill / Discovery / Data-fill SOPs (which *add* sourced
data) and the Apply SOP (which lands a reviewed batch). **Authoritative** for this
workflow. Abbreviated **QC**.

**Last revised:** 2026-06-05 rev 1 (initial SOP, written alongside the first Name-column
normalization batch. Defines the placeholder-Name conventions (§2), the QC scan + triage
(§3), the `fix`-mode correction batch with the `preserve_ref` escape hatch for
cosmetic/derived edits (§4), and the release gate (§5). Leans on `scripts/qc_backend.py`
and `build_workbook.py --mode fix`; routes corrections through the Apply SOP unchanged.).

---

## 1. Scope

**What the pre-release QC pass does.** Before a data release, scan the *whole* live backend
(not a row window) for defects that the additive batch workflows don't catch: column-offset /
misplaced-value corruption, orphan refs, lookup-table disagreements, and **Name-column
inconsistency**. Triage the findings; for the mechanical ones, build a `fix`-mode batch and
route it through the normal Apply round-trip.

**This is a correction workflow, not a research workflow.** It never invents new sourced data.
It either (a) normalizes a derived/cosmetic value (e.g. a placeholder Name string), or (b)
corrects a value that is provably wrong against its own existing `[ref]` (the §3.8c gate).
The backend is never edited directly ([ref]-Fill SOP §4.7) — output is a candidate xlsx.

**In scope.** Everything `qc_backend.py` checks (see its module docstring), with particular
release attention to:
- `name-builder-drift` / `name-ordinal-gap` — the Name-column checks (§2).
- `column-offset` / `misplaced-vocab` / `url-in-value` / `bad-shape` — corruption signatures.
- `orphan-ref` (Rule F), `lookup-mismatch`.

**Out of scope.** Filling blanks (→ Data-fill SOP), finding new vessels (→ Discovery SOP),
researching a value to resolve a conflict against a non-blank cell (→ [ref]-Fill SOP §8).

---

## 2. Name-column conventions (authoritative)

The `Name` column carries either a **real christened vessel name** or a **placeholder** for an
un-christened hull. There are exactly two placeholder forms:

1. **`Hull NNNN (Yard)`** — used when the **hull number is known** but the ship is unnamed.
   `NNNN` is the yard hull number; `(Yard)` is the short yard tag (e.g. `SHI`, `Zvezda`,
   `Hanwha`). Example: `Hull 2693 (SHI)`.

2. **`Shipbuilder (Owner N)`** — used when **only the owner is known** (no hull number, no
   name). `N` is the 1-based ordinal disambiguating that owner's un-named sister hulls at that
   yard. Example: `Hudong-Zhonghua (CNOOC, CMES, NYK 4)`.

**Consistency rules** (enforced advisorily by `qc_backend.py`):

- **B1 — one builder label per yard.** Across all `Shipbuilder (Owner N)` placeholders that
  resolve to the **same `normalize_builder` tag**, the builder portion must be spelled
  identically. Prefer the form already used by that yard's identified-hull sibling rows and
  the established short form (drop redundant geography, e.g. `Hudong-Zhonghua`, not
  `Hudong-Zhonghua Shanghai`). Flagged as `name-builder-drift`.
- **B2 — canonical owner form.** The owner portion uses the backend's canonical short owner
  display ([ref]-Fill SOP §4.14 / `owner_charterer_map.md`), e.g. `Knutsen OAS`, not `Knutsen`.
- **B3 — ordinals are contiguous within a cluster.** Within a `(Shipbuilder, Shipowner)`
  cluster, every un-named sister carries a trailing ordinal; a placeholder missing one while
  its siblings are numbered is flagged `name-ordinal-gap`. Identified hulls in the same cluster
  occupy ordinals implicitly (so a sequence may legitimately start mid-count — e.g. ordinals
  3–6 when #1/#2 are the two identified hulls). Singletons and intentional descriptor tails
  (`(owner unknown)`, `(MISC FSRU)`) are **not** ordinal-flagged and are left as-is.

`qc_backend.py` flags violations of B1/B3 (LOW, advisory). B2 is reviewed by eye against
`owner_charterer_map.md` — it's not auto-checked.

---

## 3. The QC scan + triage

```bash
# 1. Fresh backend CSV + colmap — MANDATORY first step (RF §3.0).
python scripts/pull_backend.py

# 2. Full-backend QC scan (no --rows; release pass is whole-sheet).
python scripts/qc_backend.py          # -> work/qc_report.csv ; --strict to gate CI
```

Triage `work/qc_report.csv` by check:

| Finding | Severity | Disposition |
|---|---|---|
| `column-offset`, `misplaced-vocab`, `url-in-value`, `bad-shape` | HIGH/MED | Corruption — escalate to the user; usually a backend-side paste error. May need a `fix` batch or a manual backend repair. |
| `orphan-ref` (Rule F) | MED | Either the value is missing (research → Data-fill) or the ref is stray (drop → `fix`). |
| `lookup-mismatch` | MED | Compare against `shipbuilder_facts` / `shipowner_facts`; correct whichever is wrong. |
| `name-builder-drift`, `name-ordinal-gap` | LOW | Name normalization — almost always a mechanical `fix` batch (§4). The scan flags the **whole** inconsistent group; unifying the group clears them all. |

Confirm the canonical target form with the user before mass-renaming (which builder label
wins; how to unify a label that itself contains parens). Known-legit oddities go in
`refdata/qc_allowlist.csv`, not into a fix.

---

## 4. The fix batch (mechanical corrections)

For mechanical corrections, build a `fix`-mode candidate workbook. Two kinds of cell edit:

- **Sourced value correction** (e.g. a wrong capacity): supply `refs`; each is routed through
  the **§3.8c value↔ref corroboration gate** — a ref stays only if its live page contains the
  corrected value, else it's dropped and logged. This is the default fix-mode behavior.
- **Cosmetic / derived-value edit** (e.g. normalizing a placeholder Name string): set
  **`preserve_ref: true`** on the cell. The value is rewritten, the paired `[ref]` is left
  **byte-for-byte untouched**, and the gate is **skipped** — because that ref documents the
  underlying order, not the literal string, so the gate would wrongly drop it (no page contains
  a synthetic placeholder name). A `PRESERVED` line is logged to QA_review. `refs`/`drop_refs`
  are ignored on a `preserve_ref` cell.

```bash
# fix.json keyed by row_id (the column-A stamp), Name cells with preserve_ref:true for
# placeholder normalization. Schema: see build_workbook.py build_fix docstring.
python scripts/build_workbook.py --mode fix --fix work/<name>_fix.json \
  --out batches/<date>_<HHMMET>_<label>/

python scripts/recalc.py batches/<date>_<HHMMET>_<label>/lng_carrier_fix.xlsx   # zero errors

# Sanity: confirm the build dropped 0 refs on a pure-cosmetic batch, and that re-running
# qc_backend.py on a copy with the fix applied drives the targeted findings to 0.
```

Copy the `fix.json` into the batch dir, write `notes.md` (what/why, the rename table, ref
handling, any tooling changes, verification), and commit the batch directory. Do **not** push
without approval.

---

## 5. Apply + release gate

A QC fix batch lands through the **Apply SOP** (`docs/sops/apply.md`) unchanged:
`batch_digest.py` → `apply_batch.py` → paste `apply_rows.csv` / run `tools/apply_patch.gs`
(by-name, offset-proof) → `verify_apply.py --pull`. Name-only normalizations are
additive-to-placeholder and should produce no conflicts.

**Release gate.** Before declaring the backend release-ready, re-pull and re-run
`python scripts/qc_backend.py`. The release is clear when every HIGH/MED finding is either
resolved or allowlisted with a documented reason, and the Name checks (`name-builder-drift` /
`name-ordinal-gap`) are at zero (or every remaining one is an allowlisted descriptor).

---

## 6. Pause-and-ask triggers

- A `column-offset` / `misplaced-vocab` cluster that points at backend-side paste corruption
  (a whole row or column shifted) — surface to the user; a `fix` batch may not be the right
  tool (the backend itself may need a manual repair).
- A whole class of Name values that disagrees with §2 (suggests the convention itself drifted
  or a batch was built against an older convention) — confirm the canonical form before a mass
  rename.
- A `name-builder-drift` group where the "correct" label is genuinely ambiguous (e.g. the
  established label contains parentheses) — get the user's call on how to unify before building.
