"""Tests for scripts/url_verifier.py — the §3.8 verification gate.

The gate's checks (citable URL shape, HTTP status, soft-error / bot-wall
detection with Wayback fallback, redirect re-check, required content present)
are what keep dead/hallucinated/rate-limited/banned URLs out of the xlsx. We
exercise them offline by pre-seeding the module's per-process _CACHE:
verify_url() reads the cache before it would ever shell out to curl, so no
test touches the network (tests/README.md: "Tests should never hit the
network"). The autouse fixture also stubs fetch_page so an un-seeded URL
fails loudly instead of silently going online.
"""
import json

import pytest
import url_verifier
from fetch import Page
from url_verifier import (
    CitationError,
    check_url,
    classify,
    clear_cache,
    corroborates,
    url_ban_reason,
    value_variants,
    verify_url,
)


def seed(url, status, body):
    """Plant a (status, body) response in the fetch cache for `url`."""
    url_verifier._CACHE[url] = (status, body)


def seed_page(url, status, body, **kw):
    """Plant a full Page (final_url, is_pdf, notes...) for `url`."""
    url_verifier._CACHE[url] = Page(status=status, text=body, **kw)


def seed_wayback(url, snapshots, body):
    """Seed the availability + CDX endpoints and each snapshot for `url`."""
    from urllib.parse import quote
    q = quote(url, safe="")
    closest = ({"available": True, "url": f"https://web.archive.org/web/{snapshots[0]}/{url}",
                "timestamp": snapshots[0], "status": "200"} if snapshots else {})
    seed(url_verifier._WB_AVAIL.format(u=q), "200",
         json.dumps({"archived_snapshots": {"closest": closest} if closest else {}}))
    seed(url_verifier._WB_CDX.format(u=q), "200",
         json.dumps([["timestamp", "statuscode"]] + [[ts, "200"] for ts in snapshots]))
    for ts in snapshots:
        seed(url_verifier._WB_SNAP.format(ts=ts, u=url), "200", body)


def seed_no_wayback(url):
    seed_wayback(url, [], "")


def seed_wayback_status(url, status):
    """Make both Wayback APIs answer `status` (e.g. "429") for `url`."""
    from urllib.parse import quote
    q = quote(url, safe="")
    seed(url_verifier._WB_AVAIL.format(u=q), status, "Too Many Requests")
    seed(url_verifier._WB_CDX.format(u=q), status, "Too Many Requests")


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    clear_cache()
    url_verifier.set_log_path(None)
    url_verifier.WAYBACK_ENABLED = True
    url_verifier.FETCH_DELAY = 0
    url_verifier.HOST_MIN_GAP = 0
    url_verifier.WAYBACK_RETRIES = 0

    def _no_network(url, **kw):
        raise AssertionError(f"test tried to fetch the network: {url}")
    monkeypatch.setattr(url_verifier, "fetch_page", _no_network)
    yield
    clear_cache()


def _page(title, body=""):
    return f"<html><head><title>{title}</title></head><body>{body}</body></html>"


class TestHappyPath:
    def test_200_with_all_expected_content_passes(self):
        url = "https://example.com/order"
        seed(url, "200", _page("LNG order", "Maran Gas at Samsung, 174,000 cbm"))
        ok, reason = verify_url(url, ["Maran Gas", "Samsung", "174,000"])
        assert ok is True
        assert reason == "OK"

    def test_content_match_is_case_insensitive(self):
        url = "https://example.com/x"
        seed(url, "200", _page("t", "HANWHA OCEAN delivered the vessel"))
        ok, _ = verify_url(url, ["hanwha ocean"])
        assert ok is True

    def test_empty_expected_is_a_health_check(self):
        url = "https://example.com/x"
        seed(url, "200", _page("t", "anything"))
        assert verify_url(url, []) == (True, "OK")


class TestContentChecks:
    def test_missing_expected_content_fails(self):
        url = "https://example.com/x"
        seed(url, "200", _page("t", "Maran Gas at Samsung"))
        ok, reason = verify_url(url, ["Maran Gas", "Knutsen"])
        assert ok is False
        assert "Knutsen" in reason
        assert classify(reason) == "uncorroborated"

    def test_require_all_false_passes_on_any_match(self):
        url = "https://example.com/x"
        seed(url, "200", _page("t", "only Samsung is named here"))
        ok, _ = verify_url(url, ["Knutsen", "Samsung"], require_all=False)
        assert ok is True

    def test_require_all_false_fails_when_none_match(self):
        url = "https://example.com/x"
        seed(url, "200", _page("t", "nothing relevant"))
        ok, reason = verify_url(url, ["Knutsen", "Samsung"], require_all=False)
        assert ok is False
        assert "none of expected" in reason

    def test_whitespace_and_markup_are_normalised(self):
        # "174,<b>000</b>" with a line break renders as 174,000 to a reader
        url = "https://example.com/x"
        seed(url, "200", _page("t", "capacity of 174,<b>000</b>\n   cbm for Maran\n\tGas"))
        ok, _ = verify_url(url, ["174,000", "Maran Gas"])
        assert ok is True

    def test_html_entities_are_decoded(self):
        url = "https://example.com/x"
        seed(url, "200", _page("t", "Hyundai Heavy Industries &amp; Co &#8211; 200,000&nbsp;cbm"))
        ok, _ = verify_url(url, ["Hyundai Heavy Industries & Co", "200,000 cbm"])
        assert ok is True

    def test_diacritics_fold(self):
        url = "https://example.com/x"
        seed(url, "200", _page("t", "Chantiers de l’Atlantique à Saint-Nazaire; Höegh LNG"))
        ok, _ = verify_url(url, ["Hoegh LNG", "Saint-Nazaire"])
        assert ok is True

    def test_numeric_needle_requires_digit_boundaries(self):
        url = "https://example.com/x"
        seed(url, "200", _page("t", "the yard has built 1,174,000 cbm in total; hull 20261"))
        ok, reason = verify_url(url, ["174,000"])
        assert ok is False
        ok, _ = verify_url(url, ["2026"])
        assert ok is False
        seed(url, "200", _page("t", "a 174,000 cbm vessel due 2026."))
        assert verify_url(url, ["174,000", "2026"])[0] is True

    def test_value_in_raw_source_counts(self):
        # JSON-LD / data attributes are still the page's own content
        url = "https://example.com/x"
        seed(url, "200", '<html><head><title>t</title><script type="application/ld+json">'
                         '{"headline":"Knutsen orders at Hyundai Samho"}</script></head><body></body></html>')
        ok, _ = verify_url(url, ["Hyundai Samho"])
        assert ok is True


