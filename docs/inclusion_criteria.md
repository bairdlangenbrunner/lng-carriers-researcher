# Inclusion criteria

## In scope

The LNG Carrier Tracker focuses on **conventional LNG carriers** specifically involved in transporting or regasifying LNG in global LNG trade, including **Floating Storage and Regasification Units (FSRUs)**.

## Out of scope

- **Floating Storage Units (FSUs)** — LNG carriers that have been converted to permanent floating storage at terminals
- **Small-scale and mid-scale LNG carriers** — vessels involved in short-haul delivery
- **LNG bunkering vessels** — vessels that supply LNG fuel to other ships
- **Domestic-only ships** — vessels that never operate in international trade
- **Vessels cancelled or decommissioned prior to December 2025** — these are not *added*. A row
  already in the tracker is never deleted: a vessel that is scrapped keeps its row and moves to
  Status `scrapped`, whenever the scrapping happened (decision 2026-09-17).

## Status categories

### Proposed

A new vessel has been announced by a shipping company or charterer, with public sources to support the announcement. A binding contract with a shipyard has not been signed, and financing may not be finalized.

These ships are included in the IGU orderbook. Our research determines whether a contract has been signed between a ship owner and a shipyard, which would move the vessel to "on order."

### On order

A vessel has a binding shipbuilding contract between a ship owner and a shipyard. This typically includes:

- A signed contract
- A delivery year
- A hull number assigned by the shipyard

### Active

An LNG carrier has been built, delivered, and is operable. The majority of these ships are operational, but some may not be sailing — they could be idle, under repair, or in another non-operational state. We do not distinguish among these substatuses; all are considered technically active.

### Scrapped

A vessel that was in the tracker and has been sold for demolition or broken up. The row stays —
rows are never deleted from the tracker — and the Status moves from `active` to `scrapped`, with a
verified reference for the demolition sale. Converted vessels (FSU / FSRU) are a Vessel-type
change, not a scrapping.

## Sources and methodology

The tracker relies entirely on **publicly-accessible data**. The foundation is the **International Gas Union (IGU) World LNG Report**, released annually, which catalogues active and on-order LNG carriers.

GEM and SFOC contribute additional data — vessels, updated statuses, and other fields — derived from industry news and publicly available contracts. These additions are integrated into the tracker along with any new IGU data on a **quarterly basis**.

The first release of the tracker was **December 2025**.

See [docs/sops/](sops/) for the operational procedures used to maintain the tracker.
