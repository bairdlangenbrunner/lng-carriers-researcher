"""
The §5 confidence grade — computed from what the §3.8c gate actually did (RF rev 28).

Baird directive 2026-09-22: a proposal whose `[ref]` survives the gate on a **live**
page, where the page genuinely states that value *for this vessel*, is **Green** —
one source is enough. Confidence stops being a researcher's prose judgment about
source tier ("is a DART filing more primary than Splash247?") and becomes a function
of the gate's own verdict, so the label means the same thing in every batch and a
Green line is one a machine can defend.

    grade(passes, field=..., value=..., caps=[...]) -> ("G" | "Y" | "R", why)

    G   a ref passed the gate on a LIVE fetch and the match is a real statement of
        this cell's value — either a record keyed to the vessel (an IGU report row
        for the row's IMO, a shipvault / marinetraffic unit record) or a value
        distinctive enough that its presence on the page is not a coincidence.
    Y   the value is only carried by an archived snapshot (the live page is walled),
        or it is too generic for a bare text hit to mean anything on its own, or a
        carve-out caps the cell.
    R   nothing survived the gate.

The carve-outs, all of which cap at Y and none of which can raise a cell:

  - **RF §4.18** a delivery roll-forward wants a second source — one live pass is Y.
  - **DF §5a** a per-vessel Price divided out of an order total: the page states the
    total, not the number in the cell.
  - **§3.8c conflict** another live source states a different value for the cell.
  - **a research note that documents doubt** — a discrepancy, "human review
    recommended", "not confirmed". `cap_reason` is the structured form; prose from
    batches that predate it is honoured too (`note_cap`).
  - **`cap` / `cap_reason` on the proposal** — the researcher's own documented doubt
    (a paywalled entity tag under §3.8b, a source that reads like a repackage).
    A bare `confidence` label is NOT a cap: it is overwritten by the computed grade.

What this deliberately does NOT do: read source tier. A yard press release and a
trade-press article that both state the figure on a live page grade the same. The
old §5 ladder (2 sources, or 1 primary/regulatory) is withdrawn.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

GREEN, YELLOW, RED = "G", "Y", "R"
RANK = {GREEN: 3, YELLOW: 2, RED: 1}

# Standard carve-out texts (the `why` a reviewer reads next to a held line).
CAP_DERIVED = "DF §5a: the source states the order total, not this per-vessel price"
CAP_ROLL_FORWARD = "RF §4.18: a delivery roll-forward wants a source besides the vessel database"
CAP_CONFLICT = "§3.8c: another live source states a different value for this cell"

# A pass whose reason carries one of these came from a record keyed to THIS vessel,
# not from a string sitting somewhere on a page: the IGU coordinate extraction looked
# the row's IMO up (igu_refs), and the tracker adapters verified the page against the
# unit record it loads (url_verifier._adapter_for).
_KEYED_MARKS = ("coordinate extraction", "shipvault_api", "marinetraffic_api")
_ARCHIVE_MARK = "via wayback"
# `corroborates()` passes a blank value trivially — that is not evidence of anything.
_EMPTY_MARKS = ("no value to corroborate",)

# Columns whose values are drawn from a tiny vocabulary or a country list: the string
# is on half the pages on the internet, so a bare text match never proves it was
# printed for this vessel. (Yard location columns are mirrored, never researched.)
GENERIC_FIELDS = {"Status", "Cargo type", "Vessel type", "Propulsion type",
                  "Capacity units", "Price currency", "Delivery delayed",
                  "Shipowner country/area", "Shipbuilder yard country/area"}


def field_of(column: str) -> str:
    """The backend header with any ' [ref]' suffix stripped."""
    return re.sub(r"\s*\[ref\]\s*$", "", str(column or "")).strip()


def pass_kind(reason: str) -> str | None:
    """How a ref passed: 'live_keyed' | 'live_text' | 'archive' | None (not evidence).

    `reason` is what `url_verifier.corroborates` / `igu_refs.corroborates_cell`
    returned alongside ok=True. Only call this for refs that passed.
    """
    r = (reason or "").strip().lower()
    if any(m in r for m in _EMPTY_MARKS):
        return None
    if _ARCHIVE_MARK in r:
        return "archive"
    if any(m in r for m in _KEYED_MARKS):
        return "live_keyed"
    return "live_text"


# A companion ref is the same source as the ref it sits beside, on a different host:
# the shipvault unit record (RF §6a.8 rev 21) is what the shipvault page itself loads.
# Folding it back onto the page's host keeps it from reading as a second independent
# source where a carve-out asks for one (RF §4.18).
_HOST_ALIASES: dict[str, str] = {}


def _host_aliases() -> dict:
    if not _HOST_ALIASES:
        api = "https://shipvaultapi-gjb8c.ondigitalocean.app/api/units/{id}"
        try:
            from url_verifier import SHIPVAULT_API as api
        except Exception:
            pass
        _HOST_ALIASES[(urlsplit(api).hostname or "").lower()] = "shipvault.com"
    return _HOST_ALIASES


def _host(url: str) -> str:
    h = (urlsplit(str(url or "")).hostname or "").lower()
    h = h[4:] if h.startswith("www.") else h
    return _host_aliases().get(h, h)


def live_hosts(passes) -> set:
    """Distinct hosts among the refs that passed on a live fetch."""
    return {_host(u) for u, r in passes if pass_kind(r) in ("live_keyed", "live_text") and _host(u)}


def _is_vocab_token(field: str, value: str) -> bool:
    try:
        from lookups import CONTROLLED_VOCAB
    except Exception:
        return False
    vocab = CONTROLLED_VOCAB.get(field) or ()
    return any(str(value).strip().lower() == str(v).strip().lower() for v in vocab)


def distinctive(field: str, value) -> bool:
    """Is this value specific enough that finding it on a page means it is THIS cell's?

    A capacity (`174000`), a price, a vessel name, a hull number, a contract date: yes.
    A bare year, a country, a one-word controlled-vocabulary token, a three-letter
    owner acronym: no — those need a keyed record or a second independent page.
    """
    v = str(value or "").strip()
    f = field_of(field)
    if not v:
        return False
    if f in GENERIC_FIELDS or f.startswith("Yard location"):
        return False
    if _is_vocab_token(f, v):
        return False
    if re.fullmatch(r"(19|20)\d{2}", v):        # a bare year — on every dated page
        return False
    if re.fullmatch(r"[\d,.\s]+", v):           # a pure figure: 4+ digits to be specific
        return len(re.sub(r"\D", "", v)) >= 4
    return len(re.sub(r"[^A-Za-z0-9]", "", v)) >= 5


# A research note that documents the researcher's own doubt. `cap_reason` is the
# structured way to say this (and what new batches use), but notes predating it carry
# the same argument in prose, and a documented discrepancy must not grade Green.
_NOTE_DOUBT = re.compile(
    r"discrepan|contradic|disagree(s|ment)?\b|conflicting|human review|"
    r"review recommended|needs? (human )?(review|confirmation)|not confirmed|unconfirmed",
    re.I)


def note_cap(note) -> str | None:
    """A cap drawn from a research note that documents doubt, or None."""
    m = _NOTE_DOUBT.search(str(note or ""))
    return (f"the research note documents doubt ({m.group(0).strip().lower()}) — "
            f"read it before accepting") if m else None


def rolls_forward(new_value, former_year) -> bool:
    """RF §4.18: is this Delivery year cell moving the schedule LATER?"""
    try:
        return int(str(former_year).strip()) < int(str(new_value).strip())
    except (TypeError, ValueError):
        return False


def grade(passes, field: str = "", value="", caps=()) -> tuple[str, str]:
    """(grade, why) for one proposed cell.

    Args:
        passes: [(url, reason), ...] for the refs that PASSED the gate — the reason
                string the gate returned, which says how it passed.
        field:  backend column header (with or without ' [ref]').
        value:  the proposed cell value the refs were gated against.
        caps:   carve-out texts that hold the cell at Y (CAP_* above, or a
                researcher's documented `cap_reason`).
    """
    kinds = [k for k in (pass_kind(r) for _, r in passes) if k]
    if not kinds:
        return RED, "no ref survived the §3.8c gate"
    caps = [c for c in caps if c]
    if caps:
        return YELLOW, "; ".join(caps)
    if "archive" in kinds and not any(k.startswith("live") for k in kinds):
        return YELLOW, "only an archived snapshot carries the value; the live page is walled (§3.8a)"
    if "live_keyed" in kinds:
        return GREEN, "a live record keyed to this vessel states the value"
    if distinctive(field, value):
        return GREEN, "a live page states the value (§3.8c) and the value is specific to this cell"
    hosts = live_hosts(passes)
    if len(hosts) >= 2:
        return GREEN, f"{len(hosts)} independent live pages state the value"
    return YELLOW, (f"{str(value)!r} is generic — one bare text match does not show it was "
                    f"printed for this vessel; wants a keyed record or a second source")