class TestSoftErrorDetection:
    @pytest.mark.parametrize("title", [
        "404 Not Found",
        "Page Not Found",
        "503 Service Unavailable",
        "Oops! This page no longer available",
    ])
    def test_dead_titles_fail_even_with_200(self, title):
        url = f"https://example.com/{title}"
        seed(url, "200", _page(title, "Maran Gas Samsung 174,000"))
        ok, reason = verify_url(url, ["Maran Gas"])
        assert ok is False
        assert reason.startswith("soft-error")
        assert classify(reason) == "dead"

    @pytest.mark.parametrize("title", [
        "429 Too Many Requests",
        "Just a moment...",        # Cloudflare interstitial
        "Attention Required! | Cloudflare",
        "Access Denied",
        "Sign in to continue | TradeWinds",
        "Subscribe to read | LNG Prime",
    ])
    def test_bot_wall_titles_are_blocked_not_dead(self, title):
        # A 200 whose title is a wall must not pass on its own body — this is
        # the Riviera-429 / Cloudflare class the gate exists to catch — but it
        # is BLOCKED (§3.8a: env block ≠ dead), not dead.
        url = f"https://example.com/{title}"
        seed(url, "200", _page(title, "Maran Gas Samsung 174,000"))
        seed_no_wayback(url)
        ok, reason = verify_url(url, ["Maran Gas"])
        assert ok is False
        assert "soft-error" in reason
        assert classify(reason) == "blocked"

    def test_legitimate_title_is_not_flagged(self):
        url = "https://example.com/ok"
        seed(url, "200", _page("Maran Gas orders two LNG carriers", "Maran Gas"))
        ok, _ = verify_url(url, ["Maran Gas"])
        assert ok is True

    def test_word_boundary_titles_do_not_overmatch(self):
        url = "https://example.com/ok"
        seed(url, "200", _page("Signs in the market: shipowners login to new era of orders",
                               "Maran Gas"))
        # "signs in" is not "sign in"; "login" IS a word here -> blocked. Check the
        # narrower case: only 'signs in'.
        seed(url, "200", _page("Signs in the market for LNG carriers", "Maran Gas"))
        assert verify_url(url, ["Maran Gas"])[0] is True

    def test_status_code_fragments_need_digit_boundaries(self):
        # marinetraffic.org titles carry the IMO: "IMO 1162403" is not a 403,
        # "IMO 1040447" is not a 404.
        url = "https://www.marinetraffic.org/ship-owner-manager-ism-data/SAMSUNG-2774/1162403/1"
        seed(url, "200", _page("SAMSUNG 2774 - LNG Tanker, IMO 1162403", "IMO 1162403"))
        assert verify_url(url, ["1162403"])[0] is True
        url2 = "https://www.marinetraffic.org/ship-owner-manager-ism-data/LNG-PING-HU/1040447/1"
        seed(url2, "200", _page("PING HU 3 - LNG Tanker, IMO 1040447", "Delivered"))
        assert verify_url(url2, ["Delivered"])[0] is True
        # a bare code still counts
        seed(url, "200", _page("403 Forbidden", "IMO 1162403"))
        seed_no_wayback(url)
        assert "blocked" in verify_url(url, ["1162403"])[1]

    def test_incapsula_body_marker_is_blocked(self):
        url = "https://example.com/x"
        seed(url, "200", "<html><head><title>Riviera</title></head><body>"
                         "<iframe src='/_Incapsula_Resource?SWUDNSAA=1'></iframe></body></html>")
        seed_no_wayback(url)
        ok, reason = verify_url(url, ["Riviera"])
        assert ok is False
        assert classify(reason) == "blocked"
        assert "body marker" in reason

    def test_chinese_block_phrase_is_blocked(self):
        url = "https://example.cn/x"
        seed(url, "200", _page("提示", "访问被拒绝，请稍后再试"))
        seed_no_wayback(url)
        ok, reason = verify_url(url, ["沪东"])
        assert classify(reason) == "blocked"

    def test_long_article_mentioning_cloudflare_is_not_a_wall(self):
        url = "https://example.com/x"
        body = ("Cloudflare Ray ID: mentioned in passing. " + "Maran Gas ordered vessels. " * 300)
        seed(url, "200", _page("Maran Gas orders", body))
        assert verify_url(url, ["Maran Gas"])[0] is True

    def test_empty_body_is_soft_error(self):
        url = "https://example.com/x"
        seed(url, "200", "")
        ok, reason = verify_url(url, [])
        assert ok is False
        assert classify(reason) == "dead"


