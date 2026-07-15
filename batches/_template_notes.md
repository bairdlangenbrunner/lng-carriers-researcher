# <YYYY-MM-DD> <HHMMET> — <mode> — <scope>

**SOP revs at time of batch:** <every SOP that governed this batch, e.g. RF rev 18, DC rev 8, DF rev 2, SR rev 5, FR rev 1, QC rev 1, AP rev 3 — omit the ones that didn't apply>

**Backend pull:** <bytes>, <N> data rows, header row index <i>

## Scope

- Rows / gap window / target:
- Yards in scope (if applicable):
- Mode-specific parameters: <e.g. proposed threshold, FSRU handling, --since date, fleet table edition>

## Summary

<2–3 sentences: what was proposed or found, headline counts, anything unusual. This is
what gets condensed into the batch-index row in batches/README.md.>

## Outcome

<ONE table, matched to the mode:>

<ref-fill / discovery / data-fill / corroborate — confidence breakdown:>

| Confidence | Count |
|---|---|
| Green | |
| Yellow | |
| Red | |
| Blank (with §6a.9 negative log / documented blank) | |

<reconciliations (SFOC / FSRU) — bucket counts:>

| Bucket | Count |
|---|---|
| Matched | |
| ... | |

<fix / QC — check counts:>

| Check | Findings | Corrected |
|---|---|---|
| ... | | |

## Conflicts / escalations

<Backend DATA values research says are wrong (never overwritten — they go to QA_review),
defects corrected (row id, field, old URL, why wrong, new URL), and any pause-and-ask
triggers hit (CLAUDE.md "When to escalate"). Write "none" explicitly if none.>

## Apply status

<One of: not yet reviewed / reviewed, awaiting apply / applied + verified on <date>.
Once applied: proposals accepted / held / rejected (from decisions.csv), conflicts
resolved, verify result (landed / mismatch / missing), dedupe sweep result.>

## Script changes

<If any scripts/*.py were modified during this batch, list them with a one-line summary.
Write "none" explicitly if none.>

---

<Free-form sections below this line: per-cluster narrative, source notes, methodology
detail — whatever this batch needs. The sections above are the required core.>
