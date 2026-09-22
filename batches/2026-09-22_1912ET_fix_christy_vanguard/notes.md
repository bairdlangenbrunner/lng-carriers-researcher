# Fix — Hull 2663 (SHI) named Christy Vanguard

**Batch:** `2026-09-22_1912ET_fix_christy_vanguard`
**Mode:** `fix` · 1 row · 2 cells · 3 refs checked, 0 dropped by the §3.8c gate
**Recalc:** zero formula errors

## Origin

Reviewer catch, 2026-09-22. While deciding the batch-4 `Operator/charterer` hold on
live row 876, Baird noticed the vessel now carries a name and supplied a shipspotting
page for it. Nothing in this repo had the name — no batch, no `work/` artifact, no
backend cell.

## The row

| | |
|---|---|
| live sheet row | **876** (`row_id` 130) |
| IMO | 1019670 |
| backend Name | `Hull 2663 (SHI)` (placeholder) |
| Status | `on order` (unchanged) |
| Shipowner | MOL · Samsung Heavy Industries · 174,000 cbm · delivery 2027 |

## Corrections

| field | backend | proposed | conf | refs |
|---|---|---|---|---|
| `Name` | `Hull 2663 (SHI)` | `Christy Vanguard` | **Y** | shipspotting photo 4013161 |
| `Other names` | *(blank)* | `Hull 2663 (SHI)` | **Y** | IGU 2025 PDF, IGU 2026 PDF |

`Other names` is the RF §4.16 companion line, derived by `scripts/other_names.py --batch`
and decided together with the `Name` line. Its former-name gate passed against both IGU
report PDFs — each prints `Hull 2663` for IMO 1019670 in its orderbook table, matched on
the hull number per §4.17.

`Hull number` (`Hull 2663 (SHI)`) and `Status` (`on order`) are deliberately untouched.

## Sourcing — single source, and why it is still worth proposing

`https://www.shipspotting.com/photos/4013161` is the **only** source carrying the name.
Its vessel page for the IMO titles it `CHRISTY VANGUARD - IMO 1019670`, flags it Marshall
Islands, categorises it *Ships Under Construction*, and lists the manager as MITSUI OSK
LINES. It passes the gate (`PASS (OK (cf_impersonate))`).

Every lane this repo normally consults still carries the hull placeholder:

| lane | what it says for IMO 1019670 |
|---|---|
| IGU 2025 Appendix 4 orderbook | `Hull 2663` |
| IGU 2026 Appendix 4 orderbook | `Hull 2663` |
| shipvault unit 463995 (RF §6a.8 first stop) | `MT HULL 2663`, on order, delivery 2027-01 |
| marinetraffic.org | `SAMSUNG 2663` |
| trade press | nothing indexed — searches on the name return no LNG result |

Corroboration is therefore **series-level, not source-level**. MOL runs an `<X>y Vanguard`
fleet, and hull 2663 is the second of a two-ship Samsung duo whose first hull is already
named:

| live row | IMO | Name | Hull | Name [ref] source |
|---|---|---|---|---|
| 847 | 9970674 | Archy Vanguard | Hull 2550 (Hanwha) | shipvault |
| **875** | 1019668 | **Gamy Vanguard** | **Hull 2662 (SHI)** | shipvault |
| **876** | 1019670 | → Christy Vanguard | Hull 2663 (SHI) | *this batch* |
| 960 | 1041439 | Barthy Vanguard | Hull 2687 (SHI) | shipvault |

All three siblings were named off shipvault. Shipvault has renamed unit 463994 (hull 2662)
but not yet 463995 (hull 2663) — our first-stop tracker is lagging on this one hull, and
the photographer got there first.

**Yellow, per SOP §5:** entity-level confirmation is solid (correct IMO, correct owner,
correct yard, correct series position) and the value is verbatim on the page, but it rests
on one non-primary source that the other lanes have not yet caught up to. Built on
shipspotting alone at Baird's direction, 2026-09-22.

## Why the research missed it

Not a miss on the line Baird was reviewing — the name was never in that line's scope:

1. The batch-4 line is an **Operator/charterer** data-fill cell. Data-fill is additive to
   blanks and `unknown`s only (DF §4). Row 876's `Name` is non-blank — it holds the
   placeholder — so no data-fill pass would ever look at it.
2. The IGU reconciliation compares names only where IGU prints one; IGU 2026 prints
   `Hull 2663`, matching the backend, so no finding.
3. shipvault and marinetraffic.org, the RF §6a.8 fallbacks and the sources the IGU Name
   exception points at, both still carry the placeholder.
4. `shipspotting.com` is not in `data/source_roster.md` and is not a stop in any discovery
   ring or §6a fallback step.

## Follow-up

- **Roster gap.** `shipspotting.com` beat shipvault on this rename and is a reasonable
  Tier 3 vessel database (its ship records are IMO-keyed and the page carries name, flag,
  manager and build status). Proposed for the Tier 3 list in `data/source_roster.md` and
  SOP §7 — **not added in this batch**, pending Baird's call.
- **Re-check shipvault 463995** in a few weeks. When it renames, append it to
  `Name [ref]` and the line goes Green.