class TestHttpStatus:
    def test_non_200_fails_with_status_in_reason(self):
        url = "https://example.com/gone"
        seed(url, "404", _page("whatever"))
        ok, reason = verify_url(url, ["anything"])
        assert ok is False
        assert reason == "HTTP 404"
        assert classify(reason) == "dead"

    def test_curl_failure_000_fails(self):
        url = "https://unreachable.invalid/x"
        seed(url, "000", "")
        seed_no_wayback(url)
        ok, reason = verify_url(url, ["anything"])
        assert ok is False
        assert reason == "HTTP 000 (no Wayback snapshot)"
        assert classify(reason) == "dead"

    @pytest.mark.parametrize("status", ["401", "403", "429", "503"])
    def test_block_statuses_are_blocked_not_dead(self, status):
        url = f"https://example.com/{status}"
        seed(url, status, _page("x"))
        seed_no_wayback(url)
        ok, reason = verify_url(url, ["anything"])
        assert ok is False
        assert reason.startswith(f"blocked: HTTP {status}")
        assert classify(reason) == "blocked"


class TestWaybackFallback:
    def test_blocked_live_passes_via_snapshot_with_content(self):
        url = "https://www.tradewindsnews.com/gas/story"
        seed(url, "403", "")
        seed_wayback(url, ["20260601120000"], _page("story", "Knutsen orders at Hyundai Samho"))
        ok, reason = verify_url(url, ["Knutsen", "Hyundai Samho"])
        assert ok is True
        assert reason.startswith("OK (via Wayback 20260601120000")
        assert classify(reason) == "ok"

    def test_snapshot_lacking_content_stays_blocked(self):
        url = "https://www.tradewindsnews.com/gas/story"
        seed(url, "403", "")
        seed_wayback(url, ["20260601120000"], _page("story", "something else"))
        ok, reason = verify_url(url, ["Knutsen"])
        assert ok is False
        assert classify(reason) == "blocked"
        assert "lack expected content" in reason

    def test_cdx_snapshots_are_tried_when_availability_is_empty(self):
        from urllib.parse import quote
        url = "https://example.com/blocked"
        seed(url, "429", "")
        q = quote(url, safe="")
        seed(url_verifier._WB_AVAIL.format(u=q), "200", json.dumps({"archived_snapshots": {}}))
        seed(url_verifier._WB_CDX.format(u=q), "200",
             json.dumps([["timestamp", "statuscode"], ["20250101000000", "200"],
                         ["20260301000000", "200"]]))
        seed(url_verifier._WB_SNAP.format(ts="20250101000000", u=url), "200", _page("t", "old"))
        seed(url_verifier._WB_SNAP.format(ts="20260301000000", u=url), "200", _page("t", "Maran Gas"))
        ok, reason = verify_url(url, ["Maran Gas"])
        assert ok is True
        assert "20260301000000" in reason

    def test_wayback_disabled(self):
        url = "https://example.com/blocked"
        seed(url, "403", "")
        url_verifier.WAYBACK_ENABLED = False
        ok, reason = verify_url(url, ["x"])
        assert classify(reason) == "blocked"
        assert "Wayback disabled" in reason

    def test_dead_404_never_consults_wayback(self):
        # no wayback endpoints seeded -> would raise if consulted
        url = "https://example.com/gone"
        seed(url, "404", "")
        assert verify_url(url, ["x"]) == (False, "HTTP 404")


class TestBannedShapes:
    @pytest.mark.parametrize("url, frag", [
        ("https://www.gem.wiki/Some_LNG_Carrier", "GEM"),
        ("https://globalenergymonitor.org/projects/x", "GEM"),
        ("https://abarrelfull.wikidot.com/x", "blocklisted"),
        ("http://www.theodora.com/x", "blocklisted"),
        ("https://bit.ly/3xyz", "shortener"),
        ("https://t.co/abc", "shortener"),
        ("https://web.archive.org/save/https://example.com/x", "capture endpoint"),
        ("https://web.archive.org/web/2026/https://www.gem.wiki/X", "banned host"),
        ("https://splash247.com/?s=maran+gas", "navigation"),
        ("https://lngprime.com/search?q=knutsen", "navigation"),
        ("https://www.rivieramm.com/tag/lng-carriers/", "navigation"),
        ("https://www.tradewindsnews.com/category/gas/page/3", "navigation"),
        ("https://splash247.com/author/sam-chambers/", "navigation"),
        ("ftp://example.com/x", "not an http"),
    ])
    def test_banned_without_fetching(self, url, frag):
        ok, reason = verify_url(url, ["anything"])
        assert ok is False
        assert classify(reason) == "banned"
        assert frag in reason
        assert url_ban_reason(url) == reason

    @pytest.mark.parametrize("url", [
        "https://www.google.com/maps/place/Seatrium+Admiralty+Yard/@1.4599064,103.8,17z",
        "https://maps.app.goo.gl/aXheTTWUa76FHyui7",
        "https://lngprime.com/asia/knutsen-orders/12345/",
        "https://www.tradewindsnews.com/gas/pages-of-history/2-1-1",
        "https://web.archive.org/web/20260101000000/https://lngprime.com/x",
        "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=2026",
    ])
    def test_legit_shapes_are_not_banned(self, url):
        assert url_ban_reason(url) is None

    def test_article_url_with_search_word_in_slug_is_fine(self):
        assert url_ban_reason("https://example.com/news/research-vessel-order/") is None


