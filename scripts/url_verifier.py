"""
URL verification harness for the LNG Carrier Tracker [ref]-fill workflow.

Per [ref]-Fill SOP §3.8 / Rule D §4.11: every URL cited in a [ref] cell MUST be
verified to (1) return HTTP 200, AND (2) contain the entities it's cited for,
AND (3) not be a soft-error page (200 with "404"/"429"/etc. in the title).

Rev 2026-09-16 (ported from the pipelines- / lng-terminals-researcher
verifiers, which pulled ahead of this one over the summer):

  * Blocklist enforced in CODE, not just in the SOP: GEM hosts (circular),
    abarrelfull / wikidot / theodora / yingdodo (banned aggregators), URL
    shorteners (opaque; `maps.app.goo.gl` is exempt — it's Google's own maps
    deep link and the backend's yard-location refs use it), the Wayback
    `/save/` endpoint (a side-effecting capture URL, never a citation), and
    non-citation URL SHAPES (search-result pages, tag/category/author
    listings, paginated indexes). Reason prefix: `banned`.
  * Redirect chains are re-checked: a URL that 30x's onto a banned host, or
    from a deep path to the site root, fails.
  * Bot-block ≠ dead (Update SOP §7.2 in the terminals repo). HTTP 401/403/
    429/5xx and 200-interstitials (Cloudflare "Just a moment", Incapsula,
    PerimeterX, Akamai, paywall / SSO titles, multi-language "access denied"
    bodies) are `blocked`, not dead. For blocked pages the verifier tries a
    Wayback snapshot (availability API, then CDX) and, if the SNAPSHOT
    carries the expected content, passes with reason "OK (via Wayback ...)".
    The LIVE URL stays the citation — never rewrite a ref to a snapshot URL.
    Reason prefix for the unrecoverable case: `blocked`.
  * PDFs are verified on their extracted text (see fetch.fetch_page), so a
    DART / Bursa / class-society PDF passes on the figures it actually shows.
  * Matching is whitespace-normalised, diacritic-folded (NFKD), markup-
    stripped, and entity-decoded; numeric needles must sit on digit
    boundaries ("174,000" no longer matches "1,174,000"; "2026" no longer
    matches "20261").
  * A JSONL audit log of every verdict is written when `URL_VERIFIER_LOG` is
    set (or `--log PATH`); the batch's notes.md can cite it.

Graded reasons — callers classify with `classify(reason)`:
    "OK" / "OK (...)"      -> ok            keep
    "banned: ..."          -> banned        drop everywhere, never retry
    "HTTP 404" / "HTTP 000 (no Wayback snapshot)" / "soft-error page (...)"
                           -> dead          drop everywhere (§3.8a: env blocks
                                            are NOT in this class any more)
    "blocked: ..."         -> blocked       cannot verify; do not treat as dead
                                            (retry later / human confirm)
    "missing expected ..." / "page does not contain value ..."
                           -> uncorroborated  live page lacks the value
                                            (§3.8c hard-block; conflict finding)

Two modes:
  - strict=True: raises CitationError on failure (use in build scripts where
    a broken URL is a hard error)
  - strict=False: returns (False, reason) — caller drops the URL from the
    citation bundle silently (use for best-effort propagation)

A per-process cache prevents re-fetching the same URL multiple times in one
build. The cache is in-memory only — clear between builds. Tests seed it with
plain `(status, body)` tuples; live runs store `fetch.Page` objects.

CLI usage:
    python url_verifier.py <url> <expected1> [<expected2> ...]
    # exits 0 if URL passes, 1 if not
    python url_verifier.py --value <value> <url>
    # corroboration gate: exits 0 iff the page actually contains <value>
    python url_verifier.py --check <url>
    # health only (no content): prints the graded verdict ok/blocked/dead/banned

Library usage:
    from url_verifier import verify_url, verify_and_format, corroborates, classify
    ok, reason = verify_url("https://...", ["Owner Name", "Yard Name", "174,000"])
    ok, reason = corroborates("https://...", "180000")
    url_or_none = verify_and_format(url, expected)  # None if failed
    info = check_url(url)   # {"verdict": "ok"|"blocked"|"dead"|"banned", ...}
"""
import argparse
import html as _html
import json
import os
import random
import re
import sys
import time
import unicodedata
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import quote, urlsplit

from fetch import CHROME_UA as _DEFAULT_UA
from fetch import Page, fetch_page


class CitationError(Exception):
    pass


# Per-process cache so the same URL isn't re-fetched within a build.
# Values are fetch.Page objects, or legacy (status, body) tuples seeded by tests.
_CACHE: dict[str, "Page | tuple[str, str]"] = {}

# Wayback fallback can be disabled (CLI --no-wayback, or offline tests).
WAYBACK_ENABLED = True
# Polite spacing between live fetches (seconds); 0 in tests. The rot sweep
# sets this via --delay.
FETCH_DELAY = 0.0
# Per-host floor between live fetches, on top of FETCH_DELAY: a gate run over a
# batch asks one host (shipvault, a tracker, a press site) many times in a row.
# Hosts in sweep.HOST_DELAYS (trackers, bloomberg.com) get their slower floor.
# 0 disables (tests).
HOST_MIN_GAP = 2.0
_LAST_FETCH: dict[str, float] = {}
# Wayback API 429/5xx: retry this many times after WAYBACK_RETRY_DELAY seconds
# (the availability API rate-limits a long sweep; a 429 is NOT "no snapshot").
WAYBACK_RETRIES = 1
WAYBACK_RETRY_DELAY = 10.0
_WB_RETRY_STATUSES = {"000", "429", "500", "502", "503", "504"}

# ---------------------------------------------------------------------------
# Blocklists — the SOP's Forbidden lists, enforced in code
# ---------------------------------------------------------------------------

# GEM is downstream of this tracker: citing it is circular (RF §4.2).
GEM_HOSTS = ("gem.wiki", "globalenergymonitor.org", "globalenergymonitor.com",
             "gemwiki.org")
# Banned outright, even corroborated (Baird directive 2026-07-17 + roster).
BLOCKLIST_HOSTS = ("abarrelfull.wikidot.com", "abarrelfull.co.uk", "wikidot.com",
                   "theodora.com", "yingdodo.com")
# Opaque redirectors: a citation must name its destination. maps.app.goo.gl is
# NOT a shortener in this sense — it is Google Maps' own share link and the
# backend's `Yard location [ref]` cells use it; the verifier follows it and
# insists the destination is google.com/maps.
SHORTENER_HOSTS = ("bit.ly", "t.co", "tinyurl.com", "goo.gl", "ow.ly", "buff.ly",
                   "lnkd.in", "is.gd", "shorturl.at", "rb.gy", "cutt.ly", "tiny.cc",
                   "t.ly", "bl.ink", "rebrand.ly", "s.id", "urlz.fr", "dlvr.it",
                   "trib.al", "ift.tt", "fb.me", "wp.me", "youtu.be")
SHORTENER_EXEMPT = ("maps.app.goo.gl",)

