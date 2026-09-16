"""Tests for scripts/fetch.py's Cloudflare escalation ladder and the
cf_clearance cookie store.

Nothing here touches the network or launches Chrome: `_curl`, `_cffi_get` and
`_earn_clearance` are stubbed, and the cookie store is pointed at a temp dir.
"""
import subprocess
from pathlib import Path

import cf_clearance
import fetch
import pytest

_REAL_EARN = fetch._earn_clearance      # captured before the autouse stub replaces it

WALL_403 = b"<html><head><title>Just a moment...</title></head><body>cf_chl_opt</body></html>"
FIREWALL = b"<html><head><title>Attention Required! | Cloudflare</title></head></html>"
REAL = b"<html><head><title>HULL 2616 - LNG Tanker</title></head><body>HANWHA OCEAN</body></html>"


class FakeCurl:
    """Scripted `_curl`: answers (status, body) per (cookie present?) and records calls."""

    def __init__(self, plain=("403", WALL_403), with_cookie=("200", REAL)):
        self.plain, self.with_cookie = plain, with_cookie
        self.calls = []

    def __call__(self, url, tmp, timeout, ua, insecure, headers=None, cookie=None):
        self.calls.append({"url": url, "ua": ua, "headers": headers, "cookie": cookie})
        status, body = self.with_cookie if cookie else self.plain
        Path(tmp).write_bytes(body)
        return subprocess.CompletedProcess(
            args=["curl"], returncode=0, stdout=f"{status}\ttext/html\t{url}", stderr="")


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(cf_clearance, "store_path", lambda: tmp_path / "cf.json")
    monkeypatch.setattr(fetch, "require_curl", lambda: None)
    monkeypatch.setattr(fetch, "_earn_clearance", lambda url: (None, None))
    monkeypatch.setattr(fetch, "_cffi_get", lambda *a, **k: None)
    fetch._IMPERSONATE_HOSTS.clear()
    fetch._CLEARANCE_TRIED.clear()
    yield
    fetch._IMPERSONATE_HOSTS.clear()
    fetch._CLEARANCE_TRIED.clear()


class TestWallDetection:
    def test_challenge_page_is_a_wall(self):
        assert fetch._is_cf_wall("403", WALL_403)
        assert fetch._is_cf_wall("503", FIREWALL)

    def test_plain_403_without_markers_is_not(self):
        assert not fetch._is_cf_wall("403", b"<html>Forbidden by origin</html>")

    def test_200_with_markers_is_not(self):
        # an article ABOUT Cloudflare is content, not a wall
        assert not fetch._is_cf_wall("200", WALL_403)


class TestLadder:
    def test_plain_page_needs_no_escalation(self, monkeypatch):
        curl = FakeCurl(plain=("200", REAL))
        monkeypatch.setattr(fetch, "_curl", curl)
        p = fetch.fetch_page("https://example.com/x")
        assert p.status == "200" and p.notes == [] and len(curl.calls) == 1

    def test_firewall_page_falls_back_to_impersonation(self, monkeypatch):
        curl = FakeCurl(plain=("403", FIREWALL))
        monkeypatch.setattr(fetch, "_curl", curl)
        monkeypatch.setattr(fetch, "_cffi_get",
                            lambda url, t, ua, h, c: ("200", "text/html", url, REAL))
        p = fetch.fetch_page("https://www.shipvault.com/ships/1")
        assert p.status == "200" and "HANWHA" in p.text
        assert p.notes == ["cf_impersonate"]
        # the host is remembered: the next fetch skips curl entirely
        p2 = fetch.fetch_page("https://www.shipvault.com/ships/2")
        assert p2.notes == ["cf_impersonate"] and len(curl.calls) == 1

    def test_memoised_impersonation_that_walls_again_falls_through(self, monkeypatch):
        curl = FakeCurl()
        monkeypatch.setattr(fetch, "_curl", curl)
        fetch._IMPERSONATE_HOSTS.add("www.shipvault.com")
        monkeypatch.setattr(fetch, "_cffi_get",
                            lambda url, t, ua, h, c: ("403", "text/html", url, WALL_403))
        monkeypatch.setattr(fetch, "_earn_clearance",
                            lambda url: ("cf_clearance=abc", "UA-153"))
        p = fetch.fetch_page("https://www.shipvault.com/ships/1")
        assert p.status == "200" and p.notes == ["cf_clearance"]
        assert "www.shipvault.com" not in fetch._IMPERSONATE_HOSTS

    def test_js_challenge_earns_a_cookie_then_retries_curl(self, monkeypatch):
        curl = FakeCurl()
        monkeypatch.setattr(fetch, "_curl", curl)
        # impersonation alone does not pass the JS challenge
        monkeypatch.setattr(fetch, "_cffi_get",
                            lambda url, t, ua, h, c: ("403", "text/html", url, WALL_403))
        monkeypatch.setattr(fetch, "_earn_clearance",
                            lambda url: ("cf_clearance=abc", "Mozilla/5.0 Chrome/153"))
        p = fetch.fetch_page("https://www.marinetraffic.org/v/1")
        assert p.status == "200" and p.notes == ["cf_clearance"]
        assert curl.calls[-1]["cookie"] == "cf_clearance=abc"
        assert curl.calls[-1]["ua"] == "Mozilla/5.0 Chrome/153"   # cookie needs its own UA

    def test_stored_cookie_is_sent_up_front(self, monkeypatch):
        cf_clearance.save_store({"ua": "UA-153", "cookies": {
            ".marinetraffic.org": {"value": "zzz", "expires": 4e9, "saved": 0}}})
        curl = FakeCurl()
        monkeypatch.setattr(fetch, "_curl", curl)
        p = fetch.fetch_page("https://www.marinetraffic.org/v/1")
        assert p.status == "200" and p.notes == ["cf_clearance"]
        assert len(curl.calls) == 1 and curl.calls[0]["cookie"] == "cf_clearance=zzz"
        assert curl.calls[0]["ua"] == "UA-153"

    def test_unpassable_wall_is_reported_not_raised(self, monkeypatch):
        monkeypatch.setattr(fetch, "_curl", FakeCurl())
        p = fetch.fetch_page("https://www.marinetraffic.org/v/1")
        assert p.status == "403" and "Just a moment" in p.text and p.notes == []

    def test_extra_headers_reach_curl(self, monkeypatch):
        curl = FakeCurl(plain=("200", b'{"name": "X"}'))
        monkeypatch.setattr(fetch, "_curl", curl)
        fetch.fetch_page("https://api.example.com/units/1", headers={"tx": "abc"})
        assert curl.calls[0]["headers"] == {"tx": "abc"}


