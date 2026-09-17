# Overnight full update — 2026-09-17 (autonomous run, state file)

**Deadline:** 07:30 ET 2026-09-17. **Mode:** autonomous; Baird is asleep; make every
decision, record it here. **Resume rule:** a new session reads this file top to
bottom, then continues from the first unchecked step. Update this file after every
step and commit batch dirs as they finish (branch -> PR -> merge is pre-authorized).

## Standing decisions (made for Baird)

- Reference fixing (Stream 0 rot-sweep fix batch, `--corroborate`) is **paused**. Do not resume it.
- "Finish the update" = every batch built, gated, recalc'd, committed, with
  `digest.md` + `apply_batch.py` artifacts ready. **The Google Sheet is never written**
  (hard rule + work-Drive rule). Baird applies in the morning.
- Plan of record: `docs/plans/2026-09-16_full_research_pass.md`, streams 1, 2, 4, 5, then 3 if time allows.
- Gap window for discovery: 2026-05-01 -> 2026-09-17 (latest backend contract date 08-Jun-2026; overlap is deduped). All yards. FSRUs batched in. Proposed bucket: named yard or signed LOI/HoA only.
- The 983 Dec-2024 bulk-loaded active rows: leave their Price/Operator/Contract-date blanks alone.
- Subagents: sonnet for research; every ref re-gated centrally (never pre-trusted).
- Scratch lives in `work/overnight/` (gitignored). Batch dirs use `TZ=America/New_York date '+%Y-%m-%d_%H%MET'`.
- Key tool: shipvault open API (`scripts/imo_tracker.py`: `shipvault_search`, `shipvault_unit`) returns status / name / yardno / delivered / capacity / owner / price per IMO, and the verifier corroborates `https://www.shipvault.com/ships/{id}` against that record. Script first, research agents second.

## Steps

- [x] 0. Ship last session's fetch-ladder work (PR #10 merged). Fresh pull 2026-09-17 ~01:15 ET: 1,220 rows (822 active / 364 on order / 34 proposed); QC 7 LOW only.
- [ ] 1. Watchdog running (`work/overnight/watchdog.sh`, log `work/overnight/watchdog.log`).
- [ ] 2. Shipvault sweep of all on-order/proposed rows -> `work/overnight/shipvault_sweep.json`.
- [ ] 3. Delivery roll-forward fix batch(es) from the sweep (+ agent research for rows shipvault cannot resolve).
- [ ] 4. Discovery batch (window above).
- [ ] 5. Proposed-bucket review (Mozambique LNG 01-17, Woodside 01-16, Equinor).
- [ ] 6. On-order data-fill batch (core facts; rows not covered by step 3).
- [ ] 7. Rule-F ref-fill (20 cells) — only if time remains.
- [ ] 8. Final: qc_backend, dedupe_check, digests + apply artifacts for every batch, morning summary at `docs/plans/2026-09-17_overnight_summary.md`, merge to main, write `work/overnight/DONE`.

## Log (append newest last)

- 01:20 state file created.
