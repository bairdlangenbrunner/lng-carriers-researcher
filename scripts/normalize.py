"""
Canonical name normalization for builders (shipyards) and owners.

Used by dedup_index.py, csb_fetch.py, and build_workbook.py to make cluster
matching consistent across batches. Without this, "Samsung HI" vs "Samsung
Heavy Industries" vs "SHI" would be treated as three different yards, and
cluster-coherence checks (Rule E) would over- or under-merge.

The mappings are conservative — only canonicalize where there's no ambiguity.
When a new owner/yard appears in a batch and isn't in the map, add it here
rather than papering over it in the build script.

Returns the canonical short tag (e.g. 'samsung', 'hanwha-ocean', 'misc').
If the input doesn't match any known variant, returns the input lowercased
and stripped — so unknown entities still cluster against themselves.
"""
import re


# Builders / shipyards — canonical tags
# Key: a substring that uniquely identifies the yard (case-insensitive)
# Value: canonical short tag used in indexes and CSB short names
_BUILDER_MAP = {
    # Korean — Samsung
    "samsung heavy industries": "samsung",
    "samsung hi": "samsung",
    "samsung shipbuilding": "samsung",
    "shi geoje": "samsung",
    # Korean — Hanwha Ocean (includes legacy DSME / Daewoo)
    "hanwha ocean": "hanwha-ocean",
    "daewoo shipbuilding": "hanwha-ocean",
    "dsme": "hanwha-ocean",
    "daewoo marine": "hanwha-ocean",
    # Korean — HD Hyundai family
    "hd hyundai heavy industries": "hyundai-ulsan",
    "hyundai heavy industries": "hyundai-ulsan",
    "hd hhi": "hyundai-ulsan",
    "hd hyundai samho": "hyundai-samho",
    "hyundai samho heavy industries": "hyundai-samho",
    "hd hyundai mipo": "hyundai-mipo",
    "hyundai mipo dockyard": "hyundai-mipo",
    "hd kshi": "hd-ksoe",  # HD Korea Shipbuilding & Offshore Engineering (parent)
    "hd korea shipbuilding": "hd-ksoe",
    # Chinese — CSSC family
    "jiangnan shipyard": "jiangnan",
    "hudong-zhonghua shipbuilding": "hudong-zhonghua",
    "hudong zhonghua": "hudong-zhonghua",
    "dalian shipbuilding industry": "dsic",
    "dalian shipbuilding": "dsic",
    "dsic": "dsic",
    # Chinese — CMHI
    "china merchants heavy industries": "cmhi",
    "cmhi haimen": "cmhi",
    "cmhi jiangsu": "cmhi",
    # Chinese — COSCO family
    "nantong cosco khi": "nacks",
    "dalian cosco khi": "dacks",
    "cosco shipping heavy industries (yangzhou)": "cosco-yangzhou",
    "cosco hi, yangzhou": "cosco-yangzhou",
    "cosco hi, qidong": "cosco-qidong",
    "cosco hi, dalian": "cosco-dalian",
    "cosco hi, zhoushan": "cosco-zhoushan",
    # Chinese — Yantai CIMC
    "yantai cimc raffles": "yantai-cimc",
    # Japanese
    "mitsubishi heavy industries": "mitsubishi",
    "mitsubishi hi": "mitsubishi",
    "kawasaki shipbuilding": "kawasaki",
    "imabari shipbuilding": "imabari",
    "japan marine united": "jmu",
    "jmu tsu": "jmu-tsu",
    "jmu ariake": "jmu-ariake",
    # Russian
    "zvezda shipbuilding": "zvezda",
}


