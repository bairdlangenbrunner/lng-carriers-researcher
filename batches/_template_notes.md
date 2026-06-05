# Batch <YYYY-MM-DD> — <mode> — <scope>

**SOP revs at time of batch:** RF rev XX, DC rev XX

**Backend pull:** <bytes>, <N> data rows, header row index <i>

## Scope

- Rows / gap window:
- Yards in scope:
- Mode-specific parameters: <e.g. proposed threshold, FSRU handling>

## Summary

<2-3 sentences: what was filled or discovered, how many cells, how many conflicts, anything unusual>

## Confidence breakdown

| Confidence | Count |
|---|---|
| Green | |
| Yellow | |
| Red | |
| Blank (with §6a.9 negative log) | |

## Defects corrected

<List any pre-existing backend [ref] URLs that were overridden, per RF §3.0 step 3.
Each entry: row id, field, old URL, why it was wrong, new URL.>

## Conflicts flagged for human review

<List any backend DATA values (not [ref]s) that research suggests are wrong.
Backend is never overwritten — these go to QA_review for the user to resolve.>

## Apply & verify (docs/sops/apply.md)

<Once reviewed: run batch_digest.py → apply_batch.py → apply (apply_rows.csv or
apply_patch.gs) → verify_apply.py --pull. Record: how many proposals accepted /
held / rejected (from decisions.csv), any conflicts resolved, and the verify result
(landed / mismatch / missing). Commit decisions.csv + apply.json as the record.>

## Escalations

<Any pause-and-ask triggers hit? See CLAUDE.md "When to escalate".>

## Sources used

<Optional: rough breakdown of which tiers were used — useful for spotting
over-reliance on a single source.>

## Drive link

<Paste the Google Sheets share link once the xlsx is uploaded.>

## Script changes

<If any scripts/*.py were modified during this batch, list them here. The commit
will show the diff, but a one-line summary helps future-you.>
