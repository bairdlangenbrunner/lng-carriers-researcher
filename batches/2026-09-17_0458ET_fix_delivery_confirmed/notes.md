# Fix batch — deliveries confirmed by trade press (2026-09-17, overnight run)

Follow-up to `2026-09-17_0421ET_fix_delivery_rollforward`. That batch left 26 on-order rows in
`manual_review.json` because AIS shows them sailing under a real name while shipvault still lists
them ON ORDER. Two research agents looked for a **past-tense delivery statement** for each.

Confirmed (in this batch, both Y — single source, LNG Prime):
- **Live row 887** (row_id 186, IMO 9981427, `Hull 3387 (HDHHI)`) → Status `active`, Name
  **Al Nigyan** — Knutsen took delivery Aug-2026 (QatarEnergy programme).
- **Live row 924** (row_id 318, IMO 1040693, `Hull YZJ2022-1475`) → Status `active` —
  Yangzijiang delivered **Yangze LNG 01** on/around 20-Aug-2026 (the Name is already proposed in
  the roll-forward batch). Note a data-fill agent found the original contract for rows 924/925 was
  terminated and the pair built speculatively — see the data-fill batch findings.

Not changed (24 rows, `manual_review.json`): 1 explicitly not delivered (row 824 Pyotr Stolypin,
still at Zvezda), 2 named but delivery stated as pending (row 851 Fujin Sailor, row 878 Toho
Emerald), 21 with no citable delivery statement either way. Name discrepancies worth a look:
row 934 (AIS `Hai Xie` vs shipvault `Sea Harmony`), row 933 (AIS `Dachuan Haishang` vs shipvault
`Sea Argosy`).

Gate: every ref passed §3.8c at pre-gate and again at build (0 dropped). Recalc: zero formula
errors. One agent caught a gate false positive — the bare word "active" in page boilerplate can
pass the Status gate; the agents overrode it by reading the page, and it is listed in the
overnight summary as a verifier follow-up.
