# Batch digest — 2026-09-17_1654ET_fix_igu2026_sourced

**Mode:** fix  ·  **Proposals:** 464 (auto-safe 439, needs-decision 25)  ·  **Conflicts:** 0  ·  **Documented blanks:** 0

## ✅ Auto-safe — accept in bulk (Green / derivable)

By field: Vessel type ×296, Cargo type ×79, Name ×24, Propulsion type ×19, Delivery year ×15, Capacity ×3, Capacity units ×2, Status ×1

These 439 are default-`accept` in `decisions.csv`. Skim or trust; nothing here needs a per-item call.

## ⚠️ Needs a decision (Yellow / Red / unknown)

- **row 721** · Name: `LNGT Antarctica` (Y) — 'Karmol LNGT Powership Antarctica' -> 'LNGT Antarctica': current name by IMO lookup (Baird 2026-09-18; not IGU-sourced). IGU 2026's 'Karadeniz LNGT Antarctica' is a label, carried in Other names with the former Name (batch 1737ET). shipvault / marinetraffic.org still print the Karmol name for IMO 8608872; vesseltracker.com (live AIS name, IMO 8608872) agrees — Equasis not checked (login)
- **row 811** · Name: `KLNGTP Americas` (Y) — 'LNGT Americas' -> 'KLNGTP Americas': vesseltracker.com (live AIS name, IMO 9045132), matching the backend's KLNGTP Black Sea / KLNGTP Marmara; shipvault prints 'Karadeniz LNGT P Americas', marinetraffic.org 'Karadeniz LNGT Powership Americas' — none prints IGU's 'Karadeniz LNGT Americas', which goes to Other names. No database prints the backend's 'LNGT Americas' — reject to keep it [IGU 2026 was the sole source; databases checked by IMO (Baird 2026-09-21)]
- **row 969** · Vessel type: `conventional` (Y) — value unchanged — Rule F ref-fill: backend Vessel type had no [ref] — HOLD: this row's FSU-conversion question (batch 5) is still open [vessel not listed in IGU 2026; the report is cited as the source of the Vessel type classification (size classes), capacity 135000 cbm; per Baird ruling 2026-09-17]
- **row 1004** · Name: `Gas Polaris` (Y) — 'Seapeak Hispania' -> 'Gas Polaris': marinetraffic.org and vesseltracker.com (IMO 9230048, Indonesian flag) — renamed again since IGU 2026's 'Seapeak Jupiter', which goes to Other names; shipvault still prints 'Seapeak Hispania' [IGU 2026 was the sole source; databases checked by IMO (Baird 2026-09-21)]
- **row 416** · Vessel type: `FSU` (Y) — 'conventional' -> 'FSU' per IGU 2026 (igu_changed; IGU 2025: 'Conventional') — FSU is out of scope for additions; row stays, scope flag [IGU 2026 Appendix 3 fleet table, PDF p.66; IMO 9236432; sole source per Baird ruling 2026-09-17]
- **row 459** · Name: `LNG Scorpio` (Y) — 'CCH LNG' -> 'LNG Scorpio': marinetraffic.org and vesseltracker.com (IMO 9307205); shipvault prints 'CCH Gas'; IGU 2026's 'LNG Soars' goes to Other names — a sanctioned vessel, renamed often [IGU 2026 was the sole source; databases checked by IMO (Baird 2026-09-21)]
- **row 374** · Vessel type: `FSRU` (Y) — 'conventional' -> 'FSRU' per IGU 2026 (backend_differs; IGU 2025: 'FSRU') [IGU 2026 Appendix 3 fleet table, PDF p.66; IMO 9390185; sole source per Baird ruling 2026-09-17]
- **row 371** · Name: `Al Kheesah` (Y) — 'Al-Kheesha' -> 'Al Kheesah': spelling only (`Al-Kheesha` vs IGU `Al Kheesah`) — sources differ on the transliteration [IGU 2026 Appendix 3 fleet table, PDF p.76; IMO 9982677; sole source per Baird ruling 2026-09-17]
- **row 703** · Status: `on order` (Y) — backend `active`, IGU 2026 still lists the vessel in the orderbook (shipvault lead agrees: not delivered) — sanctioned Arctic LNG 2 hull, Status left untouched in batch 1 [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918030; sole source per Baird ruling 2026-09-17]
- **row 703** · Delivery year: `2027` (Y) — rides with the Status change: IGU orderbook delivery year 2027 (backend 2025) [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918030; sole source per Baird ruling 2026-09-17]
- **row 752** · Status: `on order` (Y) — backend `active`, IGU 2026 still lists the vessel in the orderbook (shipvault lead agrees: not delivered) — sanctioned Arctic LNG 2 hull, Status left untouched in batch 1 [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918016; sole source per Baird ruling 2026-09-17]
- **row 752** · Delivery year: `2027` (Y) — rides with the Status change: IGU orderbook delivery year 2027 (backend 2025) [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918016; sole source per Baird ruling 2026-09-17]
- **row 916** · Status: `on order` (Y) — backend `active`, IGU 2026 still lists the vessel in the orderbook (shipvault lead agrees: not delivered) — sanctioned Arctic LNG 2 hull, Status left untouched in batch 1 [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918042; sole source per Baird ruling 2026-09-17]
- **row 916** · Delivery year: `2027` (Y) — rides with the Status change: IGU orderbook delivery year 2027 (backend 2025) [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918042; sole source per Baird ruling 2026-09-17]
- **row 917** · Status: `on order` (Y) — backend `active`, IGU 2026 still lists the vessel in the orderbook (shipvault lead agrees: not delivered) — sanctioned Arctic LNG 2 hull, Status left untouched in batch 1 [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918054; sole source per Baird ruling 2026-09-17]
- **row 917** · Delivery year: `2027` (Y) — rides with the Status change: IGU orderbook delivery year 2027 (backend 2025) [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918054; sole source per Baird ruling 2026-09-17]
- **row 981** · Status: `on order` (Y) — backend `active`, IGU 2026 still lists the vessel in the orderbook (shipvault lead agrees: not delivered) — sanctioned Arctic LNG 2 hull, Status left untouched in batch 1 [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918004; sole source per Baird ruling 2026-09-17]
- **row 981** · Delivery year: `2027` (Y) — rides with the Status change: IGU orderbook delivery year 2027 (backend 2025) [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918004; sole source per Baird ruling 2026-09-17]
- **row 995** · Status: `on order` (Y) — backend `active`, IGU 2026 still lists the vessel in the orderbook (shipvault lead agrees: not delivered) [IGU 2026 Appendix 4 orderbook table, PDF p.79; IMO 1013494; sole source per Baird ruling 2026-09-17]
- **row 995** · Delivery year: `2026` (Y) — rides with the Status change: IGU orderbook delivery year 2026 (backend 2025) [IGU 2026 Appendix 4 orderbook table, PDF p.79; IMO 1013494; sole source per Baird ruling 2026-09-17]
- **row 1143** · Status: `on order` (Y) — backend `active`, IGU 2026 still lists the vessel in the orderbook (shipvault lead agrees: not delivered) — sanctioned Arctic LNG 2 hull, Status left untouched in batch 1 [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918028; sole source per Baird ruling 2026-09-17]
- **row 1143** · Delivery year: `2027` (Y) — rides with the Status change: IGU orderbook delivery year 2027 (backend 2025) [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918028; sole source per Baird ruling 2026-09-17]
- **row 375** · Propulsion type: `TFDE` (Y) — 'DFDE' -> 'TFDE' per IGU 2026 — TFDE is not a value the backend uses today (DFDE covers it?) [IGU 2026 Appendix 3 fleet table, PDF p.77; IMO 9904546; sole source per Baird ruling 2026-09-17]
- **row 250** · Vessel type: `conventional` (Y) — value unchanged — Rule F ref-fill: backend Vessel type had no [ref] — HOLD: no backend Capacity, so the size class cannot be derived [vessel not listed in IGU 2026; the report is cited as the source of the Vessel type classification (size classes), capacity blank cbm; per Baird ruling 2026-09-17]
- **row 1218** · Vessel type: `conventional` (Y) — value unchanged — Rule F ref-fill: backend Vessel type had no [ref] — HOLD: no backend Capacity, so the size class cannot be derived [vessel not listed in IGU 2026; the report is cited as the source of the Vessel type classification (size classes), capacity blank cbm; per Baird ruling 2026-09-17]

These are default-`hold`. Flip to `accept`/`reject` in `decisions.csv`, then re-run `apply_batch.py`.

## ⛔ Conflicts — research disagrees with a filled backend value

_(none)_

## Next steps

1. Edit `decisions.csv` (flip any holds).  2. `python scripts/apply_batch.py --batch batches/2026-09-17_1654ET_fix_igu2026_sourced`.  3. Apply: paste `apply_rows.csv` rows over the matching backend rows, **or** run the `apply_patch.gs` by-name applier on `apply_patch.csv`.  4. `python scripts/verify_apply.py --batch batches/2026-09-17_1654ET_fix_igu2026_sourced` to confirm everything landed.
