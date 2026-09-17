# sep-17-pass — full update, 2026-09-17 (autonomous run, state file)

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
- [x] 1. Watchdog running (`work/overnight/watchdog.sh`, log `work/overnight/watchdog.log`).
- [x] 2. Shipvault sweep of all on-order/proposed rows -> `work/overnight/shipvault_sweep.json`.
- [x] 3. Delivery roll-forward fix batch(es) from the sweep (+ agent research for rows shipvault cannot resolve).
- [x] 4. Discovery batch (window above) -> `batches/2026-09-17_0431ET_discovery_since_jun_2026/` (12 candidates, 5 clusters) + `batches/2026-09-17_0458ET_fix_delivery_confirmed/`.
- [x] 5. Proposed-bucket review (Mozambique LNG 01-17, Woodside 01-16, Equinor).
- [x] 6. On-order data-fill batch -> `batches/2026-09-17_0511ET_data_fill_on_order/` (949 proposals, 477 rows).
- [x] 7. Rule-F ref-fill -> `batches/2026-09-17_0505ET_ref_fill_rule_f/` (8 refs proposed, 11 documented negatives).
- [x] 8. Final: qc_backend, dedupe_check, digests + apply artifacts for every batch, morning summary at `docs/plans/2026-09-17_sep-17-pass_summary.md`, merge to main, write `work/overnight/DONE`.

## Log (append newest last)

- 01:20 state file created.

## Log (ET)

- 00:58 watchdog running (`work/overnight/watchdog.sh`); shipvault sweep complete (323 on-order IMOs: 252 on order, 63 active, 7 no record, 1 sanctioned) -> `work/overnight/shipvault_sweep.jsonl`.
- 01:05 verifier: `value_variants` now renders `DD-Mon-YYYY` dates so `Contract date` cells can pass the §3.8c gate (tests added). Branch `overnight-update-2026-09-17`.
- 01:08 eight sonnet data-fill agents launched (task files `work/overnight/datafill_tasks_N.json` -> `work/research_of<N>.json`). If a session restarts and some `research_ofN.json` are missing/short, relaunch only those N.
- 01:12 discovery agents korea + china/other finished (`work/overnight/discovery_*.json`): 5 new clusters / 12 vessels so far (SHI-Dynagas x4, HHI-Tsakos x1, HHI FSRU x1, Jiangnan-ADNOC x4 + x2). Press cross-check still running.
- 01:12 proposed review finished (`work/overnight/proposed_review.json`): no cell edits; recommend deleting Woodside placeholders live rows 1204-1206 (converted: Seapeak rows 1165-1167). Goes in the morning summary.
- 01:15 vesselfinder sweep ~150/323 (`work/overnight/vesselfinder_sweep.jsonl`, resumable: `python work/overnight/vf_sweep.py`). Then: `python work/overnight/make_rollforward.py` -> `python work/overnight/gate_fix.py work/overnight/rollforward_fix.raw.json work/overnight/rollforward_fix.json` -> build fix batch.
- 01:15 shipvault on-order LNG hull enumeration started (`python work/overnight/sv_orderbook.py`, resumable -> `work/overnight/sv_orderbook.jsonl`): finds IMOs/hulls for the 41 no-IMO rows and cross-checks discovery completeness.
- 01:35 local (clock note: this machine runs ~3 h behind ET; deadline 07:30 is LOCAL; batch dir stamps stay ET). roll-forward batch `batches/2026-09-17_0421ET_fix_delivery_rollforward/` built, gated, recalc clean, apply artifacts written (apply_batch.py now has a `fix` mode). step 3 done.
- shipvault on-order enumeration done -> `work/overnight/sv_orderbook.jsonl`; `work/research_sv.json` holds 81 central hull/IMO/capacity fills for the data-fill merge. discovery agent outputs in `work/overnight/discovery_*.json`, proposed review in `proposed_review.json`.
- delivery-check agent 2 finished (`delivery_check_2.out.json`: 1 delivered, 2 sea trials, 10 unresolved); agent 1 + 8 data-fill agents (`work/research_of1..8.json`) still running. on restart relaunch only the missing N.
- 02:10 local: all 8 data-fill agents done (`work/research_of1..8.json`, `research_sv.json`, `research_leads.json`, `research_zz_companions.json`); pre-merge sanity filter run; `merge_fills.py` running in background -> `work/overnight/merge.log` (base copy `work/overnight/data_fill.base.json`). If restarting: check merge.log ends with "final fills:"; if not, `cp work/overnight/data_fill.base.json work/data_fill.json` and re-run merge, then build step 6.
- 02:25 local: all steps done; summary at `docs/plans/2026-09-17_sep-17-pass_summary.md`; merged to main; `work/overnight/DONE` written.