# URL shapes that are navigation, not evidence: a search results page, a tag /
# category / author listing, page N of an index. The specific article must be
# cited instead. Google Maps place URLs carry `?q=`-free paths so are unaffected.
_NON_CITATION_RE = re.compile(
    r"(?:^|/)(?:search|suche|recherche|busca|buscar|results?)(?:/|\?|$)"
    r"|[?&](?:q|query|s|search|keyword|keywords|kw)=[^&]"
    r"|/(?:tag|tags|category|categories|topic|topics|author|authors|label)/[^/?#]+/?(?:$|\?)"
    r"|/page/\d+/?(?:$|\?)"
    r"|[?&](?:page|paged|p)=\d+(?:$|&)",
    re.I,
)
_WAYBACK_SAVE_RE = re.compile(r"^https?://web\.archive\.org/save/", re.I)
_WAYBACK_SNAPSHOT_RE = re.compile(r"^https?://web\.archive\.org/web/(\d{4,14})(?:[a-z]{2}_)?/(.+)$", re.I)

# ---------------------------------------------------------------------------
# Soft-error / bot-block signals
# ---------------------------------------------------------------------------

# Title fragments meaning "this 200 is really an error page" (dead class).
_SOFT_ERROR_TITLES = (
    "404", "410",
    "not found", "page not found", "page cannot be found", "page doesn't exist",
    "page does not exist", "no longer available", "has been removed",
    "article not available", "content not available",
    "temporarily unavailable", "service unavailable",
    "500 ", "502 ", "503", "504 ", "internal server error", "bad gateway",
    "gateway time", "something went wrong", "error page", "an error occurred",
    "error 4", "error 5",
)
# Title fragments meaning "a bot wall / rate limit / paywall / SSO stands
# between us and the content" (blocked class -> Wayback fallback).
_BOT_BLOCK_TITLES = (
    "429", "403", "401",
    "too many requests", "rate limit",
    "access denied", "forbidden", "access to this page has been denied",
    "just a moment",          # Cloudflare interstitial
    "attention required",     # Cloudflare block
    "checking your browser", "verify you are human", "are you a robot",
    "are you human", "human verification", "security check", "captcha",
    "request blocked", "blocked", "bot detection", "pardon our interruption",
    "please wait", "one moment", "redirecting",
    "sign in", "log in", "login", "signin", "subscribe to continue",
    "subscribe to read", "subscription required", "register to continue",
    "members only", "paywall", "unauthorized", "authentication required",
    "incapsula", "perimeterx", "radware", "imperva", "datadome",
)
# Word-boundary-sensitive titles (would otherwise hit "signs in the market").
_BOT_BLOCK_TITLES_WB = ("sign in", "log in", "login", "signin", "blocked",
                        "forbidden", "captcha", "please wait", "one moment",
                        "redirecting", "unauthorized", "paywall")
# HTTP statuses that mean "blocked / transient", never "gone".
_BOT_BLOCK_STATUSES = {"202", "401", "403", "406", "407", "409", "418", "421", "425",
                       "429", "451", "500", "502", "503", "504", "520", "521",
                       "522", "523", "524", "525", "526", "529", "530"}
# Statuses that really do mean the resource is gone.
_DEAD_STATUSES = {"404", "410", "000", "400", "405", "414"}

# Body markers of a bot wall (checked when the visible body is short, so an
# article that merely mentions Cloudflare doesn't trip it).
_BOT_BLOCK_BODY_MARKERS = (
    "_incapsula_resource", "incapsula incident", "visid_incap",
    "perimeterx", "px-captcha", "_pxappid", "px-cookie",
    "cf-chl", "cf_chl_", "challenge-platform", "cf-browser-verification",
    "cf-error-details", "cf-wrapper", "cloudflare ray id", "ray id:",
    "enable javascript and cookies to continue", "checking if the site connection is secure",
    "verify you are human", "verify that you are human", "are you a human",
    "please verify you are a human", "complete the security check",
    "access denied" , "reference #18.", "errors.edgesuite.net",  # Akamai
    "request unsuccessful", "request blocked", "your request has been blocked",
    "datadome", "captcha-delivery.com", "geo.captcha-delivery.com",
    "radware bot manager", "imperva", "distil networks", "shieldsquare",
    "you have been blocked", "this website is using a security service",
    "automated access to this site has been denied",
    # multi-language block phrases (Chinese / Korean / Japanese sources)
    "访问被拒绝", "访问受限", "拒绝访问", "请开启javascript", "请启用javascript",
    "验证码", "人机验证", "安全验证", "访问过于频繁", "请稍后再试",
    "접근이 거부", "접근 거부", "접근이 제한", "자동 등록 방지", "보안 확인",
    "アクセスが拒否", "アクセスできません", "アクセス制限",
)
_MAX_BOTWALL_BODY = 4000   # visible chars; larger bodies are real pages

# Wayback endpoints (fetched through the same cache so tests can seed them).
_WB_AVAIL = "https://archive.org/wayback/available?url={u}"
_WB_CDX = ("https://web.archive.org/cdx/search/cdx?url={u}&output=json"
           "&fl=timestamp,statuscode&filter=statuscode:200&collapse=digest&limit=-5")
_WB_SNAP = "https://web.archive.org/web/{ts}id_/{u}"

_SEC_UA = "lng-carriers-researcher/1.0 (research; contact via github.com/bairdlangenbrunner)"

# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

_LOG_PATH: str | None = os.environ.get("URL_VERIFIER_LOG") or None


def set_log_path(path: str | None) -> None:
    """Route the JSONL audit log to `path` (None disables)."""
    global _LOG_PATH
    _LOG_PATH = path


