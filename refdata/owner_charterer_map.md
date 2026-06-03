# Owner / charterer canonical names and variants

Authoritative version: the `_OWNER_MAP` dict in `scripts/normalize.py`. This file is the human-readable reference for what canonical tags exist and which variants resolve to each.

When you encounter a new owner/charterer in a batch, add it to `normalize.py` AND to this table.

## Display stylization (how the name is written in the sheet)

Two different things live here:
- the **canonical tag** (lowercase, e.g. `cosco-shipping-energy`) used only for clustering / dedup, and
- the **display form** — the exact string written into the backend's `Shipowner` / `Operator/charterer` cells.

Per [ref]-Fill SOP §4.14, the display form must **match the backend's existing stylization**, preferring the established **short** form. When the backend already uses a short name, use it; don't introduce a longer legal name. Display forms are recorded in `scripts/normalize.py` (`_OWNER_DISPLAY`, returned by `display_owner()`); this map only needs entries for owners the backend abbreviates.

| Canonical tag | Backend display form | Notes |
|---|---|---|
| `cosco-shipping-energy` | **`COSCO`** | Backend writes `COSCO` / `MOL, COSCO`; do NOT write `Cosco Shipping Energy Transportation`. |

## Why this matters

Cluster-coherence checks (Rule E §4.12) and the dedup index both rely on canonical owner names. "Eastern Pacific Shipping" and "EPS" must resolve to the same tag, otherwise:
- Discovery dedup misses backend rows that already cover the cluster
- Trade-press URLs get cited for the wrong cluster

## Canonical tags (key) → known variants (value)

### Greek shipowners

| Canonical | Variants seen |
|---|---|
| `maran-gas` | Maran Gas Maritime, Maran Gas, Angelicoussis (parent group) |
| `alpha-gas` | Alpha Gas, Alpha Tankers |
| `tsakos` | Tsakos Energy, Tsakos Group, TEN |
| `tms-cardiff` | TMS Cardiff Gas, TMS Cardiff |
| `dynagas` | Dynagas Ltd |

### Singapore / Asian

| Canonical | Variants seen |
|---|---|
| `eps` | Eastern Pacific Shipping |

### Norwegian / Danish

| Canonical | Variants seen |
|---|---|
| `knutsen` | Knutsen OAS, Knutsen Group |
| `celsius` | Celsius Shipping, Celsius Tankers |
| `cool-co` | Cool Company, Cool Co |
| `bw-lng` | BW LNG, BW Group |

### UK / US

| Canonical | Variants seen |
|---|---|
| `purus` | Purus Marine, Purus Marine Services Ltd |
| `hayfin` | Hayfin Capital Management, Hayfin Capital |
| `seapeak` | Seapeak |
| `stonepeak` | Stonepeak |
| `capital` | Capital Gas, Capital Product Partners, Capital Clean Energy, Capital Clean ECC |

### Africa

| Canonical | Variants seen |
|---|---|
| `sonangol` | Sonangol, Sonangol EP |
| `bgt` | Bonny Gas Transport, BGT (Nigeria LNG affiliate) |

### Asian state-linked

| Canonical | Variants seen |
|---|---|
| `misc` | MISC Berhad, MISC Bhd, Malaysia Int Shpg (Petronas subsidiary) |
| `qatargas` | QatarGas |
| `nakilat` | Nakilat (Qatar Gas Transport) |
| `shandong-marine` | Shandong Marine |
| `cosco-shipping-energy` | COSCO Shipping Energy, Cosco Shipping Energy Transportation, CSET — **write as `COSCO`** (see Display stylization) |
| `china-merchants-energy` | China Merchants Energy (Shipping) |
| `minsheng` | Minsheng Financial Leasing |

### Japanese

| Canonical | Variants seen |
|---|---|
| `nyk` | NYK Line, NYK |
| `mol` | Mitsui OSK Lines, MOL |
| `k-line` | K-Line, Kawasaki Kisen Kaisha |

### Charterers (operator side)

| Canonical | Variants seen |
|---|---|
| `cheniere` | Cheniere |
| `venture-global` | Venture Global LNG |
| `qatarenergy` | QatarEnergy |
| `shell` | Shell |
| `bp` | BP |
| `totalenergies` | TotalEnergies |
| `woodside` | Woodside |
| `adnoc` | ADNOC, ADNOC LNG |
| `nextdecade` | NextDecade |

### Other

| Canonical | Variants seen |
|---|---|
| `glovis` | Hyundai Glovis, Glovis |
| `oceonix` | Oceonix Services |
| `itochu` | Itochu |
| `one` | Ocean Network Express |

## DART regional-euphemism decoder

DART filings disclose counterparties by region rather than name. Common patterns observed:

| DART phrasing | Often (but not always) actually... |
|---|---|
| "Oceania-region shipowner" | TMS Cardiff, Hayfin, or another Greek/UK-managed entity on Marshall Islands / Bermuda flag |
| "Americas-region shipowner" | Cheniere-related charter co, NextDecade-linked, or a US-listed owner like Capital |
| "Asia-region shipowner" | MISC, COSCO, NYK, MOL, K-Line, or a Singapore-flagged Greek operator |
| "Europe-region shipowner" | Knutsen, Maran Gas via Greek registry, Cool Co, BW |

Always cross-check with TradeWinds / Splash247 / Riviera shipbroker attribution before treating the actual buyer as confirmed. The pattern is consistent enough to seed a hypothesis but not authoritative on its own.
