"""Tests for scripts/sweep.py — the polite bulk-fetch helper.

The helper exists to keep a bulk sweep from earning an IP ban (the 2026-09-17
vesselfinder incident), so what's pinned here is the protective behaviour:
per-host pacing, the circuit breaker (consecutive timeouts / 429 / 403, and the
consecutive-404-after-200s soft-block pattern), skipped URLs being recorded,
the --max cap, and resume. Nothing touches the network or sleeps for real: the
fetch layer is a scripted fake, and the sleep / clock / jitter are injected
(tests/README.md: "Tests should never hit the network"). The autouse fixture
also stubs sweep.fetch_page so a Sweeper built without the fake fails loudly.
"""
import json

import pytest
import sweep
from fetch import Page
from sweep import Sweeper, host_delay, host_key, load_records, meta_description

VF = "https://www.vesselfinder.com/vessels/details/{}"
EX = "https://example.com/p/{}"


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    def _no_network(url, **kw):
        raise AssertionError(f"test tried to fetch the network: {url}")
    monkeypatch.setattr(sweep, "fetch_page", _no_network)


def _html(title="T", desc="D"):
    return (f'<html><head><title>{title}</title>'
            f'<meta name="description" content="{desc}"></head><body></body></html>')


class Harness:
    """Scripted fetch + fake clock. `script` maps url -> status (default "200"),
    or is a callable(url) -> status. Sleeping advances the clock; so does each
    fetch (by `fetch_secs`), like a real request would."""

    def __init__(self, tmp_path, script=None, fetch_secs=0.5, **kw):
        self.script = script or {}
        self.fetch_secs = fetch_secs
        self.t = 1000.0
        self.sleeps = []
        self.fetched = []
        self.out = tmp_path / "sweep.jsonl"
        self.kw = kw

    def _fetch(self, url, **kw):
        self.fetched.append(url)
        self.t += self.fetch_secs
        status = self.script(url) if callable(self.script) else self.script.get(url, "200")
        if isinstance(status, Exception):
            raise status
        return Page(status=status, text=_html(f"page {url[-3:]}") if status == "200" else "",
                    notes=["cf_impersonate"] if status == "200" else [])

    def _sleep(self, secs):
        self.sleeps.append(secs)
        self.t += secs

    def sweeper(self, **kw):
        opts = dict(fetch=self._fetch, sleep=self._sleep, clock=lambda: self.t,
                    rng=lambda a, b: 0.0, now=lambda: "2026-09-17T00:00:00Z",
                    echo=lambda *_: None)
        opts.update(self.kw)
        opts.update(kw)
        return Sweeper(self.out, **opts)

    def records(self):
        return [json.loads(ln) for ln in self.out.read_text().splitlines()]


class TestHostKeyAndDelays:
    def test_host_key_strips_www_and_lowercases(self):
        assert host_key("https://WWW.VesselFinder.com/vessels/details/1") == "vesselfinder.com"
        assert host_key("https://example.com/x") == "example.com"

    def test_default_delay(self):
        assert host_delay("example.com") == (sweep.DEFAULT_DELAY, sweep.DEFAULT_JITTER)
        assert (sweep.DEFAULT_DELAY, sweep.DEFAULT_JITTER) == (6.0, 2.0)

    @pytest.mark.parametrize("host", ["vesselfinder.com", "marinetraffic.com",
                                      "marinetraffic.org", "api.vesselfinder.com"])
    def test_tracker_hosts_are_slower(self, host):
        assert host_delay(host) == (10.0, 3.0)

    def test_cli_delay_cannot_lower_a_tracker_floor(self):
        assert host_delay("vesselfinder.com", delay=1.0)[0] == 10.0
        assert host_delay("vesselfinder.com", delay=30.0)[0] == 30.0
        assert host_delay("example.com", delay=1.0)[0] == 1.0

    def test_meta_description(self):
        assert meta_description(_html(desc="Vessel X &amp; Y")) == "Vessel X & Y"
        assert meta_description("<html></html>") == ""


class TestPacing:
    def test_gap_is_applied_between_requests_to_one_host(self, tmp_path):
        h = Harness(tmp_path)
        h.sweeper().run([EX.format(i) for i in range(3)])
        # no wait before the first request; a full 6 s after each of the others
        assert h.sleeps == [6.0, 6.0]

    def test_tracker_host_gets_its_slower_gap(self, tmp_path):
        h = Harness(tmp_path)
        h.sweeper().run([VF.format(i) for i in range(2)])
        assert h.sleeps == [10.0]

    def test_pacing_is_per_host(self, tmp_path):
        h = Harness(tmp_path, fetch_secs=0.0)
        h.sweeper().run([EX.format(1), VF.format(1), EX.format(2), VF.format(2)])
        # first hit on each host is free; example.com then waits its 6 s, and by
        # the time vesselfinder's turn comes 6 s of its 10 s gap has elapsed
        assert h.sleeps == [6.0, 4.0]

    def test_jitter_is_added_to_the_gap(self, tmp_path):
        h = Harness(tmp_path, fetch_secs=0.0)
        seen = []

        def rng(a, b):
            seen.append((a, b))
            return b
        h.sweeper(rng=rng).run([EX.format(i) for i in range(2)])
        assert seen == [(-2.0, 2.0)]
        assert h.sleeps == [8.0]

    def test_time_already_spent_counts_toward_the_gap(self, tmp_path):
        h = Harness(tmp_path, fetch_secs=0.0)
        s = h.sweeper()
        s.run([EX.format(1)])
        h.t += 100                       # long pause between runs of one Sweeper
        s.run([EX.format(2)])
        assert h.sleeps == []


