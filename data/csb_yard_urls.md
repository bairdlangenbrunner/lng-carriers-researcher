# ChinaShipBuild yard URLs (reference)

These are the stable per-yard URLs verified across multiple sessions. Append them to `http://www.chinashipbuild.com/shipyard.aspx?` if using as templates; the full URLs below are ready to curl.

Use `scripts/csb_fetch.py` rather than curling directly — it handles UA, parsing, and filtering. This file is for quick reference and to confirm a yard slug is known.

## Main LNGC yards (the seven that build essentially all conventional LNGCs)

| Slug | Full name | URL |
|---|---|---|
| `samsung` | Samsung Heavy Industries | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcbganmkhTk8Pl4EN` |
| `hanwha-ocean` | Hanwha Ocean (ex-DSME / Daewoo) | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcJXanmkhTk8Pl4EN` |
| `hyundai-ulsan` | HD Hyundai HI, Ulsan | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbccbanmkhTk8Pl4EN` |
| `hyundai-samho` | HD Hyundai Samho | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbccCanmkhTk8Pl4EN` |
| `hyundai-mipo` | HD Hyundai Mipo | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbccBanmkhTk8Pl4EN` |
| `jiangnan` | Jiangnan Shipyard | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4csFcanmkhTk8Pl4EN` |
| `hudong-zhonghua` | Hudong-Zhonghua Shipbuilding | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4csFXanmkhTk8Pl4EN` |

## Secondary LNGC-capable yards (sweep when user opts for full coverage)

| Slug | Full name | URL |
|---|---|---|
| `dsic-dalian` | Dalian Shipbuilding Industry Co (DSIC) | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4JJgJFanmkhTk8Pl4EN` |
| `mitsubishi-hi` | Mitsubishi HI | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BsXCg` |
| `kawasaki-kobe` | Kawasaki Shipbuilding, Kobe | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BscJg` |
| `zvezda` | Zvezda Shipbuilding (Russia, Arctic LNGCs) | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcBSanmkhTk8Pl4EN` |
| `jmu-tsu` | JMU Tsu | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BscJF` |
| `jmu-ariake` | JMU Ariake | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcXb` |
| `nacks` | Nantong COSCO KHI (NACKS) | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcFcanmkhTk8Pl4EN` |
| `dacks` | Dalian COSCO KHI (DACKS) | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcJFanmkhTk8Pl4EN` |
| `imabari-marugame` | Imabari Shipbuilding, Marugame | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbccSanmkhTk8Pl4EN` |
| `cosco-yangzhou` | COSCO HI, Yangzhou | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcgSanmkhTk8Pl4EN` |
| `cosco-qidong` | COSCO HI Offshore, Qidong | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcJganmkhTk8Pl4EN` |
| `cosco-dalian` | COSCO HI, Dalian | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcgBanmkhTk8Pl4EN` |
| `cosco-zhoushan` | COSCO HI, Zhoushan | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BsgFFanmkhTk8Pl4EN` |
| `yantai-cimc` | Yantai CIMC Raffles | `http://www.chinashipbuild.com/shipyard.aspx?pklujyukkpp4BbcBBanmkhTk8Pl4EN` |

## Yards worth adding when they show LNGC activity

- **CMHI Haimen (China Merchants HI Jiangsu)** — delivered Celsius Georgetown 27-Apr-2026, first large LNGC delivery. URL not yet pinned to a stable slug; look up via master directory.

## Master directory (when a yard isn't in the table above)

The CSB master directory is paginated (8 pages, 382 yards, alphabetical):

- Page 1: `http://www.chinashipbuild.com/shipyards.aspx`
- Page 2: `http://www.chinashipbuild.com/shipyards.aspx?nmkhTk8Pl4ENaoklppLwi94cgapoljjlSLPHH4c`
- Pages 3-8: same URL ending in `4X`, `4F`, `4b`, `4B`, `4C`, `4s`

## Pagination tokens (within a yard)

Append to the yard URL to get pages beyond p1:
- p2: `aORDERBOOK4c`
- p3: `aORDERBOOK4X`
- p4: `aORDERBOOK4F`
- p5: `aORDERBOOK4b`
- p6: `aORDERBOOK4B`
- p7: `aORDERBOOK4C`
- p8: `aORDERBOOK4s`

## Important behavior note (added 2026-05)

CSB's orderbook list page shows the **yard name** (e.g. "Samsung HI") instead of an actual hull number when the contract is very recent and the hull hasn't been assigned/indexed yet. The `csb_fetch.py` parser tags these rows with `hull_assigned: false`. These rows are still valid signal (contract date, owner, capacity all correct) but Rule A `Hull number [ref]` will need the §6a fallback protocol — the CSB page is not yet sufficient for hull citation.
