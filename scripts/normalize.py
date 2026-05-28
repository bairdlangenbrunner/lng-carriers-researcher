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
