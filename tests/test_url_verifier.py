"""Tests for scripts/url_verifier.py — the §3.8 verification gate.

The gate's three checks (HTTP 200, no soft-error title, required content present)
are what keep dead/hallucinated/rate-limited URLs out of the xlsx. We exercise
them offline by pre-seeding the module's per-process _CACHE: verify_url() reads
the cache before it would ever shell out to curl, so no test touches the network
(tests/README.md: "Tests should never hit the network").
"""
import pytest

import url_verifier
from url_verifier import CitationError, clear_cache, verify_url


def seed(url, status, body):
    """Plant a (status, body) response in the fetch cache for `url`."""
    url_verifier._CACHE[url] = (status, body)


@pytest.fixture(autouse=True)
def _clean_cache():
    clear_cache()
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


class TestContentChecks:
    def test_missing_expected_content_fails(self):
        url = "https://example.com/x"
        seed(url, "200", _page("t", "Maran Gas at Samsung"))
        ok, reason = verify_url(url, ["Maran Gas", "Knutsen"])
        assert ok is False
        assert "Knutsen" in reason

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


class TestSoftErrorDetection:
    @pytest.mark.parametrize("title", [
        "404 Not Found",
        "Page Not Found",
        "429 Too Many Requests",
        "Just a moment...",        # Cloudflare interstitial
        "Attention Required! | Cloudflare",
        "Access Denied",
    ])
    def test_soft_error_titles_fail_even_with_200(self, title):
        # A 200 response whose title is an error template must not pass — this is
        # the Riviera-429 / Cloudflare class the gate exists to catch.
        url = f"https://example.com/{title}"
        seed(url, "200", _page(title, "Maran Gas Samsung 174,000"))
        ok, reason = verify_url(url, ["Maran Gas"])
        assert ok is False
        assert "soft-error" in reason

    def test_legitimate_title_is_not_flagged(self):
        url = "https://example.com/ok"
        seed(url, "200", _page("Maran Gas orders two LNG carriers", "Maran Gas"))
        ok, _ = verify_url(url, ["Maran Gas"])
        assert ok is True


class TestHttpStatus:
    def test_non_200_fails_with_status_in_reason(self):
        url = "https://example.com/gone"
        seed(url, "404", _page("whatever"))
        ok, reason = verify_url(url, ["anything"])
        assert ok is False
        assert reason == "HTTP 404"

    def test_curl_failure_000_fails(self):
        url = "https://unreachable.invalid/x"
        seed(url, "000", "")
        ok, reason = verify_url(url, ["anything"])
        assert ok is False
        assert reason == "HTTP 000"


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