class TestRedirects:
    def test_redirect_to_banned_host_fails(self):
        url = "https://example.com/x"
        seed_page(url, "200", _page("t", "Maran Gas"), final_url="https://www.gem.wiki/X")
        ok, reason = verify_url(url, ["Maran Gas"])
        assert classify(reason) == "banned"

    def test_deep_link_redirected_to_homepage_is_soft_error(self):
        url = "https://example.com/news/2024/story-that-was-removed"
        seed_page(url, "200", _page("Example Home", "Maran Gas Samsung"),
                  final_url="https://example.com/")
        ok, reason = verify_url(url, ["Maran Gas"])
        assert ok is False
        assert classify(reason) == "dead"
        assert "site root" in reason

    def test_id_keyed_redirect_to_different_article_is_soft_error(self):
        # TradeWinds resolves by the trailing id and rewrites the slug: a cited
        # "woodside-...-newbuildings/2-1-1875739" that serves "greek-shipowners-
        # take-nuclear-leap-of-faith/2-1-1875739" was never the Woodside story.
        url = ("https://www.tradewindsnews.com/gas/woodside-energy-poised-to-kick-off-hunt-"
               "for-large-haul-of-lng-carrier-newbuildings/2-1-1875739")
        seed_page(url, "200", _page("Greek shipowners take nuclear leap", "Woodside"),
                  final_url="https://www.tradewindsnews.com/sustainability/greek-shipowners-"
                            "take-nuclear-leap-of-faith-at-tradewinds-forum-in-athens/2-1-1875739")
        ok, reason = verify_url(url, ["Woodside"])
        assert ok is False
        assert classify(reason) == "dead"
        assert "different article" in reason

    def test_slug_rewrite_of_same_article_is_fine(self):
        url = "https://example.com/gas/knutsen-orders-two-lng-carriers-hyundai-samho/2-1-1"
        seed_page(url, "200", _page("t", "Knutsen"),
                  final_url="https://example.com/gas/knutsen-orders-two-lng-carriers-at-hyundai-samho-amp/2-1-1")
        assert verify_url(url, ["Knutsen"])[0] is True

    def test_ordinary_redirect_keeps_working(self):
        url = "http://example.com/story"
        seed_page(url, "200", _page("t", "Maran Gas"), final_url="https://www.example.com/story/")
        assert verify_url(url, ["Maran Gas"])[0] is True

    def test_maps_short_link_must_land_on_google_maps(self):
        url = "https://maps.app.goo.gl/aXheTTWUa76FHyui7"
        seed_page(url, "200", _page("Yard", "Samsung"),
                  final_url="https://www.google.com/maps/place/Samsung+Heavy/@35,129,17z")
        assert verify_url(url, ["Samsung"])[0] is True
        seed_page(url, "200", _page("Yard", "Samsung"), final_url="https://evil.example/")
        assert classify(verify_url(url, ["Samsung"])[1]) == "banned"


class TestPdf:
    def test_pdf_text_is_matched_and_titles_ignored(self):
        url = "https://dart.example/filing.pdf"
        # extracted text of a scanned filing — no <title>, "404" would be a
        # soft-error hit for HTML but PDFs are judged on text only
        seed_page(url, "200", "Hull 2404 ... 174,000 cbm LNG carrier for Knutsen OAS\nPage 1",
                  is_pdf=True, notes=["pdf_ocr"])
        ok, reason = verify_url(url, ["174,000", "Knutsen OAS"])
        assert ok is True
        assert "pdf_ocr" in reason
        assert classify(reason) == "ok"


class TestStrictMode:
    def test_strict_raises_on_failure(self):
        url = "https://example.com/gone"
        seed(url, "404", _page("x"))
        with pytest.raises(CitationError):
            verify_url(url, ["anything"], strict=True)

    def test_strict_returns_normally_on_pass(self):
        url = "https://example.com/ok"
        seed(url, "200", _page("ok", "Samsung"))
        ok, _ = verify_url(url, ["Samsung"], strict=True)
        assert ok is True

    def test_strict_raises_on_banned(self):
        with pytest.raises(CitationError):
            verify_url("https://www.gem.wiki/X", ["x"], strict=True)