class TestBreaker:
    def test_trips_on_consecutive_timeouts_and_stops_the_host(self, tmp_path):
        urls = [VF.format(i) for i in range(10)]
        h = Harness(tmp_path, script=lambda u: "000")
        stats = h.sweeper().run(urls)
        assert h.fetched == urls[:3]                      # default threshold: 3
        assert "3 consecutive failure" in stats["vesselfinder.com"]["tripped"]
        assert stats["vesselfinder.com"]["skipped"] == 7

    @pytest.mark.parametrize("status", ["429", "403"])
    def test_429_and_403_count_as_failures(self, tmp_path, status):
        h = Harness(tmp_path, script=lambda u: status)
        stats = h.sweeper().run([EX.format(i) for i in range(5)])
        assert len(h.fetched) == 3
        assert f"HTTP {status}" in stats["example.com"]["tripped"]

    def test_a_fetch_exception_counts_as_a_timeout(self, tmp_path):
        h = Harness(tmp_path, script=lambda u: RuntimeError("curl exploded"))
        stats = h.sweeper().run([EX.format(i) for i in range(5)])
        assert len(h.fetched) == 3
        assert stats["example.com"]["tripped"]
        assert h.records()[0]["status"] == "000"
        assert "curl exploded" in h.records()[0]["notes"][0]

    def test_a_success_resets_the_failure_count(self, tmp_path):
        seq = iter(["000", "000", "200", "000", "000", "200"])
        h = Harness(tmp_path, script=lambda u: next(seq))
        stats = h.sweeper().run([EX.format(i) for i in range(6)])
        assert len(h.fetched) == 6
        assert stats["example.com"]["tripped"] == ""

    def test_breaker_is_per_host(self, tmp_path):
        urls = [VF.format(1), VF.format(2), VF.format(3), VF.format(4), EX.format(1)]
        h = Harness(tmp_path, script=lambda u: "000" if "vesselfinder" in u else "200")
        stats = h.sweeper().run(urls)
        assert EX.format(1) in h.fetched and VF.format(4) not in h.fetched
        assert stats["example.com"]["tripped"] == ""

    def test_consecutive_404s_after_200s_trip_it(self, tmp_path):
        urls = [VF.format(i) for i in range(20)]
        h = Harness(tmp_path, script=lambda u: "200" if u in urls[:2] else "404")
        stats = h.sweeper().run(urls)
        assert len(h.fetched) == 2 + 8                    # default threshold: 8
        assert "consecutive 404s" in stats["vesselfinder.com"]["tripped"]
        assert "soft block" in stats["vesselfinder.com"]["tripped"]

    def test_404s_on_a_host_that_never_answered_200_do_not_trip(self, tmp_path):
        h = Harness(tmp_path, script=lambda u: "404")
        stats = h.sweeper().run([EX.format(i) for i in range(12)])
        assert len(h.fetched) == 12
        assert stats["example.com"]["tripped"] == ""

    def test_scattered_404s_do_not_trip(self, tmp_path):
        h = Harness(tmp_path, script=lambda u: "404" if int(u.rsplit("/", 1)[1]) % 2 else "200")
        stats = h.sweeper().run([EX.format(i) for i in range(30)])
        assert len(h.fetched) == 30
        assert stats["example.com"]["tripped"] == ""

    def test_thresholds_are_configurable(self, tmp_path):
        h = Harness(tmp_path, script=lambda u: "000")
        h.sweeper(max_fails=1).run([EX.format(i) for i in range(4)])
        assert len(h.fetched) == 1