# Owners / charterers — canonical tags
_OWNER_MAP = {
    # Greek shipowners
    "maran gas maritime": "maran-gas",
    "maran gas": "maran-gas",
    "angelicoussis": "maran-gas",
    "alpha gas": "alpha-gas",
    "alpha tankers": "alpha-gas",
    "tsakos energy": "tsakos",
    "tsakos group": "tsakos",
    "tms cardiff gas": "tms-cardiff",
    "tms cardiff": "tms-cardiff",
    "dynagas": "dynagas",
    "capital gas": "capital",
    "capital product partners": "capital",
    "capital clean energy": "capital",
    "capital clean ecc": "capital",
    # Singapore / Asian
    "eastern pacific shipping": "eps",
    "ocean network express": "one",
    # Norwegian / Danish
    "knutsen oas": "knutsen",
    "knutsen group": "knutsen",
    "celsius shipping": "celsius",
    "celsius tankers": "celsius",
    "cool company": "cool-co",
    "cool co": "cool-co",
    "bw lng": "bw-lng",
    "bw group": "bw-lng",
    # UK / US
    "purus marine": "purus",
    "purus marine services": "purus",
    "hayfin capital": "hayfin",
    "seapeak": "seapeak",
    "stonepeak": "stonepeak",
    # Africa
    "sonangol": "sonangol",
    "bonny gas transport": "bgt",
    "bgt": "bgt",
    # Asian state-linked
    "misc berhad": "misc",
    "misc bhd": "misc",
    "malaysia int shpg": "misc",
    "qatargas": "qatargas",
    "nakilat": "nakilat",
    "shandong marine": "shandong-marine",
    "cosco shipping energy": "cosco-shipping-energy",
    "china merchants energy": "china-merchants-energy",
    "minsheng financial leasing": "minsheng",
    # Japanese
    "nyk line": "nyk",
    "nyk": "nyk",
    "mitsui osk lines": "mol",
    "mol": "mol",
    "k-line": "k-line",
    "kawasaki kisen kaisha": "k-line",
    # Charterers (operator side, sometimes also appear as Shipowner via charter affiliate)
    "cheniere": "cheniere",
    "venture global lng": "venture-global",
    "qatarenergy": "qatarenergy",
    "shell": "shell",
    "bp": "bp",
    "totalenergies": "totalenergies",
    "woodside": "woodside",
    "adnoc": "adnoc",
    "nextdecade": "nextdecade",
    # Other
    "hyundai glovis": "glovis",
    "glovis": "glovis",
    "oceonix services": "oceonix",
    "itochu": "itochu",
}


# Preferred display forms — the exact string to WRITE into the backend's
# Shipowner / Operator/charterer cells, keyed by canonical owner tag. Per
# [ref]-Fill SOP §4.14, match the backend's existing stylization and prefer the
# established short form. Seed entries as a stylization is settled; an owner
# absent here is written as researched (display_owner returns the input
# unchanged), so this map only needs the ones the backend abbreviates.
_OWNER_DISPLAY = {
    "cosco-shipping-energy": "COSCO",
}


# Seeded owner -> Shipowner country/area, for the data-fill derivable autofill
# (Data-fill SOP §5) when an owner has NO sibling row in the backend to copy a
# country from. Populated as owner countries settle (sourced), parallel to
# _OWNER_DISPLAY. Sibling-copy (see owner_country) is preferred when available.
_OWNER_COUNTRY = {}


def _normalize_input(s: str) -> str:
    """Lowercase, strip, collapse whitespace, remove parenthetical content."""
    if s is None:
        return ""
    s = str(s).lower().strip()
    # Remove parenthetical content like "(Hudong)" or "(Chinese name)"
    s = re.sub(r"\([^)]*\)", "", s).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_builder(s: str) -> str:
    """Return canonical builder tag. Unknown inputs returned lowercased/stripped."""
    norm = _normalize_input(s)
    if not norm:
        return ""
    # Try exact prefix match first, then substring match
    for key, tag in _BUILDER_MAP.items():
        if norm.startswith(key) or key in norm:
            return tag
    return norm


def normalize_owner(s: str) -> str:
    """Return canonical owner tag. Unknown inputs returned lowercased/stripped."""
    norm = _normalize_input(s)
    if not norm:
        return ""
    for key, tag in _OWNER_MAP.items():
        if norm.startswith(key) or key in norm:
            return tag
    return norm