class TestEarnClearance:
    def test_no_browser_env_blocks_the_launch(self, monkeypatch):
        monkeypatch.setenv("LNGCT_NO_BROWSER", "1")
        monkeypatch.setattr(fetch, "_earn_clearance", _REAL_EARN)
        launched = []
        monkeypatch.setattr(cf_clearance, "refresh", lambda urls, **k: launched.append(urls))
        assert fetch._earn_clearance("https://www.marinetraffic.org/v/1") == (None, None)
        assert launched == []
        assert "www.marinetraffic.org" in fetch._CLEARANCE_TRIED

    def test_one_launch_per_host_per_process(self, monkeypatch):
        monkeypatch.setattr(fetch, "_earn_clearance", _REAL_EARN)
        monkeypatch.delenv("LNGCT_NO_BROWSER", raising=False)
        launches = []

        def fake_refresh(urls, **k):
            launches.append(urls)
            cf_clearance.save_store({"ua": "UA", "cookies": {
                ".marinetraffic.org": {"value": "new", "expires": 4e9, "saved": 0}}})
        monkeypatch.setattr(cf_clearance, "refresh", fake_refresh)
        assert fetch._earn_clearance("https://www.marinetraffic.org/a") == ("cf_clearance=new", "UA")
        assert fetch._earn_clearance("https://www.marinetraffic.org/b") == (None, None)
        assert len(launches) == 1


class TestCookieStore:
    def test_round_trip_and_suffix_match(self):
        cf_clearance.save_store({"ua": "UA", "cookies": {
            ".marinetraffic.org": {"value": "v1", "expires": 4e9, "saved": 0}}})
        assert cf_clearance.cookie_for("https://www.marinetraffic.org/x") == ("v1", "UA")
        assert cf_clearance.cookie_for("https://marinetraffic.org/") == ("v1", "UA")
        assert cf_clearance.cookie_for("https://notmarinetraffic.org/") is None
        assert cf_clearance.cookie_for("https://www.shipvault.com/") is None

    def test_expired_cookie_is_ignored(self):
        cf_clearance.save_store({"ua": "UA", "cookies": {
            ".marinetraffic.org": {"value": "old", "expires": 1.0, "saved": 0}}})
        assert cf_clearance.cookie_for("https://www.marinetraffic.org/x") is None

    def test_forget_drops_only_that_host(self):
        cf_clearance.save_store({"ua": "UA", "cookies": {
            ".marinetraffic.org": {"value": "a", "expires": 4e9, "saved": 0},
            ".marinevesseltraffic.com": {"value": "b", "expires": 4e9, "saved": 0}}})
        cf_clearance.forget("https://www.marinetraffic.org/x")
        assert cf_clearance.cookie_for("https://www.marinetraffic.org/x") is None
        assert cf_clearance.cookie_for("https://www.marinevesseltraffic.com/x") == ("b", "UA")

    def test_missing_store_is_empty(self):
        assert cf_clearance.load_store() == {"ua": "", "cookies": {}}
        assert cf_clearance.cookie_for("https://www.marinetraffic.org/x") is None

    def test_challenge_titles(self):
        assert cf_clearance._is_challenge_title("Just a moment...")
        assert cf_clearance._is_challenge_title("")
        assert not cf_clearance._is_challenge_title("HULL 2616 - LNG Tanker, IMO 1175527")