class TestRecords:
    def test_fetched_record_shape(self, tmp_path):
        h = Harness(tmp_path)
        h.sweeper().run([(VF.format(9904675), {"imo": "9904675"})])
        assert h.records() == [{
            "url": VF.format(9904675), "host": "vesselfinder.com", "imo": "9904675",
            "status": "200", "title": "page 675", "description": "D",
            "notes": ["cf_impersonate"], "ts": "2026-09-17T00:00:00Z"}]

    def test_skipped_urls_are_recorded_with_the_reason(self, tmp_path):
        urls = [(VF.format(i), {"imo": str(i)}) for i in range(5)]
        h = Harness(tmp_path, script=lambda u: "000")
        h.sweeper().run(urls)
        recs = h.records()
        assert [r.get("status") for r in recs[:3]] == ["000"] * 3
        assert all(r["skipped"] is True and r["reason"].startswith("breaker:")
                   and "status" not in r for r in recs[3:])
        assert [r["imo"] for r in recs[3:]] == ["3", "4"]
        assert [r["url"] for r in recs] == [u for u, _ in urls]   # order preserved

    def test_extract_adds_caller_fields(self, tmp_path):
        h = Harness(tmp_path)
        h.sweeper(extract=lambda page: {"n": len(page.text)}).run([EX.format(1)])
        assert h.records()[0]["n"] > 0


class TestMaxPerHost:
    def test_cap_limits_requests_per_host_and_records_nothing_for_the_rest(self, tmp_path):
        urls = [VF.format(i) for i in range(5)] + [EX.format(i) for i in range(2)]
        h = Harness(tmp_path)
        stats = h.sweeper(max_per_host=2).run(urls)
        assert h.fetched == [VF.format(0), VF.format(1), EX.format(0), EX.format(1)]
        assert stats["vesselfinder.com"]["deferred"] == 3
        assert len(h.records()) == 4


class TestResume:
    def test_completed_urls_are_not_refetched(self, tmp_path):
        urls = [EX.format(i) for i in range(4)]
        h = Harness(tmp_path)
        h.sweeper(max_per_host=2).run(urls)
        h.fetched.clear()
        h.sweeper().run(urls)
        assert h.fetched == urls[2:]
        assert sorted(load_records(h.out)) == sorted(urls)

    def test_skipped_urls_are_retried_and_the_latest_record_wins(self, tmp_path):
        urls = [EX.format(i) for i in range(5)]
        h = Harness(tmp_path, script=lambda u: "000")
        h.sweeper().run(urls)
        h.fetched.clear()
        h.script = {}                                    # the host is back
        h.sweeper().run(urls)
        # the three recorded 000s are done; only the two skipped URLs go again
        assert h.fetched == urls[3:]
        latest = load_records(h.out)
        assert latest[urls[4]]["status"] == "200" and "skipped" not in latest[urls[4]]

    def test_a_host_that_tripped_last_run_retrips_on_its_first_failure(self, tmp_path):
        urls = [VF.format(i) for i in range(8)]
        h = Harness(tmp_path, script=lambda u: "000")
        h.sweeper().run(urls)                            # 3 requests, 5 skipped
        h.fetched.clear()
        stats = h.sweeper().run(urls)                    # still banned: one probe only
        assert h.fetched == [urls[3]]
        assert "earlier run" in stats["vesselfinder.com"]["tripped"]

    def test_duplicate_input_urls_are_fetched_once(self, tmp_path):
        h = Harness(tmp_path)
        h.sweeper().run([EX.format(1), EX.format(1)])
        assert h.fetched == [EX.format(1)]

    def test_load_records_tolerates_junk_lines(self, tmp_path):
        p = tmp_path / "x.jsonl"
        p.write_text('{"url": "a", "status": "200"}\nnot json\n{"no_url": 1}\n')
        assert list(load_records(p)) == ["a"]
        assert load_records(tmp_path / "absent.jsonl") == {}


class TestCli:
    def test_read_list_takes_a_file_or_a_comma_list(self, tmp_path):
        f = tmp_path / "imos.txt"
        f.write_text("# priority first\n9904675\n\n1048982\n")
        assert sweep._read_list(str(f)) == ["9904675", "1048982"]
        assert sweep._read_list("9904675, 1048982") == ["9904675", "1048982"]

    def test_relative_out_lands_under_work(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LNGCT_WORK_DIR", str(tmp_path))
        assert sweep._out_path("vf.jsonl") == tmp_path.resolve() / "vf.jsonl"
        assert sweep._out_path("/abs/vf.jsonl").as_posix() == "/abs/vf.jsonl"

    def test_template_run_end_to_end(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LNGCT_WORK_DIR", str(tmp_path))
        monkeypatch.setattr(sweep, "fetch_page",
                            lambda url, **kw: Page(status="200", text=_html("LNG Tanker")))
        monkeypatch.setattr(sweep.time, "sleep", lambda s: None)
        monkeypatch.setattr(sweep.sys, "argv",
                            ["sweep.py", "--template", VF.format("{imo}"),
                             "--imos", "9904675,1048982", "--out", "t.jsonl"])
        with pytest.raises(SystemExit) as exc:
            sweep.main()
        assert exc.value.code == 0
        recs = load_records(tmp_path / "t.jsonl")
        assert [r["imo"] for r in recs.values()] == ["9904675", "1048982"]