def display_owner(s: str) -> str:
    """Return the preferred backend display string for an owner/charterer.

    Looks up the canonical tag in _OWNER_DISPLAY; if a short form is settled
    (e.g. 'COSCO'), returns it, otherwise returns the input unchanged. Per
    [ref]-Fill SOP §4.14 — match the backend's existing stylization.
    """
    return _OWNER_DISPLAY.get(normalize_owner(s), s)


def owner_country(owner_raw, backend_data=None, owner_idx=None, country_idx=None):
    """Preferred Shipowner country/area for an owner (Data-fill SOP §5).

    1. If a seeded value exists in _OWNER_COUNTRY, return it.
    2. Else, if backend_data + the Shipowner / country column indices are given,
       return the UNAMBIGUOUS country shared by every sibling backend row of the
       same normalized owner. Returns None if siblings disagree (e.g. 'mol' has
       Japan + Türkiye; 'maran-gas' has multiple) or none carry a country — those
       cases must be researched, never sibling-autofilled.
    """
    tag = normalize_owner(owner_raw)
    if tag in _OWNER_COUNTRY:
        return _OWNER_COUNTRY[tag]
    if backend_data is None or owner_idx is None or country_idx is None:
        return None
    seen = set()
    for r in backend_data:
        if len(r) > max(owner_idx, country_idx) and normalize_owner(r[owner_idx]) == tag:
            v = r[country_idx].strip()
            if v:
                seen.add(v)
    return next(iter(seen)) if len(seen) == 1 else None


def normalize_hull(builder_tag: str, hull_raw: str) -> str:
    """
    Canonicalize a hull string within a builder context.

    CSB and the backend use slightly different conventions per yard:
      Samsung: "Samsung 2775" / "Samsung HI Geoje 2775" / "2775" → all → "2775"
      Hanwha Ocean: "Hanwha Ocean 2623" / "2623" → "2623"
      Hyundai Samho: "Hyundai Samho H8340" / "H8340" / "8340" → "h8340"
      Jiangnan: "Jiangnan H2950" / "H2950" → "h2950"
      Hudong-Zhonghua: "Hudong H2014A" / "H2014A" → "h2014a"

    Returns lowercased hull with yard prefix stripped where unambiguous.
    """
    if hull_raw is None:
        return ""
    h = str(hull_raw).strip().lower()
    if not h:
        return ""
    # Strip known yard-name prefixes
    prefixes = [
        "samsung hi geoje ", "samsung hi ", "samsung ",
        "hanwha ocean ", "hanwha ",
        "hd hyundai samho ", "hyundai samho ", "samho ",
        "hd hyundai ulsan ", "hyundai ulsan ", "ulsan ", "hhi ",
        "hd hyundai mipo ", "hyundai mipo ", "mipo ",
        "jiangnan ", "hudong-zhonghua ", "hudong ",
        "dsic ", "cmhi ",
    ]
    for p in prefixes:
        if h.startswith(p):
            h = h[len(p):]
            break
    return h.strip()


# --- Vessel-name normalization (FSRU reconciliation, Phase A) ------------------
# Used by fsru_reconcile.py to join the GIIGNL FSRU fleet table (no IMO column)
# to the backend on vessel name. The join keys on {current name} ∪ {ex_names}, so
# this only needs to collapse cosmetic noise — diacritics (GIIGNL "Höegh" vs
# backend "Hoegh"), "(ex …)"/"(MISC FSRU)" parentheticals, case, whitespace. It
# deliberately does NOT rewrite owner rebrands (Golar→Energos, Transgas→Energos):
# GIIGNL supplies the former name as an ex_name, so the name union already bridges
# a rebrand without a fragile rewrite table. New, additive — the existing
# builder/owner normalizers are untouched.
import unicodedata