class TestCorroborates:
    def test_numeric_value_matches_grouped_rendering(self):
        url = "https://example.com/x"
        seed(url, "200", _page("t", "a 174,000-cbm vessel"))
        assert corroborates(url, "174000")[0] is True

    def test_numeric_value_does_not_match_superstring(self):
        url = "https://example.com/x"
        seed(url, "200", _page("t", "the 1,174,000 cbm fleet total"))
        ok, reason = corroborates(url, "174000")
        assert ok is False
        assert classify(reason) == "uncorroborated"
        assert "does not contain value" in reason

    def test_date_renderings(self):
        for v in ("08-Jun-2026", "08-June-2026"):
            got = value_variants(v)
            for want in ("8 June 2026", "June 8, 2026", "Jun 8, 2026", "2026-06-08", "2026.06.08"):
                assert want in got
        url = "https://example.com/d"
        seed(url, "200", _page("t", "the contract was signed on June 8, 2026 with the yard"))
        assert corroborates(url, "08-Jun-2026")[0] is True
        assert corroborates(url, "09-Jun-2026")[0] is False

    def test_status_active_needs_past_tense_delivery(self):
        url = "https://example.com/s1"
        seed(url, "200", _page("t", "The owner took delivery of the 174,000-cbm carrier on Monday"))
        assert corroborates(url, "active")[0] is True
        url2 = "https://example.com/s2"
        seed(url2, "200", _page("t", "The carrier will be delivered in 2027"))
        assert corroborates(url2, "active")[0] is False

    def test_hull_number_yard_tag_is_not_required(self):
        got = value_variants("Hull 2598 (Hanwha)")
        assert "Hull 2598" in got and "H2598" in got and "2598" in got
        assert "042" not in value_variants("Hull 042 (Zvezda)")

    def test_abbreviated_owner_matches_spelled_out_name(self):
        got = value_variants("ADNOC L&S")
        assert "ADNOC L&S" in got and "ADNOC Logistics & Services" in got
        # one way only: a long value never picks up the bare abbreviation
        assert "ADNOC L&S" not in value_variants("ADNOC Logistics & Services")
        url = "https://example.com/csb"
        seed(url, "200", _page("t", "Owner: ADNOC Logistics &amp; Services (UAE)"))
        assert corroborates(url, "ADNOC L&S")[0] is True

    def test_price_abbreviations(self):
        assert "$250m" in value_variants("250000000")
        assert "250 million" in value_variants("$250,000,000")
        url = "https://example.com/x"
        seed(url, "200", _page("t", "worth about $250 million each"))
        assert corroborates(url, "250000000")[0] is True

    def test_multiword_text_tokens_fallback(self):
        url = "https://example.com/x"
        seed(url, "200", _page("t", "Knutsen OAS Shipping signed with Hyundai"))
        ok, reason = corroborates(url, "Knutsen OAS")
        assert ok is True
        seed(url, "200", _page("t", "the Knutsen fleet"))
        assert corroborates(url, "Knutsen OAS")[0] is False

    def test_blank_value_passes(self):
        assert corroborates("https://example.com/x", "") == (True, "no value to corroborate")

    def test_blocked_ref_reports_blocked(self):
        url = "https://example.com/x"
        seed(url, "403", "")
        seed_no_wayback(url)
        ok, reason = corroborates(url, "174000")
        assert ok is False
        assert classify(reason) == "blocked"


class TestCheckUrl:
    def test_health_verdicts(self):
        seed("https://a.example/ok", "200", _page("fine", "x"))
        seed("https://a.example/gone", "404", "")
        seed("https://a.example/wall", "403", "")
        seed_no_wayback("https://a.example/wall")
        assert check_url("https://a.example/ok")["verdict"] == "ok"
        assert check_url("https://a.example/gone")["verdict"] == "dead"
        w = check_url("https://a.example/wall")
        assert w["verdict"] == "blocked" and w["status"] == "403"
        assert check_url("https://www.gem.wiki/X")["verdict"] == "banned"


class TestAuditLog:
    def test_jsonl_record_per_verdict(self, tmp_path):
        log = tmp_path / "v.jsonl"
        url_verifier.set_log_path(str(log))
        url = "https://example.com/x"
        seed(url, "200", _page("t", "Samsung"))
        verify_url(url, ["Samsung"])
        verify_url("https://www.gem.wiki/X", ["x"])
        recs = [json.loads(line) for line in log.read_text().splitlines()]
        assert len(recs) == 2
        assert recs[0]["url"] == url and recs[0]["ok"] is True and recs[0]["status"] == "200"
        assert recs[1]["ok"] is False and classify(recs[1]["reason"]) == "banned"


class TestWaybackAvailability:
    def test_wayback_429_is_reported_not_no_snapshot(self):
        url = "https://example.com/walled"
        seed(url, "403", "")
        seed_wayback_status(url, "429")
        ok, reason = verify_url(url, ["x"])
        assert not ok
        assert reason == "blocked: HTTP 403 (Wayback rate-limited (HTTP 429))"
        assert classify(reason) == "blocked"

    def test_wayback_retry_after_429(self, monkeypatch):
        url = "https://example.com/walled2"
        seed(url, "403", "")
        seed_wayback_status(url, "429")
        url_verifier.WAYBACK_RETRIES = 1
        url_verifier.WAYBACK_RETRY_DELAY = 0
        calls = []

        def _fake_fetch(u, **kw):
            calls.append(u)
            from urllib.parse import quote
            q = quote(url, safe="")
            if u == url_verifier._WB_AVAIL.format(u=q):
                return Page(status="200", text=json.dumps({"archived_snapshots": {"closest": {
                    "available": True, "url": f"https://web.archive.org/web/20250101000000/{url}"}}}))
            if u == url_verifier._WB_CDX.format(u=q):
                return Page(status="200", text="[]")
            if u.startswith("https://web.archive.org/web/20250101000000"):
                return Page(status="200", text="<html><body>snapshot has x</body></html>")
            raise AssertionError(u)
        monkeypatch.setattr(url_verifier, "fetch_page", _fake_fetch)
        ok, reason = verify_url(url, ["x"])
        assert ok and reason.startswith("OK (via Wayback 20250101000000")
        assert calls, "retry should have re-fetched the API uncached"

    def test_wayback_offline_html_is_not_no_snapshot(self):
        from urllib.parse import quote
        url = "https://example.com/walled3"
        seed(url, "403", "")
        q = quote(url, safe="")
        offline = "<html><head><title>Internet Archive: Temporarily Offline</title></head></html>"
        seed(url_verifier._WB_AVAIL.format(u=q), "200", offline)
        seed(url_verifier._WB_CDX.format(u=q), "200", offline)
        ok, reason = verify_url(url, ["x"])
        assert reason == "blocked: HTTP 403 (Wayback unavailable (Internet Archive: Temporarily Offline))"

    def test_202_empty_is_blocked(self):
        url = "https://investors.example.com/newsroom/x"
        seed(url, "202", "")
        seed_no_wayback(url)
        ok, reason = verify_url(url, ["x"])
        assert classify(reason) == "blocked"
        assert reason == "blocked: HTTP 202 (no Wayback snapshot)"

    def test_000_without_snapshot_is_dead(self):
        url = "https://gone.example.cn/"
        seed(url, "000", "")
        seed_no_wayback(url)
        ok, reason = verify_url(url, ["yard"])
        assert reason == "HTTP 000 (no Wayback snapshot)"
        assert classify(reason) == "dead"

    def test_000_with_snapshot_is_blocked_or_ok(self):
        url = "https://geo.example.cn/page"
        seed(url, "000", "")
        seed_wayback(url, ["20250301000000"], "<html><body>Jiangnan yard</body></html>")
        ok, reason = verify_url(url, ["Jiangnan"])
        assert ok and "via Wayback" in reason
        ok, reason = verify_url(url, ["Hudong"])
        assert not ok
        assert reason == "blocked: HTTP 000 (1 Wayback snapshot(s) lack expected content)"
        assert classify(reason) == "blocked"

    def test_health_check_never_upgrades_a_wall(self):
        url = "https://walled.example.com/article"
        seed(url, "403", "")
        seed_wayback(url, ["20240527053802"], "<html><body>full article</body></html>")
        info = check_url(url)
        assert info["verdict"] == "blocked"
        assert info["reason"] == "blocked: HTTP 403 (Wayback snapshot 20240527053802 exists; no content to confirm)"

    def test_clear_cache_single_url_drops_wayback_lookups(self):
        from urllib.parse import quote
        url = "https://example.com/one"
        seed(url, "403", "")
        seed_wayback_status(url, "429")
        q = quote(url, safe="")
        clear_cache(url)
        assert url not in url_verifier._CACHE
        assert url_verifier._WB_AVAIL.format(u=q) not in url_verifier._CACHE


