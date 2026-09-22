# fix — Shipowner country/area refs off shipvault (2026-09-21 20:03 ET)

## Why

A `shipvault.com` ship page (and the unit record behind it) prints the **owner
string** and the **vessel's flag**. It never states where the owner is based, so
it cannot corroborate a `Shipowner country/area` cell under RF §3.8c. Two
consequences were live in the data:

1. **In the pending data-fill batch** (`2026-09-17_0511ET_data_fill_on_order`),
   the §3.8c gate correctly dropped the copied shipvault ref, and Data-fill SOP §5
   kept the value anyway (a derivable fill stands on backend consistency). That
   produced 63 Green, default-`accept`, **ref-less** country proposals — the
   "blank → South Korea, no references" card Baird hit in the review app on
   SK Sunrise (live row 79). None had been pushed.
2. **In the backend**, 55 rows still carry a shipvault URL in
   `Shipowner country/area [ref]`. Where those passed a gate at all, they passed
   because the *flag* happened to read like the country — corroboration of the
   wrong fact.

## What this batch does

Replaces the `Shipowner country/area [ref]` on all 55 rows with 2–3 sources that
name the country as the owner's base. Fix-mode default semantics apply: the
gated refs **replace** the shipvault URL. Zero refs were dropped by the gate.

| decision | rows | |
|---|---|---|
| accept (G) | 53 | value unchanged — reference swap only |
| **hold (Y)** | 2 | **value change, needs Baird** |

### The two holds — live sheet rows 953 and 954

`Hull 2606 (Hanwha)` (IMO 1115072) and `Hull 2607 (Hanwha)` (IMO 1115084),
Shipowner `Hanwha Ocean Co Ltd`, currently **United States** → proposed
**South Korea**.

Hanwha Ocean Co Ltd is the South Korean shipbuilder (ex-DSME, Geoje); the US
entity is the separate **Hanwha Shipping LLC**. The old value came with a
shipvault ref that states neither. So one of the two cells is wrong, and which
one is Baird's call: if the intended owner of these hulls really is Hanwha
Shipping LLC, fix the `Shipowner` cell instead and leave the country as
United States. Held rather than applied; it is excluded from `apply_patch.csv`.

## Sources by owner

| owner tag | country | refs |
|---|---|---|
| misc (37 rows) | Malaysia | misc.com.my contact page, MISC Integrated Annual Report 2025 (PDF), Wikipedia |
| capital maritime & trading corp (4) | Greece | magicport, capitalship.gr press release |
| adnoc (3) | United Arab Emirates | magicport, stockanalysis, Ship & Bunker |
| sk shipping (2) | South Korea | Wikipedia, Splash 247 |
| mol (2) | Japan | Wikipedia, magicport, stockanalysis |
| hanwha ocean co ltd (2) | South Korea | hanwha.com, Lloyd's Register shipyard profile, CNBC |
| evalend shipping (2) | Greece | magicport, Splash 247 ×2 |
| maran-gas (1) | Greece | magicport, LNG Prime |
| celsius (1) | Denmark | magicport, LNG Prime ×2 |
| capital (1) | Greece | magicport, stockanalysis, Riviera Maritime |

`mol` and `maran-gas` stay **`AMBIGUOUS`** in `data/shipowner_facts.csv` on
purpose — their backend siblings genuinely disagree, so the autofill must keep
researching them per vessel. The refs above corroborate the value *these
specific rows* already carry.

## Also changed outside the batch

- `data/shipowner_facts.csv` — the seven owner tags whose table ref was a
  shipvault URL now carry 2–3 gate-passing refs, and `hanwha ocean co ltd` is
  corrected United States → South Korea. `adnoc`'s failing `adnocls.ae` ref
  (page never says "United Arab Emirates") was swapped out in the same pass.
- `batches/2026-09-17_0511ET_data_fill_on_order/` — all 63 ref-less country
  fills now carry the table's refs; 63 stale `candidate_findings` naming the
  dropped shipvault URL removed; apply artifacts regenerated (Baird's existing
  decisions preserved).
- `docs/sops/data_fill.md` §5 and `data/source_roster.md` — record that
  shipvault is never a country ref.

## Still failing the gate (advisory, untouched — not shipvault)

`hyundai lng shipping` → hls.co.kr (403, no Wayback body), `sinokor merchant` →
sinokor.co.kr (its **only** ref), `united liquefied gas` → dnb.com. Every one of
those owners except `sinokor merchant` still has a passing ref.

## Apply

Patch path (`apply_patch.csv`, 106 cells over 53 rows) with
`OVERWRITE_NONBLANK=true` — this is a ref-replacement batch (AP §2a).