def _log(record: dict) -> None:
    if not _LOG_PATH:
        return
    record = {"ts": datetime.now(UTC).isoformat(timespec="seconds"), **record}
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:  # never let logging break a verify
        print(f"  [url_verifier] log write failed: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Fetch (cached)
# ---------------------------------------------------------------------------

def _as_page(v) -> Page:
    if isinstance(v, Page):
        return v
    status, text = v
    return Page(status=str(status), text=text or "")


def _fetch(url: str, timeout: int = 30, ua: str = _DEFAULT_UA,
           headers: dict | None = None) -> Page:
    """Fetch URL (cached per process). Returns a fetch.Page."""
    if url in _CACHE:
        return _as_page(_CACHE[url])
    host = _host(url)
    if host.endswith("sec.gov"):
        ua = _SEC_UA      # sec.gov rejects browser UAs from non-browsers
    if FETCH_DELAY:
        time.sleep(FETCH_DELAY)
    _pace_host(host)
    page = fetch_page(url, timeout=timeout, ua=ua, headers=headers)
    _LAST_FETCH[_pace_key(host)] = time.monotonic()
    _CACHE[url] = page
    return page


def _pace_key(host: str) -> str:
    return host[4:] if host.startswith("www.") else host


def _pace_host(host: str) -> None:
    """Sleep until `host`'s floor since its last live fetch has passed."""
    if not HOST_MIN_GAP:
        return
    from sweep import host_delay          # late import: sweep.py imports fetch too
    key = _pace_key(host)
    gap, jitter = host_delay(key, HOST_MIN_GAP)
    last = _LAST_FETCH.get(key)
    if last is not None:
        wait = last + gap + random.uniform(0, jitter) - time.monotonic()
        if wait > 0:
            time.sleep(wait)


def _fetch_pair(url: str) -> tuple[str, str]:
    p = _fetch(url)
    return p.status, p.text


# ---------------------------------------------------------------------------
# URL-shape checks
# ---------------------------------------------------------------------------

def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def _host_in(host: str, hosts) -> bool:
    return any(host == h or host.endswith("." + h) for h in hosts)


# A report's landing page surfaces no per-vessel value, so it can never pass §3.8c — but the
# report it stands for can (IG §5.4). The backend was seeded from IGU 2025 and cites its
# landing page on thousands of cells: wherever such a ref is a candidate, gate and cite the
# edition's PDF instead. Never skip the landing page and call the cell unsourced.
IGU_PDF = {"2025": "https://www.datocms-assets.com/146580/1763396210-1747916410-igu-world-lng-report-2025.pdf",
           "2026": "https://www.datocms-assets.com/146580/1783403747-igu-world-lng-report-2026.pdf"}
_IGU_LANDING_RE = re.compile(r"^https?://(?:www\.)?igu\.org/igu-reports/(\d{4})-world-lng-report/?(?:[?#].*)?$", re.I)


def citable_form(url: str) -> str:
    """The URL to gate and cite in place of `url`: an IGU landing page -> that edition's
    report PDF; anything else unchanged. Pure — no network."""
    m = _IGU_LANDING_RE.match((url or "").strip())
    return IGU_PDF.get(m.group(1), url) if m else url


def citable_forms(urls) -> list[str]:
    """`citable_form` over a list, order kept, duplicates dropped."""
    return list(dict.fromkeys(citable_form(u) for u in urls))


def url_ban_reason(url: str) -> str | None:
    """Why this URL can never be a citation, or None if its shape is fine.
    Pure — no network. Checked before any fetch."""
    if not re.match(r"^https?://", url or "", re.I):
        return f"banned: not an http(s) URL ({url!r})"
    host = _host(url)
    if _host_in(host, GEM_HOSTS):
        return f"banned: GEM host {host} (circular — GEM is downstream of this tracker)"
    if _host_in(host, BLOCKLIST_HOSTS):
        return f"banned: blocklisted source {host}"
    if _host_in(host, SHORTENER_HOSTS) and not _host_in(host, SHORTENER_EXEMPT):
        return f"banned: URL shortener {host} (cite the destination URL)"
    if _WAYBACK_SAVE_RE.match(url):
        return "banned: web.archive.org/save/ is a capture endpoint, not a citation"
    m = _WAYBACK_SNAPSHOT_RE.match(url)
    target = m.group(2) if m else url
    if m:
        inner = re.sub(r"^https?://", "", target)
        thost = inner.split("/")[0].lower()
        if _host_in(thost, GEM_HOSTS) or _host_in(thost, BLOCKLIST_HOSTS):
            return f"banned: Wayback snapshot of banned host {thost}"
    path_q = urlsplit(target).path + ("?" + urlsplit(target).query if urlsplit(target).query else "")
    if "google." not in host and _NON_CITATION_RE.search(path_q):
        return "banned: navigation URL (search / tag / category / author / paginated index) — cite the article"
    return None


def _redirect_reason(url: str, page: Page) -> str | None:
    """Post-fetch redirect-chain check."""
    final = page.final_url or ""
    if not final or final == url:
        return None
    fhost = _host(final)
    if _host_in(fhost, GEM_HOSTS) or _host_in(fhost, BLOCKLIST_HOSTS):
        return f"banned: redirects to banned host {fhost}"
    if _host_in(_host(url), SHORTENER_EXEMPT) and not (
            fhost.endswith("google.com") or fhost.endswith("goo.gl")):
        return f"banned: maps short link resolved off Google Maps ({fhost})"
    o, f = urlsplit(url), urlsplit(final)
    if o.path.strip("/") and not f.path.strip("/") and not f.query:
        # a deep link that now lands on the homepage: the article is gone.
        return f"soft-error page (redirected to site root {f.scheme}://{fhost}/)"
    # Slug drift: id-keyed CMSs (TradeWinds "…/2-1-1875739", many WordPress
    # sites) resolve by the numeric id and rewrite the slug. If the cited slug
    # and the served slug share almost no words, the cited URL was pointing at
    # a different story than the one that loads — a hallucinated/mis-pasted ref.
    ow, fw = _slug_words(o.path), _slug_words(f.path)
    if len(ow) >= 4 and len(fw) >= 4:
        overlap = len(ow & fw) / len(ow)
        if overlap < 0.25:
            return (f"soft-error page (redirected to a different article: "
                    f"{f.path[:80]})")
    return None


_SLUG_STOP = {"the", "a", "an", "of", "for", "to", "in", "on", "and", "at", "with",
              "news", "article", "articles", "story", "content", "hub", "html", "htm"}


def _slug_words(path: str) -> set[str]:
    words = set()
    for seg in path.split("/"):
        for w in re.findall(r"[a-z]{3,}", seg.lower()):
            if w not in _SLUG_STOP:
                words.add(w)
    return words


# ---------------------------------------------------------------------------
# Text normalisation + matching
# ---------------------------------------------------------------------------

_SCRIPT_RE = re.compile(r"<(script|style|noscript)\b[^>]*>.*?</\1>", re.I | re.S)
_INLINE_TAG_RE = re.compile(r"</?(?:b|i|u|em|strong|span|a|sup|sub|small|font|mark|abbr|wbr)\b[^>]*>", re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _fold(s: str) -> str:
    """Lowercase, strip diacritics (NFKD), collapse whitespace."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return _WS_RE.sub(" ", s).strip().lower()


def visible_text(body: str) -> str:
    """Markup stripped to spaces, entities decoded, whitespace collapsed."""
    t = _SCRIPT_RE.sub(" ", body or "")
    t = _INLINE_TAG_RE.sub("", t)     # 174,<b>000</b> reads as 174,000
    t = _TAG_RE.sub(" ", t)
    t = _html.unescape(t)
    return _WS_RE.sub(" ", t).strip()


_META_CONTENT_RE = re.compile(r"""<meta\b[^>]*\bcontent\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
_DATA_SCRIPT_RE = re.compile(r"""<script\b([^>]*\btype\s*=\s*["']application/(?:ld\+)?json[^"']*["'][^>]*)>(.*?)</script>""", re.I | re.S)
_JSON_STRING_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
_DATA_ATTR_RE = re.compile(r"""\s(?:data-[\w-]+|alt|title|aria-label)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)


def _raw_for_match(body: str) -> str:
    """The non-visible places a real value hides: <meta content="…">, JSON-LD,
    the string values of JSON data scripts (Next/Nuxt payloads — TradeWinds
    serves its standfirst there), and data-* / alt / title / aria-label
    attribute values. Nothing else from the source — a stylesheet's
    `font-size:16px`, a favicon's `sizes="16x16"` or an SVG path's numbers
    must never satisfy a needle of "16"."""
    b = body or ""
    parts = [g1 or g2 for g1, g2 in _META_CONTENT_RE.findall(b)]
    for attrs, payload in _DATA_SCRIPT_RE.findall(b):
        if "ld+json" in attrs.lower():
            parts.append(payload)
        else:
            # Next/Nuxt state payloads: prose lives in string literals; the bare
            # integers are ids / ad-slot codes ("type":16) and would fake a match.
            parts += [m.replace('\\/', '/').replace('\\"', '"')
                      for m in _JSON_STRING_RE.findall(payload)]
    parts += [g1 or g2 for g1, g2 in _DATA_ATTR_RE.findall(b)]
    # URLs / paths are not corroboration text (image hashes, slugs, ad ids).
    return " | ".join(x for x in parts
                      if x and not x.lstrip().lower().startswith(("http", "//", "/")))


def _match_texts(body: str) -> tuple[str, str]:
    """(folded visible text, folded raw source) — a needle may sit in either
    (raw = only meta content, JSON-LD / JSON data scripts and data-*/alt/title
    attribute values — see _raw_for_match)."""
    return _fold(visible_text(body)), _fold(_html.unescape(_raw_for_match(body)))


def _contains(hay: str, needle: str) -> bool:
    """Substring test; numeric-edged needles must sit on digit boundaries so
    "174,000" doesn't match "1,174,000" and "2026" doesn't match "20261"."""
    n = _fold(needle)
    if not n:
        return False
    if not (n[0].isdigit() or n[-1].isdigit()):
        return n in hay
    # Digit-edged needles sit on digit boundaries AND not inside a hex-ish
    # token: "77" must not match an image hash "…/binary/77ec82…", "16" must
    # not match "16px". (Letters are excluded on both sides; "174,000 cbm"
    # has a space, "174000cbm" in a URL slug is not corroboration.)
    pat = (r"(?<![\d.,a-z])" if n[0].isdigit() else "") + re.escape(n) + \
          (r"(?![\da-z])" if n[-1].isdigit() else "")
    return re.search(pat, hay) is not None


def _page_contains(body: str, needle: str) -> bool:
    vis, raw = _match_texts(body)
    return _contains(vis, needle) or _contains(raw, needle)


# ---------------------------------------------------------------------------
# Vessel type: the word must describe this ship, in the article's own text
# ---------------------------------------------------------------------------
# Baird 2026-09-23: "conventional" passed the plain substring gate on a Hellenic
# Shipping News sidebar headline ("biofuel prices against conventionals") and on
# Offshore Energy's "conventional marine fuels". A Vessel type value counts only
# where the article body uses it of a vessel ("conventional LNG carrier").

_CHROME_TAGS = {"nav", "aside", "footer", "form", "menu", "select", "button", "template",
                "script", "style", "noscript", "a"}   # <a>: link text = headlines / menus
_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
              "source", "track", "wbr"}
_CHROME_CLASS_RE = re.compile(
    r"(?:^|[-_])(?:sidebar|widgets?|related|menu|navbar|nav|navigation|breadcrumbs?|trending|"
    r"popular|recommended|newsletter|share|sharing|social|comments?|tagcloud|ticker|footer)(?:$|[-_])")


class _BodyText(HTMLParser):
    """Text outside page chrome; the <article>/<main> text kept apart."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.all, self.article = [], []
        self.skip = []            # [tag, depth] of the chrome element being skipped
        self.in_article = 0

    def handle_starttag(self, tag, attrs):
        if self.skip:
            if tag == self.skip[0]:
                self.skip[1] += 1
            return
        if tag in ("article", "main"):
            self.in_article += 1
            return
        if tag in _VOID_TAGS:
            return
        a = dict(attrs)
        tokens = f"{a.get('class') or ''} {a.get('id') or ''}".lower().split()
        if tag in _CHROME_TAGS or (tag == "header" and not self.in_article) or \
                (tag not in ("html", "body") and any(_CHROME_CLASS_RE.search(t) for t in tokens)):
            self.skip = [tag, 1]

    def handle_endtag(self, tag):
        if self.skip:
            if tag == self.skip[0]:
                self.skip[1] -= 1
                if not self.skip[1]:
                    self.skip = []
            return
        if tag in ("article", "main") and self.in_article:
            self.in_article -= 1

    def handle_data(self, data):
        if self.skip:
            return
        self.all.append(data)
        if self.in_article:
            self.article.append(data)


def article_text(body: str) -> str:
    """Folded text of the page's own article: <article>/<main> when present, else the
    whole page — minus nav / aside / footer / forms, sidebar- and widget-classed blocks
    and all link text. A PDF or plain-text body is returned whole."""
    b = body or ""
    if not re.search(r"<(?:html|body|div|p|article)\b", b, re.I):
        return _fold(b)
    parser = _BodyText()
    try:
        parser.feed(b)
        parser.close()
    except Exception:                                        # malformed markup: be strict
        return ""
    art = _fold(" ".join(parser.article))
    return art if len(art) >= 200 else _fold(" ".join(parser.all))


# Values that are themselves a vessel noun need no second word; the others
# ("conventional", "small-scale", "supporting") must sit next to one.
_VT_SELF_NOUN = {"fsru", "fsu", "icebreaker", "q-flex", "q-max", "qc-max"}
_VT_NOUN_RE = re.compile(r"(?:carriers?|lngcs?|vessels?|ships?|tankers?|newbuild(?:ing)?s?|fsrus?|fsus?|"
                         r"units?|designs?|class|fleet|hulls?|icebreakers?)")
# A qualifier that turns the word from the ship to something else ("conventional marine fuels").
_VT_STOP_RE = re.compile(r"fuel|marine|bunker|oil|diesel|propulsion|engine|power|emission|energy")


def _vt_tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9,.\-/]*", s)


def _vt_is_noun(tok: str) -> bool:
    return any(_VT_NOUN_RE.fullmatch(x) for x in re.split(r"[-/]", tok.strip(".,")) if x)


def vessel_type_statement(body: str, variants) -> str | None:
    """The phrase in `body` that states a Vessel type value of a vessel, else None.

    Counts only in `article_text`, never followed by a non-vessel qualifier (fuel,
    marine, propulsion …), and — unless the value is itself a vessel noun (FSRU,
    icebreaker, Q-Max) — with a vessel noun within five words after it or three
    before it ("conventional 174,000 cbm LNG carrier", "LNG carriers of conventional
    design")."""
    text = article_text(body)
    for v in {_fold(x) for x in variants if x}:
        for m in re.finditer(r"(?<![a-z0-9])" + re.escape(v) + r"(?![a-z0-9])", text):
            after = _vt_tokens(text[m.end():m.end() + 120])[:5]
            before = _vt_tokens(text[max(0, m.start() - 60):m.start()])[-3:]
            if after and _VT_STOP_RE.search(after[0]):
                continue
            phrase = text[max(0, m.start() - 40):m.end() + 60].strip()
            if v in _VT_SELF_NOUN:
                return phrase
            for tok in after:
                if _VT_STOP_RE.search(tok):
                    break
                if _vt_is_noun(tok):
                    return phrase
            if any(_vt_is_noun(t) for t in before):
                return phrase
    return None


def _title(body: str) -> str:
    m = re.search(r"<title[^>]*>([^<]+)</title>", body or "", re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _title_hit(title: str, fragments, wb=()) -> str | None:
    tl = _fold(title)
    for bad in fragments:
        if bad in wb:
            if re.search(r"(?<![a-z])" + re.escape(bad) + r"(?![a-z])", tl):
                return bad
        elif bad.strip().isdigit():
            # A status code must stand alone: "IMO 1162403" is not a 403 and
            # "IMO 1040447" is not a 404 (marinetraffic.org titles, 2026-09-16).
            # ...nor is a quantity: "$500 million order" / "404 MW" is a headline, not an error.
            if re.search(r"(?<![\d$€£.,])" + re.escape(bad.strip())
                         + r"(?![\d,.]|\s*(?:million|billion|mln|bn|m\b|cbm|mw|teu|ships|vessels))", tl):
                return bad
        elif bad in tl:
            return bad
    return None


# Cloudflare Bot Management injects this beacon into EVERY page of a protected
# site (marinetraffic.com's SPA shell included); it is telemetry, not a wall.
# Real challenges live under /cdn-cgi/challenge-platform/h/... and still match.
_CF_JSD_BEACON = "/cdn-cgi/challenge-platform/scripts/jsd/"


def _bot_wall_body(body: str) -> str | None:
    vis = _fold(visible_text(body))
    if len(vis) > _MAX_BOTWALL_BODY:
        return None
    low = (body or "").lower().replace(_CF_JSD_BEACON, "/cdn-cgi/jsd-beacon/")
    for m in _BOT_BLOCK_BODY_MARKERS:
        if m in vis or m in low:
            return m
    return None


# ---------------------------------------------------------------------------
# Host adapters — single-page apps whose HTML shell carries no data
# ---------------------------------------------------------------------------
#
# The vessel-tracker SPAs return a 200 shell with the vessel facts loaded by
# XHR, so a body match on the shell can never corroborate anything. Each
# adapter fetches the JSON the page itself calls and renders it as "key: value"
# lines that are appended to the page text before the content check. An
# adapter returns (extra_text, None) or (None, reason) — a reason in the dead
# grammar ("soft-error page (...)") when the record does not exist, in the
# blocked grammar when the API itself was walled.

SHIPVAULT_API = "https://shipvaultapi-gjb8c.ondigitalocean.app/api/units/{id}"
SHIPVAULT_API_HOST = "shipvaultapi-gjb8c.ondigitalocean.app"
_SHIPVAULT_PAGE_RE = re.compile(r"^/ships/(\d+)/?$")
# The unit-record endpoint is citable in its own right (it answers a plain
# browser click, no tenant header) — the companion ref for a page whose SPA
# renders blank. It is verified on the same rendered record as the page.
_SHIPVAULT_API_RE = re.compile(r"^/api/units/(\d+)/?$")
# shipvault's Angular bundle sends this fixed tenant header on shipsearch calls.
SHIPVAULT_HEADERS = {"tx": "06fa22ce-fd30-44e9-a7d3-2147d4b72d26",
                     "Origin": "https://www.shipvault.com", "Accept": "application/json"}
MARINETRAFFIC_COM_API = "https://www.marinetraffic.com/en/vesselDetails/vesselInfo/shipid:{id}"
_MARINETRAFFIC_COM_RE = re.compile(r"/shipid:(\d+)")
_MARINETRAFFIC_COM_HEADERS = {"Vessel-Image": "0", "X-Requested-With": "XMLHttpRequest"}


def _json_body(page: Page):
    """Parse a JSON page body; shipvault double-encodes some answers (a JSON
    string that itself holds JSON). None when the body is not JSON."""
    try:
        d = json.loads(page.text)
    except (ValueError, TypeError):
        return None
    if isinstance(d, str):
        try:
            d = json.loads(d)
        except (ValueError, TypeError):
            return None
    return d


def _render_record(rec: dict) -> str:
    """'key: value' lines for the content matcher (nested values as JSON)."""
    lines = []
    for k, v in rec.items():
        if v in (None, "", [], {}):
            continue
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        lines.append(f"{k}: {v}")
    return "\n".join(lines)


def _shipvault_unit_id(url: str) -> str | None:
    """Unit id of a shipvault page URL or of its unit-record API URL, else None."""
    pat = _SHIPVAULT_API_RE if _host(url) == SHIPVAULT_API_HOST else _SHIPVAULT_PAGE_RE
    m = pat.match(urlsplit(url).path)
    return m.group(1) if m else None


def _shipvault_adapter(url: str, page: Page) -> tuple[str | None, str | None]:
    uid = _shipvault_unit_id(url)
    if not uid:
        return "", None
    api = _fetch(SHIPVAULT_API.format(id=uid), headers=SHIPVAULT_HEADERS)
    if api.status != "200":
        cls = "blocked: " if api.status in _BOT_BLOCK_STATUSES else ""
        return None, f"{cls}shipvault unit {uid} API HTTP {api.status}"
    data = _json_body(api)
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        return None, f"soft-error page (shipvault unit {uid} has no record)"
    rec = dict(data[0])
    built, month = rec.get("built"), rec.get("month")
    if built and month:
        rec["delivery"] = f"{built}-{int(month):02d}"
    # The record's own forms never sit on a match boundary: a date is an ISO
    # timestamp ("1999-04-01T00:00:00"), a price is whole dollars (165000000)
    # where the backend carries $m. Render both the way a cell states them.
    for k, v in list(rec.items()):
        if isinstance(v, str) and re.fullmatch(r"\d{4}-\d\d-\d\dT[\d:.]+Z?", v):
            rec[k] = v[:10]
    if isinstance(rec.get("newprice"), (int, float)) and rec["newprice"] > 0:
        rec["newprice (million)"] = f"{rec['newprice'] / 1e6:g}"
    page.notes.append("shipvault_api")
    return _render_record(rec), None


def _marinetraffic_com_adapter(url: str, page: Page) -> tuple[str | None, str | None]:
    m = _MARINETRAFFIC_COM_RE.search(urlsplit(url).path)
    if not m:
        return "", None          # news pages etc. are ordinary HTML
    sid = m.group(1)
    api = _fetch(MARINETRAFFIC_COM_API.format(id=sid),
                 headers={**_MARINETRAFFIC_COM_HEADERS, "Referer": url})
    if api.status == "404":
        return None, f"soft-error page (marinetraffic.com shipid {sid} not found)"
    if api.status != "200":
        cls = "blocked: " if api.status in _BOT_BLOCK_STATUSES else ""
        return None, f"{cls}marinetraffic.com vesselInfo HTTP {api.status}"
    data = _json_body(api)
    if not isinstance(data, dict) or not data.get("name"):
        return None, f"blocked: marinetraffic.com vesselInfo for shipid {sid} is not JSON"
    page.notes.append("marinetraffic_api")
    return _render_record(data), None


_HOST_ADAPTERS = {
    "shipvault.com": _shipvault_adapter,
    SHIPVAULT_API_HOST: _shipvault_adapter,
    "marinetraffic.com": _marinetraffic_com_adapter,
}


def _adapter_for(url: str):
    host = _host(url)
    for suffix, fn in _HOST_ADAPTERS.items():
        if host == suffix or host.endswith("." + suffix):
            return fn
    return None


# ---------------------------------------------------------------------------
# Wayback fallback
# ---------------------------------------------------------------------------

def _wayback_api(api_url: str) -> Page:
    """Fetch a Wayback API endpoint; on 429/5xx wait and retry (uncached)."""
    p = _fetch(api_url)
    tries = 0
    while p.status in _WB_RETRY_STATUSES and tries < WAYBACK_RETRIES:
        tries += 1
        _CACHE.pop(api_url, None)
        time.sleep(WAYBACK_RETRY_DELAY)
        p = _fetch(api_url)
    return p


def _wayback_snapshot_urls(url: str) -> tuple[list[str], str]:
    """(candidate snapshot URLs newest first, note). The note is "" when the
    APIs answered, else why they didn't ("Wayback rate-limited (HTTP 429)")
    — so a throttled archive is never reported as "no Wayback snapshot"."""
    out: list[str] = []
    q = quote(url, safe="")
    answered = []          # per API: True = JSON answer, else the failure label
    avail = _wayback_api(_WB_AVAIL.format(u=q))
    try:
        if avail.status != "200":
            raise ValueError(avail.status)
        snap = (json.loads(avail.text).get("archived_snapshots") or {}).get("closest") or {}
        answered.append(True)
        if snap.get("available") and snap.get("url"):
            m = _WAYBACK_SNAPSHOT_RE.match(snap["url"])
            out.append(_WB_SNAP.format(ts=m.group(1), u=m.group(2)) if m else snap["url"])
    except (ValueError, AttributeError):
        answered.append(_wayback_failure(avail))
    cdx = _wayback_api(_WB_CDX.format(u=q))
    try:
        if cdx.status != "200":
            raise ValueError(cdx.status)
        rows = json.loads(cdx.text)
        answered.append(True)
        for row in reversed(rows[1:] if rows and rows[0] and rows[0][0] == "timestamp" else rows):
            if row and row[0].isdigit():
                cand = _WB_SNAP.format(ts=row[0], u=url)
                if cand not in out:
                    out.append(cand)
    except (ValueError, TypeError, IndexError):
        answered.append(_wayback_failure(cdx))
    note = ""
    if True not in answered:      # neither API gave a real answer
        note = next((a for a in answered if "rate-limited" in a), answered[0])
    return out, note


def _wayback_failure(p: Page) -> str:
    """Label a non-answer from a Wayback API (never confuse it with "no snapshot")."""
    if p.status == "429":
        return "Wayback rate-limited (HTTP 429)"
    if p.status == "200":
        # 200 with an HTML body: the "Internet Archive: Temporarily Offline" page
        t = _title(p.text) or "non-JSON answer"
        return f"Wayback unavailable ({t.strip()[:60]})"
    return f"Wayback unavailable (HTTP {p.status})"


def _check_wayback(url: str, expected: list[str], require_all: bool,
                   matcher=None) -> tuple[bool, str, int]:
    """Try snapshots. Returns (ok, reason, n_readable_snapshots).

    (True, "OK (via Wayback <ts>)") when a snapshot carries the content. With
    no expected content (health-only checks) a snapshot never upgrades a wall
    — it is reported as existing, so the caller can grade `blocked` with the
    archive noted. n_readable_snapshots > 0 proves the page existed at some
    point (used to keep an HTTP 000 out of `dead`).
    """
    if not WAYBACK_ENABLED:
        return False, "Wayback disabled", 0
    snaps, note = _wayback_snapshot_urls(url)
    tried = 0
    readable: list[str] = []
    for snap in snaps[:4]:
        tried += 1
        p = _fetch(snap)
        if p.status != "200" or not p.text.strip():
            continue
        if _title_hit(_title(p.text), _SOFT_ERROR_TITLES):
            continue
        readable.append(snap)
        if not expected:
            continue
        ok, _ = _content_check(p.text, expected, require_all, matcher)
        if ok:
            return True, f"OK (via Wayback {_snap_ts(snap)}; live URL blocked, snapshot carries content)", len(readable)
    if tried == 0:
        return False, note or "no Wayback snapshot", 0
    if not readable:
        return False, f"{tried} Wayback snapshot(s) unreadable", 0
    if not expected:
        return False, f"Wayback snapshot {_snap_ts(readable[0])} exists; no content to confirm", len(readable)
    return False, f"{tried} Wayback snapshot(s) lack expected content", len(readable)


def _snap_ts(snap: str) -> str:
    m = _WAYBACK_SNAPSHOT_RE.match(snap)
    return m.group(1) if m else "?"


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

def _content_check(body: str, expected: list[str], require_all: bool,
                   matcher=None) -> tuple[bool, str]:
    if not expected:
        return True, "OK"
    if matcher is not None:          # a field-specific test replaces the substring test
        return (True, "OK") if matcher(body) else \
            (False, f"none of expected content found: {expected}")
    found = [s for s in expected if _page_contains(body, s)]
    missing = [s for s in expected if s not in found]
    if require_all and missing:
        return False, f"missing expected content: {missing}"
    if not require_all and not found:
        return False, f"none of expected content found: {expected}"
    return True, "OK"


def _finish(url, ok, reason, strict, page: Page | None, expected, kind="verify"):
    _log({"url": url, "kind": kind, "ok": ok, "reason": reason,
          "status": page.status if page else None,
          "final_url": (page.final_url or None) if page else None,
          "is_pdf": page.is_pdf if page else None,
          "notes": list(page.notes) if page else [],
          "expected": list(expected or [])})
    if not ok and strict:
        raise CitationError(f"URL failed verification ({reason}): {url}")
    return ok, reason


def verify_url(url: str, expected: list[str], strict: bool = False,
               require_all: bool = True, matcher=None) -> tuple[bool, str]:
    """
    Verify URL passes the gate:
      0. URL shape is citable (not banned / shortener / navigation / save-endpoint)
      1. HTTP 200 (401/403/429/5xx -> Wayback fallback; 404/410/000 -> dead)
      2. Not a soft-error page (title / bot-wall body); bot walls -> Wayback fallback
      3. Redirect chain did not land on a banned host or the site root
      4. Body (or PDF text, or the Wayback snapshot) contains `expected`

    Args:
        url: the URL to verify
        expected: substrings that must appear in the page body.
                  Cluster coherence (Rule E): [owner, yard, hull-count];
                  value presence (Rule F): [owner, yard, "174,000"]
        strict: if True, raise CitationError on failure instead of returning False
        require_all: every expected substring must be present (default). If
                     False, at least one must be (rarely correct outside the
                     corroboration gate's variant list).
        matcher: optional body -> bool that replaces the substring test (on the
                 live page and any Wayback snapshot) — the Vessel type gate.

    Returns:
        (ok: bool, reason: str) — see the module docstring for the reason
        grammar; use `classify(reason)` rather than parsing it.
    """
    url = (url or "").strip()
    ban = url_ban_reason(url)
    if ban:
        return _finish(url, False, ban, strict, None, expected)

    page = _fetch(url)
    status, text = page.status, page.text

    if status != "200":
        if status in _BOT_BLOCK_STATUSES or status == "000":
            ok, wb, n_snap = _check_wayback(url, expected, require_all, matcher)
            if ok:
                return _finish(url, True, wb, strict, page, expected)
            if status == "000" and not n_snap:
                # connection failed AND the archive never saw the page: dead.
                # (With a snapshot it is a geo-block / outage — blocked.)
                return _finish(url, False, f"HTTP 000 ({wb})", strict, page, expected)
            return _finish(url, False, f"blocked: HTTP {status} ({wb})", strict, page, expected)
        return _finish(url, False, f"HTTP {status}", strict, page, expected)

    rr = _redirect_reason(url, page)
    if rr:
        return _finish(url, False, rr, strict, page, expected)

    if not page.is_pdf:
        title = _title(text)
        # Soft-error (dead class) beats bot-block when both could match: a
        # "404 Not Found" title is a gone page, not a wall.
        if title and _title_hit(title, _SOFT_ERROR_TITLES):
            return _finish(url, False, f"soft-error page (title: {title!r})", strict, page, expected)
        wall = (_title_hit(title, _BOT_BLOCK_TITLES, _BOT_BLOCK_TITLES_WB) if title else None) \
            or _bot_wall_body(text)
        if wall:
            ok, wb, _ = _check_wayback(url, expected, require_all, matcher)
            if ok:
                return _finish(url, True, wb, strict, page, expected)
            where = f"title: {title!r}" if title and _title_hit(title, _BOT_BLOCK_TITLES, _BOT_BLOCK_TITLES_WB) \
                else f"body marker: {wall!r}"
            return _finish(url, False, f"blocked: soft-error page ({where}; {wb})",
                           strict, page, expected)
        if not text.strip():
            return _finish(url, False, "soft-error page (empty body)", strict, page, expected)
        adapter = _adapter_for(url)
        if adapter:
            extra, err = adapter(url, page)
            if err:
                return _finish(url, False, err, strict, page, expected)
            if extra:
                text = text + "\n" + extra

    ok, reason = _content_check(text, expected, require_all, matcher)
    if ok and page.notes:
        reason = "OK (" + ", ".join(page.notes) + ")"
    return _finish(url, ok, reason, strict, page, expected)


def classify(reason: str) -> str:
    """Grade a verify/corroborate reason: ok | banned | dead | blocked | uncorroborated."""
    r = (reason or "").strip()
    if r == "OK" or r.startswith("OK ") or r.startswith("OK("):
        return "ok"
    if r.startswith("banned"):
        return "banned"
    if r.startswith("blocked"):
        return "blocked"
    if r.startswith("HTTP") or r.startswith("soft-error"):
        return "dead"
    return "uncorroborated"


def check_url(url: str) -> dict:
    """Health-only check (no content requirement) for the citation rot sweep.

    Returns {"url", "verdict", "reason", "status", "final_url", "title", "is_pdf"}
    with verdict in ok / blocked / dead / banned. A blocked page that has a
    Wayback snapshot at all reports verdict "blocked" with the snapshot noted —
    health alone never upgrades a wall to ok (there is no content to confirm).
    """
    url = (url or "").strip()
    ok, reason = verify_url(url, [], strict=False)
    page = _CACHE.get(url)
    page = _as_page(page) if page is not None else None
    verdict = classify(reason)
    if verdict == "uncorroborated":     # impossible with no expected content, but be safe
        verdict = "ok"
    return {"url": url, "verdict": verdict, "reason": reason,
            "status": page.status if page else "",
            "final_url": (page.final_url if page else "") or "",
            "title": _title(page.text) if page and not page.is_pdf else "",
            "is_pdf": bool(page.is_pdf) if page else False}


# ---------------------------------------------------------------------------
# Value ↔ ref corroboration (§3.8c)
# ---------------------------------------------------------------------------

_DELIVERED_PHRASES = (
    "took delivery", "taken delivery", "takes delivery", "taking delivery", "was delivered",
    "were delivered", "has been delivered", "have been delivered", "handed over", "delivery ceremony",
    "naming and delivery", "joined the fleet", "joins the fleet", "entered service",
    "maiden voyage", "first cargo")

_ORDERED_PHRASES = (
    "on order", "has ordered", "have ordered", "ordered", "order for", "orders for", "wins order",
    "won an order", "won orders", "secured an order", "shipbuilding contract", "newbuilding contract",
    "contract to build", "contract for the construction", "orderbook", "order book",
    "carrier order", "fsru order", "order at", "order of a", "order with", "under construction")

# A demolition sale is reported as the sale or the arrival at the breakers, never as the
# tracker's status word. "to be scrapped" / "could be scrapped" is an intention, so the
# bare verb is not enough on its own: only completed-sale wording passes.
_SCRAPPED_PHRASES = (
    "scrapped", "sold for scrap", "sold for demolition", "sold for recycling", "sold to breakers",
    "sold to cash buyer", "sold to cash buyers", "demolition sale", "for demolition", "for recycling",
    "for scrap", "demolished", "broken up", "beached", "recycling yard", "scrapyard", "shipbreaking",
    "ship breaking", "breakers")

_MONTHS = {a.lower(): (i + 1, a, f) for i, (a, f) in enumerate([
    ("Jan", "January"), ("Feb", "February"), ("Mar", "March"), ("Apr", "April"),
    ("May", "May"), ("Jun", "June"), ("Jul", "July"), ("Aug", "August"),
    ("Sep", "September"), ("Oct", "October"), ("Nov", "November"), ("Dec", "December")])}


def value_variants(value) -> list[str]:
    """Plausible page renderings of a data value, for the corroboration gate.

    The gate matches a cell value against a page case-insensitively, but raw
    values rarely appear verbatim: ``180000`` shows as "180,000", a price of
    ``250000000`` shows as "$250 million" or "$250m". This generates the family
    of forms so a hard-block gate doesn't reject legitimately-worded sources.

    Text values yield themselves (+ lowercase). Numeric values additionally
    yield comma-grouped, plain, and millions/billions-abbreviated forms.
    """
    v = str(value).strip()
    if not v:
        return []
    out = {v, v.lower()}

    # Backend hull numbers carry a yard tag the source never prints:
    # "Hull 2598 (Hanwha)" -> the page says "Hull 2598", "H2598", "hull no. 2598".
    # Chinese-yard hulls carry no tag at all ("Hull H2706"); same treatment.
    hm = re.match(r"^Hull\s+(\S+)(?:\s+\(.+\))?$", v, re.I)
    if hm:
        no = hm.group(1)
        out.update({f"Hull {no}", f"hull no. {no}", f"hull number {no}", f"H{no}", f"HN{no}",
                    f"H-{no}", f"No. {no}"})
        if len(re.sub(r"\D", "", no)) >= 4:
            out.add(no)
        return [s for s in out if s]

    # Status "active" = the ship has been delivered. Press never writes "active";
    # it writes a past-tense delivery. Future-tense ("will be delivered") must not pass.
    if v.lower() == "active":
        out.update(_DELIVERED_PHRASES)
        return [s for s in out if s]

    # Status "scrapped" = sold for demolition / broken up.
    if v.lower() == "scrapped":
        out.update(_SCRAPPED_PHRASES)
        return [s for s in out if s]

    # Status "on order" = a firm newbuilding contract exists. Press reports the order
    # ("has ordered", "shipbuilding contract"), never the tracker's status word.
    if v.lower() == "on order":
        out.update(_ORDERED_PHRASES)
        return [s for s in out if s]

    # Backend dates are DD-Mon-YYYY ("08-Jun-2026", "02-June-2026"); pages write
    # "8 June 2026", "June 8, 2026", "2026-06-08" (also the datePublished meta),
    # "2026.06.08" (Korean press). Year-less forms are long-month only.
    dm = re.match(r"^(\d{1,2})-([A-Za-z]{3,9})-(\d{4})$", v)
    if dm and dm.group(2)[:3].lower() in _MONTHS:
        day, (mi, abbr, full), year = int(dm.group(1)), _MONTHS[dm.group(2)[:3].lower()], dm.group(3)
        for d in {str(day), f"{day:02d}"}:
            for mon in {abbr, full}:
                out.update({f"{d} {mon} {year}", f"{mon} {d}, {year}", f"{mon} {d} {year}",
                            f"{mon}. {d}, {year}", f"{d}-{mon}-{year}"})
            out.update({f"{full} {d}", f"{d} {full}"} if len(full) > 3 else set())
        out.update({f"{year}-{mi:02d}-{day:02d}", f"{year}.{mi:02d}.{day:02d}",
                    f"{year}/{mi:02d}/{day:02d}", f"{day:02d}.{mi:02d}.{year}",
                    f"{day:02d}/{mi:02d}/{year}"})
        return [s for s in out if s]

    m = re.match(r"^\$?\s*([\d,]+(?:\.\d+)?)", v)
    if m:
        try:
            num = float(m.group(1).replace(",", ""))
        except ValueError:
            num = None
        if num is not None:
            if num == int(num):
                num = int(num)
            out.add(str(num))
            if isinstance(num, int):
                out.add(f"{num:,}")
                out.add(f"{num:,}".replace(",", " "))      # 174 000 (FR/Nordic style)
                out.add(f"{num:,}".replace(",", "."))      # 174.000 (DE/ES style)
                if num >= 1_000_000:
                    for mm in {num / 1_000_000, round(num / 1_000_000)}:
                        s = f"{mm:g}"
                        out.update({f"{s}m", f"${s}m", f"{s} million", f"{s} mn"})
                    if num >= 1_000_000_000:
                        for bb in {num / 1_000_000_000, round(num / 1_000_000_000, 2)}:
                            s = f"{bb:g}"
                            out.update({f"{s}bn", f"${s}bn", f"{s} billion"})
    return [s for s in out if s]


def corroborates(url: str, value, strict: bool = False, field: str = "") -> tuple[bool, str]:
    """The value↔ref corroboration gate ([ref]-Fill SOP §3.8c / Rule D §4.11).

    A ref may only be cited on a cell whose VALUE the ref's live page actually
    contains (in some rendering — see ``value_variants``). This is the hard-block
    that stops a ref corroborating a *different* number than the cell carries
    (e.g. a 180,000-cbm source pinned to a 176,400 cell).

    A blank value has nothing to corroborate -> passes (use ``verify_url`` for
    entity-only checks). On failure with ``strict``, raises CitationError.

    ``field == "Vessel type"``: the value counts only where the article body states
    it of a vessel (``vessel_type_statement``) — never in a sidebar, a link or a
    phrase like "conventional marine fuels" — and the token fallback is off.

    Returns (ok, reason); grade with ``classify``.
    """
    variants = value_variants(value)
    if not variants:
        return True, "no value to corroborate"
    if field == "Vessel type":
        ok, reason = verify_url(url, variants, strict=False, require_all=False,
                                matcher=lambda body: vessel_type_statement(body, variants) is not None)
        if not ok and reason.startswith("none of expected"):
            reason = (f"page does not contain value {str(value).strip()!r} as a vessel type "
                      "(article text, next to vessel wording)")
            _log({"url": url, "kind": "corroborate", "ok": False, "reason": reason, "value": str(value)})
        if not ok and strict:
            raise CitationError(f"ref does not corroborate value ({reason}): {url}")
        return ok, reason
    ok, reason = verify_url(url, variants, strict=False, require_all=False)

    # Multi-word text fallback: an owner "Knutsen OAS" legitimately appears as
    # "Knutsen OAS Shipping"; a builder "China Merchants Heavy Industries" as
    # "China Merchants". Accept when every significant token (alnum, len>=3) is
    # present, so hard-block doesn't reject correctly-sourced text whose exact
    # phrasing differs. Numeric values (leading digit) never use this fallback —
    # 180,000 must appear as the figure, not as scattered digits.
    if not ok and reason.startswith("none of expected"):
        v = str(value).strip()
        is_numeric = bool(re.match(r"^\$?\s*[\d,]", v))
        tokens = [t for t in re.findall(r"[^\W_]+", v) if len(t) >= 3]
        if not is_numeric and len(tokens) >= 2:
            page = _fetch(url)
            if page.status == "200" and all(_page_contains(page.text, t) for t in tokens):
                _log({"url": url, "kind": "corroborate", "ok": True,
                      "reason": "OK (all tokens present)", "value": v})
                return True, "OK (all tokens present)"
        reason = f"page does not contain value {v!r}"
        _log({"url": url, "kind": "corroborate", "ok": False, "reason": reason, "value": v})
    if not ok and strict:
        raise CitationError(f"ref does not corroborate value ({reason}): {url}")
    return ok, reason


def verify_and_format(url: str, expected: list[str]) -> str | None:
    """
    Verify a URL. If it passes, return the URL.
    If it fails, return None and log the reason to stderr.

    Use in build scripts so failed URLs are silently dropped from citations
    rather than written into the xlsx.
    """
    ok, reason = verify_url(url, expected, strict=False)
    if ok:
        return url
    print(f"  [CITATION DROPPED] {url}\n    reason: {reason}", file=sys.stderr)
    return None


def clear_cache(url: str | None = None) -> None:
    """Clear the in-memory cache (all of it, or one URL + its Wayback lookups)."""
    if url is None:
        _CACHE.clear()
        return
    q = quote(url, safe="")
    for k in (url, _WB_AVAIL.format(u=q), _WB_CDX.format(u=q)):
        _CACHE.pop(k, None)


def main():
    global WAYBACK_ENABLED
    p = argparse.ArgumentParser(
        description="The §3.8 URL verification gate: citable shape + HTTP 200 "
                    "+ soft-error / bot-wall detection (Wayback fallback) + "
                    "content check. Exits 0 on PASS, 1 on FAIL.")
    p.add_argument("url", help="URL to verify")
    p.add_argument("expected", nargs="*",
                   help="Substrings that must all appear in the page body "
                        "(e.g. owner, yard, capacity)")
    p.add_argument("--value",
                   help="Corroboration-gate mode: pass iff the page contains "
                        "this cell VALUE in some plausible rendering "
                        "(ignores positional <expected> args)")
    p.add_argument("--field", default="",
                   help='With --value: the backend column (e.g. "Vessel type" = article '
                        'text next to vessel wording only)')
    p.add_argument("--check", action="store_true",
                   help="Health-only: print the graded verdict (ok/blocked/dead/banned)")
    p.add_argument("--no-wayback", action="store_true",
                   help="Do not consult Wayback for blocked pages")
    p.add_argument("--log", help="Append a JSONL audit record per verdict to this file "
                                 "(default: $URL_VERIFIER_LOG)")
    args = p.parse_args()

    if args.no_wayback:
        WAYBACK_ENABLED = False
    if args.log:
        set_log_path(args.log)

    if args.check:
        info = check_url(args.url)
        print(f"  URL: {args.url}")
        print(f"  Verdict: {info['verdict'].upper()}  ({info['reason']})")
        print(f"  Status: {info['status']}  final: {info['final_url'] or '-'}  "
              f"title: {info['title'][:80]!r}")
        sys.exit(0 if info["verdict"] == "ok" else 1)

    if args.value is not None:
        ok, reason = corroborates(args.url, args.value, field=args.field)
        print(f"  URL: {args.url}")
        print(f"  Value: {args.value!r}  (variants: {value_variants(args.value)})")
        print(f"  Corroborates: {'PASS' if ok else 'FAIL'}  ({reason}) [{classify(reason)}]")
        sys.exit(0 if ok else 1)

    ok, reason = verify_url(args.url, args.expected, strict=False, require_all=True)
    print(f"  URL: {args.url}")
    print(f"  Expected: {args.expected}")
    print(f"  Result: {'PASS' if ok else 'FAIL'}  ({reason}) [{classify(reason)}]")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