class TestRawSourceMatching:
    CSS_PAGE = ("<html><head><title>Story</title><style>:root{--x-font-size:16px;--y:20px}</style>"
                "<meta property=\"og:description\" content=\"Shipbuilders holding 2028 berths\">"
                "<script>var n = 999;</script>"
                "<script type=\"application/ld+json\">{\"headline\":\"Hull 3417 ordered\"}</script>"
                "<link rel=\"icon\" sizes=\"16x16\" href=\"/favicon-16x16.png\">"
                "</head><body style=\"width:174px\"><svg><path d=\"M0 0v20.9c0 6.74\"/></svg>"
                "<img alt=\"Hull 3418 at the yard\"><div data-imo=\"9975521\"></div>"
                "<p>Woodside Energy</p></body></html>")

    def test_css_does_not_satisfy_numeric_needle(self):
        assert not url_verifier._page_contains(self.CSS_PAGE, "16")
        assert not url_verifier._page_contains(self.CSS_PAGE, "20")
        assert not url_verifier._page_contains(self.CSS_PAGE, "174")

    def test_plain_script_does_not_count(self):
        assert not url_verifier._page_contains(self.CSS_PAGE, "999")

    def test_favicon_sizes_and_svg_paths_do_not_count(self):
        assert not url_verifier._page_contains(self.CSS_PAGE, "16")
        assert not url_verifier._page_contains(self.CSS_PAGE, "6.74")

    NUXT_PAGE = ("<html><body><script type=\"application/json\" id=\"__NUXT_DATA__\">"
                 "[{\"type\":16,\"id\":20},\"requirements for between 16 and 20 LNG carrier "
                 "newbuildings\",{\"slot\":77}]</script><p>Woodside</p></body></html>")

    def test_hex_hashes_and_urls_do_not_count(self):
        page = ("<html><head><meta property=\"og:image\" content=\"https://img.example/binary/77ec82c4\">"
                "</head><body><p>Hull 3417 at 174,000 cbm, 16px-free prose</p></body></html>")
        assert not url_verifier._page_contains(page, "77")
        assert not url_verifier._page_contains(page, "16")
        assert url_verifier._page_contains(page, "174,000")
        assert url_verifier._page_contains(page, "3417")

    def test_json_payload_matches_strings_not_bare_integers(self):
        assert url_verifier._page_contains(self.NUXT_PAGE, "between 16 and 20 LNG carrier newbuildings")
        assert url_verifier._page_contains(self.NUXT_PAGE, "16")
        assert not url_verifier._page_contains(self.NUXT_PAGE, "77")

    def test_meta_json_ld_and_data_attrs_still_count(self):
        assert url_verifier._page_contains(self.CSS_PAGE, "2028")
        assert url_verifier._page_contains(self.CSS_PAGE, "3417")
        assert url_verifier._page_contains(self.CSS_PAGE, "3418")
        assert url_verifier._page_contains(self.CSS_PAGE, "9975521")
        assert url_verifier._page_contains(self.CSS_PAGE, "Woodside Energy")