def _strip_diacritics(s: str) -> str:
    """Fold accented letters to ASCII: 'Höegh' -> 'Hoegh', 'Türkiye' -> 'Turkiye'."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize_vessel_name(s: str) -> str:
    """Canonical key for matching a vessel name across GIIGNL and the backend.

    Lowercase, fold diacritics, drop parenthetical content ('(ex …)', '(MISC
    FSRU)'), strip surrounding quotes/punctuation, collapse whitespace. Empty in
    -> empty out. Conservative: it does not strip 'FSRU'/'LNG' tokens or rewrite
    rebrands, so distinct vessels stay distinct.
    """
    if not s:
        return ""
    s = _strip_diacritics(str(s)).lower()
    s = re.sub(r"\([^)]*\)", " ", s)          # remove (ex …) / (MISC FSRU) etc.
    s = re.sub(r"[\"'`]", "", s)               # drop stray quotes
    s = re.sub(r"\s+", " ", s).strip()
    return s


# FSRU owner / lessor aliases — collapse the many stylings GIIGNL and the backend
# use for the same lessor so an owner DIFF in the reconciliation means a real
# disagreement, not "Energos Inf." vs "Energos". Substring match, lowercased.
# Kept SEPARATE from _OWNER_MAP / normalize_owner so the shared toolchain
# (dedup, data-fill autofill, qc facts) is unaffected. Resolution is per-token
# (callers split multi-owner cells like "Karpowership, MOL" on commas first).
_FSRU_OWNER_ALIASES = {
    "energos": "energos",
    "hoegh": "hoegh",                 # diacritics already folded before lookup
    "karmol": "karmol",
    "karpowership": "karmol",
    "snam": "snam",
    "excelerate": "excelerate",
    "mitsui osk": "mol",
    "mol": "mol",
    "bw lng": "bw", "bw ": "bw", "bw,": "bw",
    "swan energy": "swan",
    "exmar": "exmar",
    "gazprom": "gazprom",
    "botas": "botas",
    "gaslog": "gaslog",
    "klaipedos": "klaipedos-nafta",
    "lng hrvatska": "lng-croatia", "lng croatia": "lng-croatia",
}


def fsru_owner_tags(raw: str) -> set:
    """Set of canonical owner tags from a (possibly multi-owner) owner cell.

    Splits on comma / '&' / '/' so 'Karpowership, MOL' -> {'karmol', 'mol'} and
    'Hoegh, MOL, TLTC' -> {'hoegh', 'mol', 'tltc'}. Each piece resolves through
    _FSRU_OWNER_ALIASES (substring), else falls back to its own cleaned text so
    unknown owners still compare against themselves. Used for the advisory owner
    diff only — never to make a join decision.
    """
    if not raw:
        return set()
    base = _strip_diacritics(str(raw)).lower()
    tags = set()
    for piece in re.split(r"[,/&]| and ", base):
        p = re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", " ", piece)).strip()
        if not p:
            continue
        tag = next((t for k, t in _FSRU_OWNER_ALIASES.items() if k in p), p)
        tags.add(tag)
    return tags


def main():
    """CLI smoke test."""
    samples = [
        ("Samsung Heavy Industries", "Maran Gas Maritime", "Samsung 2775"),
        ("Hanwha Ocean", "Knutsen OAS Shipping", "Hanwha Ocean 2623"),
        ("HD Hyundai Samho", "BW LNG", "Hyundai Samho H8340"),
        ("Jiangnan Shipyard", "Eastern Pacific Shipping", "Jiangnan H2950"),
        ("DSME", "Bonny Gas Transport (Nigeria LNG)", "5042"),
    ]
    for b, o, h in samples:
        print(f"  builder={b!r:35} -> {normalize_builder(b)}")
        print(f"  owner=  {o!r:35} -> {normalize_owner(o)}")
        print(f"  hull=   {h!r:35} -> {normalize_hull(normalize_builder(b), h)}")
        print()


if __name__ == "__main__":
    main()
