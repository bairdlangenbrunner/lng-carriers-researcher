# Batch digest — 2026-09-17_1654ET_fix_igu2026_sourced

**Mode:** fix  ·  **Proposals:** 497 (auto-safe 460, needs-decision 37)  ·  **Conflicts:** 0  ·  **Documented blanks:** 0

## ✅ Auto-safe — accept in bulk (Green / derivable)

By field: Vessel type ×289, Cargo type ×79, Name ×24, Propulsion type ×19, Delivery year ×15, Previous delivery year(s) ×14, Delivery delayed ×14, Capacity ×3, Capacity units ×2, Status ×1

These 460 are default-`accept` in `decisions.csv`. Skim or trust; nothing here needs a per-item call.

## ⚠️ Needs a decision (Yellow / Red / unknown)

- **row 721** · Name: `LNGT Antarctica` (Y) — 'Karmol LNGT Powership Antarctica' -> 'LNGT Antarctica': current name by IMO lookup (Baird 2026-09-18; not IGU-sourced). IGU 2026's 'Karadeniz LNGT Antarctica' is a label, carried in Other names with the former Name (batch 1737ET). shipvault / marinetraffic.org still print the Karmol name for IMO 8608872; vesseltracker.com (live AIS name, IMO 8608872) agrees — Equasis not checked (login)
- **row 811** · Name: `KLNGTP Americas` (Y) — 'LNGT Americas' -> 'KLNGTP Americas': vesseltracker.com (live AIS name, IMO 9045132), matching the backend's KLNGTP Black Sea / KLNGTP Marmara; shipvault prints 'Karadeniz LNGT P Americas', marinetraffic.org 'Karadeniz LNGT Powership Americas' — none prints IGU's 'Karadeniz LNGT Americas', which goes to Other names. No database prints the backend's 'LNGT Americas' — reject to keep it [IGU 2026 was the sole source; databases checked by IMO (Baird 2026-09-21)]
- **row 1004** · Name: `Gas Polaris` (Y) — 'Seapeak Hispania' -> 'Gas Polaris': marinetraffic.org and vesseltracker.com (IMO 9230048, Indonesian flag) — renamed again since IGU 2026's 'Seapeak Jupiter', which goes to Other names; shipvault still prints 'Seapeak Hispania' [IGU 2026 was the sole source; databases checked by IMO (Baird 2026-09-21)]
- **row 416** · Vessel type: `FSU` (Y) — 'conventional' -> 'FSU' per IGU 2026 (igu_changed; IGU 2025: 'Conventional') — FSU is out of scope for additions; row stays, scope flag [IGU 2026 Appendix 3 fleet table, PDF p.66; IMO 9236432; sole source per Baird ruling 2026-09-17]
- **row 686** · Status: `scrapped` (Y) — 'active' -> 'scrapped': shipvault (status SCRAPPED) and vesseltracker.com (header label 'scrapped', last position Bangladesh) for IMO 9250725, sailing under the demolition-voyage name 'Ergy'. IGU 2026 still lists the vessel — suggestion, held (Baird 2026-09-21); the row is kept, never deleted (IG §5.2)
- **row 459** · Name: `LNG Scorpio` (Y) — 'CCH LNG' -> 'LNG Scorpio': marinetraffic.org and vesseltracker.com (IMO 9307205); shipvault prints 'CCH Gas'; IGU 2026's 'LNG Soars' goes to Other names — a sanctioned vessel, renamed often [IGU 2026 was the sole source; databases checked by IMO (Baird 2026-09-21)]
- **row 374** · Vessel type: `FSRU` (Y) — 'conventional' -> 'FSRU' per IGU 2026 (backend_differs; IGU 2025: 'FSRU') [IGU 2026 Appendix 3 fleet table, PDF p.66; IMO 9390185; sole source per Baird ruling 2026-09-17]
- **row 371** · Name: `Al Kheesah` (Y) — 'Al-Kheesha' -> 'Al Kheesah': spelling only (`Al-Kheesha` vs IGU `Al Kheesah`) — sources differ on the transliteration [IGU 2026 Appendix 3 fleet table, PDF p.76; IMO 9982677; sole source per Baird ruling 2026-09-17]
- **row 703** · Status: `on order` (Y) — backend `active`, IGU 2026 still lists the vessel in the orderbook (shipvault lead agrees: not delivered) — sanctioned Arctic LNG 2 hull, Status left untouched in batch 1 [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918030; sole source per Baird ruling 2026-09-17]
- **row 703** · Delivery year: `2027` (Y) — rides with the Status change: IGU orderbook delivery year 2027 (backend 2025) [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918030; sole source per Baird ruling 2026-09-17]
- **row 703** · Previous delivery year(s): `2025` (Y) — former Delivery year 2025 (now proposed 2027) — decide with the Delivery year line; IGU landing page not asked; IGU 2025 prints 2025 for IMO 9918030
- **row 703** · Delivery delayed: `yes` (Y) — derived: Delivery year 2025 -> 2027 — decide with the Delivery year line
- **row 752** · Status: `on order` (Y) — backend `active`, IGU 2026 still lists the vessel in the orderbook (shipvault lead agrees: not delivered) — sanctioned Arctic LNG 2 hull, Status left untouched in batch 1 [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918016; sole source per Baird ruling 2026-09-17]
- **row 752** · Delivery year: `2027` (Y) — rides with the Status change: IGU orderbook delivery year 2027 (backend 2025) [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918016; sole source per Baird ruling 2026-09-17]
- **row 752** · Previous delivery year(s): `2025` (Y) — former Delivery year 2025 (now proposed 2027) — decide with the Delivery year line; IGU landing page not asked; IGU 2025 prints 2025 for IMO 9918016
- **row 752** · Delivery delayed: `yes` (Y) — derived: Delivery year 2025 -> 2027 — decide with the Delivery year line
- **row 916** · Status: `on order` (Y) — backend `active`, IGU 2026 still lists the vessel in the orderbook (shipvault lead agrees: not delivered) — sanctioned Arctic LNG 2 hull, Status left untouched in batch 1 [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918042; sole source per Baird ruling 2026-09-17]
- **row 916** · Delivery year: `2027` (Y) — rides with the Status change: IGU orderbook delivery year 2027 (backend 2025) [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918042; sole source per Baird ruling 2026-09-17]
- **row 916** · Previous delivery year(s): `2025` (Y) — former Delivery year 2025 (now proposed 2027) — decide with the Delivery year line; IGU landing page not asked; IGU 2025 prints 2025 for IMO 9918042
- **row 916** · Delivery delayed: `yes` (Y) — derived: Delivery year 2025 -> 2027 — decide with the Delivery year line
- **row 917** · Status: `on order` (Y) — backend `active`, IGU 2026 still lists the vessel in the orderbook (shipvault lead agrees: not delivered) — sanctioned Arctic LNG 2 hull, Status left untouched in batch 1 [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918054; sole source per Baird ruling 2026-09-17]
- **row 917** · Delivery year: `2027` (Y) — rides with the Status change: IGU orderbook delivery year 2027 (backend 2025) [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918054; sole source per Baird ruling 2026-09-17]
- **row 917** · Previous delivery year(s): `2025` (Y) — former Delivery year 2025 (now proposed 2027) — decide with the Delivery year line; IGU landing page not asked; IGU 2025 prints 2025 for IMO 9918054
- **row 917** · Delivery delayed: `yes` (Y) — derived: Delivery year 2025 -> 2027 — decide with the Delivery year line
- **row 981** · Status: `on order` (Y) — backend `active`, IGU 2026 still lists the vessel in the orderbook (shipvault lead agrees: not delivered) — sanctioned Arctic LNG 2 hull, Status left untouched in batch 1 [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918004; sole source per Baird ruling 2026-09-17]
- **row 981** · Delivery year: `2027` (Y) — rides with the Status change: IGU orderbook delivery year 2027 (backend 2025) [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918004; sole source per Baird ruling 2026-09-17]
- **row 981** · Previous delivery year(s): `2025` (Y) — former Delivery year 2025 (now proposed 2027) — decide with the Delivery year line; IGU landing page not asked; IGU 2025 prints 2025 for IMO 9918004
- **row 981** · Delivery delayed: `yes` (Y) — derived: Delivery year 2025 -> 2027 — decide with the Delivery year line
- **row 995** · Status: `on order` (Y) — backend `active`, IGU 2026 still lists the vessel in the orderbook (shipvault lead agrees: not delivered) [IGU 2026 Appendix 4 orderbook table, PDF p.79; IMO 1013494; sole source per Baird ruling 2026-09-17]
- **row 995** · Delivery year: `2026` (Y) — rides with the Status change: IGU orderbook delivery year 2026 (backend 2025) [IGU 2026 Appendix 4 orderbook table, PDF p.79; IMO 1013494; sole source per Baird ruling 2026-09-17]
- **row 995** · Previous delivery year(s): `2025` (Y) — former Delivery year 2025 (now proposed 2026) — decide with the Delivery year line; IGU landing page not asked; IGU 2025 prints 2025 for IMO 1013494
- **row 995** · Delivery delayed: `yes` (Y) — derived: Delivery year 2025 -> 2026 — decide with the Delivery year line
- **row 1143** · Status: `on order` (Y) — backend `active`, IGU 2026 still lists the vessel in the orderbook (shipvault lead agrees: not delivered) — sanctioned Arctic LNG 2 hull, Status left untouched in batch 1 [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918028; sole source per Baird ruling 2026-09-17]
- **row 1143** · Delivery year: `2027` (Y) — rides with the Status change: IGU orderbook delivery year 2027 (backend 2025) [IGU 2026 Appendix 4 orderbook table, PDF p.78; IMO 9918028; sole source per Baird ruling 2026-09-17]
- **row 1143** · Previous delivery year(s): `2025` (Y) — former Delivery year 2025 (now proposed 2027) — decide with the Delivery year line; IGU landing page not asked; IGU 2025 prints 2025 for IMO 9918028
- **row 1143** · Delivery delayed: `yes` (Y) — derived: Delivery year 2025 -> 2027 — decide with the Delivery year line
- **row 375** · Propulsion type: `TFDE` (Y) — 'DFDE' -> 'TFDE' per IGU 2026 — TFDE is not a value the backend uses today (DFDE covers it?) [IGU 2026 Appendix 3 fleet table, PDF p.77; IMO 9904546; sole source per Baird ruling 2026-09-17]

These are default-`hold`. Flip to `accept`/`reject` in `decisions.csv`, then re-run `apply_batch.py`.

## ⛔ Conflicts — research disagrees with a filled backend value

_(none)_

## Next steps

1. Edit `decisions.csv` (flip any holds).  2. `python scripts/apply_batch.py --batch batches/2026-09-17_1654ET_fix_igu2026_sourced`.  3. Apply: paste `apply_rows.csv` rows over the matching backend rows, **or** run the `apply_patch.gs` by-name applier on `apply_patch.csv`.  4. `python scripts/verify_apply.py --batch batches/2026-09-17_1654ET_fix_igu2026_sourced` to confirm everything landed.