class TestHostAdapters:
    """SPA shells (shipvault.com, marinetraffic.com) are verified against the
    JSON the page itself loads — the shell alone can never corroborate."""

    SV_PAGE = "https://www.shipvault.com/ships/465056"
    SV_API = url_verifier.SHIPVAULT_API.format(id="465056")
    MT_PAGE = ("https://www.marinetraffic.com/en/ais/details/ships/shipid:9034461/"
               "mmsi:636023560/imo:9953274/vessel:LIMAIL")
    MT_API = url_verifier.MARINETRAFFIC_COM_API.format(id="9034461")
    SHELL = _page("ShipVault", "<app-root></app-root>")

    def test_shipvault_matches_against_unit_record(self):
        seed_page(self.SV_PAGE, "200", self.SHELL, notes=["cf_impersonate"])
        seed(self.SV_API, "200", json.dumps([{"unitid": 465056, "name": "HULL 2580",
                                              "owner": "MITSUI OSK LINES LTD", "imo": 1140761,
                                              "yard": "HANWHA OCEAN", "yardno": "2580",
                                              "built": 2027, "month": 3, "events": []}]))
        ok, reason = verify_url(self.SV_PAGE, ["HULL 2580", "MITSUI OSK", "1140761", "2027-03"])
        assert ok and reason == "OK (cf_impersonate, shipvault_api)"
        ok, reason = verify_url(self.SV_PAGE, ["HULL 9999"])
        assert not ok and classify(reason) == "uncorroborated"

    def test_shipvault_unknown_unit_is_dead(self):
        seed(self.SV_PAGE, "200", self.SHELL)
        seed(self.SV_API, "200", "[]")
        ok, reason = verify_url(self.SV_PAGE, ["x"])
        assert not ok and classify(reason) == "dead"
        assert "465056" in reason

    def test_shipvault_api_wall_is_blocked_not_dead(self):
        seed(self.SV_PAGE, "200", self.SHELL)
        seed(self.SV_API, "403", "")
        ok, reason = verify_url(self.SV_PAGE, ["x"])
        assert not ok and classify(reason) == "blocked"

    def test_shipvault_double_encoded_json(self):
        seed(self.SV_PAGE, "200", self.SHELL)
        seed(self.SV_API, "200", json.dumps(json.dumps([{"name": "HULL 2580"}])))
        assert verify_url(self.SV_PAGE, ["HULL 2580"])[0]

    def test_shipvault_api_url_verifies_like_its_page(self):
        # the unit-record endpoint is the companion ref for a page that renders
        # blank; it is gated on the same rendered record (incl. the derived delivery)
        seed(self.SV_API, "200", json.dumps(json.dumps([{"unitid": 465056, "name": "HULL 2580",
                                                         "cap1": 174000, "built": 2027, "month": 3}])))
        ok, reason = verify_url(self.SV_API, ["HULL 2580", "174000", "2027-03"])
        assert ok and reason == "OK (shipvault_api)"
        assert not verify_url(self.SV_API, ["135000"])[0]

    def test_shipvault_record_dates_and_prices_match_cell_forms(self):
        # an ISO timestamp / whole-dollar price never sits on a match boundary;
        # the adapter renders the date alone and the price in $m, as cells carry them
        seed(self.SV_API, "200", json.dumps([{"name": "PUTERI DELIMA SATU",
                                              "ordered": "1999-04-01T00:00:00",
                                              "newprice": 165000000}]))
        assert corroborates(self.SV_API, "1-Apr-1999")[0]
        assert corroborates(self.SV_API, "165")[0]
        assert not corroborates(self.SV_API, "1-May-1999")[0]
        assert not corroborates(self.SV_API, "166")[0]

    def test_marinetraffic_com_matches_against_vesselinfo(self):
        seed(self.MT_PAGE, "200", _page("MarineTraffic: Global Ship Tracking", "<div id=app>"))
        seed(self.MT_API, "200", json.dumps({"name": "LIMAIL", "imo": 9953274,
                                             "typeSpecific": "LNG Tanker", "yearBuilt": 2025}))
        ok, reason = verify_url(self.MT_PAGE, ["LIMAIL", "9953274", "LNG Tanker"])
        assert ok and reason == "OK (marinetraffic_api)"
        assert not verify_url(self.MT_PAGE, ["EVER GIVEN"])[0]

    def test_marinetraffic_com_unknown_shipid_is_dead(self):
        seed(self.MT_PAGE, "200", _page("MarineTraffic", "<div id=app>"))
        seed(self.MT_API, "404", "")
        ok, reason = verify_url(self.MT_PAGE, ["LIMAIL"])
        assert not ok and classify(reason) == "dead"

    def test_marinetraffic_com_news_page_has_no_adapter(self):
        url = "https://www.marinetraffic.com/is/maritime-news/16/general/2025/12432/cnooc-story"
        seed(url, "200", _page("CNOOC takes delivery", "<p>Greenergy Star delivered by Hudong</p>"))
        assert verify_url(url, ["Greenergy Star"]) == (True, "OK")

    def test_cloudflare_telemetry_beacon_is_not_a_wall(self):
        # every page of a Bot-Management site carries this script; only the
        # /h/ challenge path means a wall.
        url = "https://www.marinetraffic.com/is/maritime-news/1/x"
        seed(url, "200", _page("Greenergy Star delivered",
             "<p>short</p><script>a.src='/cdn-cgi/challenge-platform/scripts/jsd/main.js'</script>"))
        assert verify_url(url, ["Greenergy"]) == (True, "OK")
        wall = "https://www.example.com/walled"
        seed(wall, "200", _page("Site", "<script src='/cdn-cgi/challenge-platform/h/b/orchestrate/x'>"))
        seed_no_wayback(wall)
        ok, reason = verify_url(wall, ["x"])
        assert not ok and classify(reason) == "blocked"


def test_status_on_order_corroborated_by_order_wording():
    vs = [x.lower() for x in url_verifier.value_variants("on order")]
    assert "has ordered" in vs and "shipbuilding contract" in vs
    assert "delivered" not in vs


def test_status_scrapped_corroborated_by_demolition_wording():
    vs = [x.lower() for x in url_verifier.value_variants("scrapped")]
    assert "sold for demolition" in vs and "sold for recycling" in vs and "scrapped" in vs
    assert "took delivery" not in vs and "on order" not in vs


def test_untagged_hull_number():
    vs = url_verifier.value_variants("Hull H2706")
    assert "H2706" in vs and "Hull H2706" in vs


def test_igu_landing_page_has_a_citable_form():
    landing = "https://www.igu.org/igu-reports/2025-world-lng-report"
    assert url_verifier.citable_form(landing) == url_verifier.IGU_PDF["2025"]
    assert url_verifier.citable_form(landing + "/") == url_verifier.IGU_PDF["2025"]
    assert url_verifier.citable_form("https://www.igu.org/igu-reports/2019-world-lng-report") \
        == "https://www.igu.org/igu-reports/2019-world-lng-report"          # no PDF known: unchanged
    assert url_verifier.citable_form("https://example.org/a") == "https://example.org/a"
    assert url_verifier.citable_forms([landing, url_verifier.IGU_PDF["2025"], "https://example.org/a"]) \
        == [url_verifier.IGU_PDF["2025"], "https://example.org/a"]


def test_dollar_figure_in_title_is_not_a_status_code():
    assert url_verifier._title_hit("DSME wins $500 million LNG carrier order", url_verifier._SOFT_ERROR_TITLES) is None
    assert url_verifier._title_hit("500 Internal Server Error", url_verifier._SOFT_ERROR_TITLES)
    assert url_verifier._title_hit("404 Not Found", url_verifier._SOFT_ERROR_TITLES)


class TestHostPacing:
    def test_same_host_waits_its_floor_other_host_does_not(self, monkeypatch):
        clock, slept = [100.0], []
        monkeypatch.setattr(url_verifier.time, "monotonic", lambda: clock[0])
        monkeypatch.setattr(url_verifier.time, "sleep", lambda s: (slept.append(s), clock.__setitem__(0, clock[0] + s)))
        monkeypatch.setattr(url_verifier.random, "uniform", lambda a, b: 0.0)
        monkeypatch.setattr(url_verifier, "fetch_page", lambda url, **kw: Page(status="200", text="x"))
        url_verifier.HOST_MIN_GAP = 2.0
        url_verifier._LAST_FETCH.clear()
        url_verifier._fetch("https://www.bloomberg.com/a")
        url_verifier._fetch("https://example.com/a")
        assert slept == []
        url_verifier._fetch("https://bloomberg.com/b")        # www. and bare share a floor
        assert slept == [30.0]
        url_verifier._fetch("https://example.com/b")
        assert slept == [30.0]                                # 30 s already passed for example.com
        url_verifier._fetch("https://example.com/c")
        assert slept == [30.0, 2.0]
        url_verifier._fetch("https://example.com/c")          # cached: no fetch, no wait
        assert slept == [30.0, 2.0]


# --- Vessel type: article text, next to vessel wording (Baird 2026-09-23) ---

_VT_FILLER = "<p>" + "The order was placed with the yard in Geoje this week. " * 6 + "</p>"


def _vt_page(article, sidebar=""):
    return (f"<html><head><title>t</title></head><body><nav><a href='/'>Home</a></nav>"
            f"<article><h1>Order</h1>{_VT_FILLER}{article}</article>"
            f"<div class='sidebar widget-area'>{sidebar}</div>"
            f"<footer>conventional LNG carrier footer text</footer></body></html>")


@pytest.mark.parametrize("article,sidebar,ok", [
    ("<p>Two conventional 174,000 cbm LNG carriers.</p>", "", True),
    ("<p>The LNG carriers are of conventional design.</p>", "", True),
    ("<p>An 85% cut compared to conventional marine fuels on the new LNG carrier.</p>", "", False),
    ("<p>Two 174,000 cbm LNG carriers.</p>",
     "<ul><li><a href='/x'>Fuel switch: biofuel prices against conventionals</a></li>"
     "<li>conventional LNG carriers see rates fall</li></ul>", False),
    ("<p>Read <a href='/y'>conventional LNG carrier rates</a> here.</p>", "", False),
])
def test_vessel_type_counts_only_in_article_next_to_vessel_wording(article, sidebar, ok):
    url = "https://news.example.com/vt"
    seed(url, "200", _vt_page(article, sidebar))
    got, reason = corroborates(url, "conventional", field="Vessel type")
    assert got is ok, reason
    if not ok:
        assert reason.startswith("page does not contain")


def test_vessel_type_self_noun_and_other_fields_unchanged():
    url = "https://news.example.com/fsru"
    seed(url, "200", _vt_page("<p>The FSRU arrived at the terminal.</p>"))
    assert corroborates(url, "FSRU", field="Vessel type")[0]
    # without the field the plain substring gate still applies (footer text counts)
    url2 = "https://news.example.com/plain"
    seed(url2, "200", _vt_page("<p>Two 174,000 cbm LNG carriers.</p>"))
    assert corroborates(url2, "conventional")[0]
    assert not corroborates(url2, "conventional", field="Vessel type")[0]


def test_vessel_type_pdf_text_is_read_whole():
    url = "https://example.com/report.pdf"
    seed_page(url, "200", "Fleet overview: 12 conventional LNG carriers delivered in 2025.",
              is_pdf=True)
    assert corroborates(url, "conventional", field="Vessel type")[0]
