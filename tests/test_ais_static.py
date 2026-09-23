"""Tests for scripts/ais_static.py — the aisstream static-data cross-check.

Offline throughout (tests/README.md: "Tests should never hit the network"):
the canned messages below follow the shape of a real aisstream capture
(2026-09-17 — a SubscriptionConfirmation first, then ShipStaticData with
space-padded text fields and an integer ImoNumber), the websocket is a scripted
fake injected through listen(connect=...), and the clock / sleep are injected
too. No test reads the real key: the keychain lookup is stubbed.
"""
import asyncio
import json
import subprocess
from types import SimpleNamespace

import ais_static
import pytest
from ais_static import (
    AisStreamError,
    Collector,
    backend_watchlist,
    listen,
    load_sightings,
    parse_static,
    ship_type_label,
    subscription,
)
from backend_io import Backend

CONFIRMATION = {"Message": {"CompressionEnabled": True}, "MessageType": "SubscriptionConfirmation"}


def static_msg(imo=9904675, name="PETR STOLYPIN       ", mmsi=273278650, ship_type=84,
               destination="SABETTA             ", callsign="UBXW5  "):
    return {
        "MetaData": {"MMSI": mmsi, "MMSI_String": mmsi, "ShipName": name,
                     "latitude": 71.27, "longitude": 72.06,
                     "time_utc": "2026-09-17 15:29:53.299471859 +0000 UTC"},
        "MessageType": "ShipStaticData",
        "Message": {"ShipStaticData": {
            "AisVersion": 1, "CallSign": callsign, "Destination": destination,
            "Dimension": {"A": 250, "B": 49, "C": 25, "D": 25}, "Dte": False,
            "Eta": {"Day": 11, "Hour": 10, "Minute": 0, "Month": 5}, "FixType": 1,
            "ImoNumber": imo, "MaximumStaticDraught": 11.5, "MessageID": 5, "Name": name,
            "RepeatIndicator": 0, "Spare": False, "Type": ship_type, "UserID": mmsi,
            "Valid": True}},
    }


POSITION = {"MessageType": "PositionReport", "MetaData": {"MMSI": 273278650},
            "Message": {"PositionReport": {"UserID": 273278650, "Latitude": 1.0, "Longitude": 2.0}}}


class TestParseStatic:
    def test_wanted_imo_yields_a_clean_record(self):
        assert parse_static(static_msg(), {"9904675"}) == {
            "imo": "9904675", "name": "PETR STOLYPIN", "mmsi": 273278650,
            "ship_type": 84, "ship_type_label": "tanker", "destination": "SABETTA",
            "callsign": "UBXW5", "lat": 71.27, "lon": 72.06, "ts": "2026-09-17T15:29:53Z"}

    def test_unwanted_imo_is_dropped(self):
        assert parse_static(static_msg(imo=9509346), {"9904675"}) is None

    def test_pre_delivery_1xxxxxx_imo_matches(self):
        rec = parse_static(static_msg(imo=1048982, name="HN 8366"), {"1048982"})
        assert rec["imo"] == "1048982" and rec["name"] == "HN 8366"

    @pytest.mark.parametrize("imo", [0, None, "9904675", -1])
    def test_zero_missing_or_non_integer_imo_never_matches(self, imo):
        # a newbuild on trials often transmits IMO 0 — it must not match anything
        assert parse_static(static_msg(imo=imo), {"0", "9904675", "None", "-1"}) is None

    @pytest.mark.parametrize("msg", [CONFIRMATION, POSITION, {}, [], None, "x",
                                     {"MessageType": "ShipStaticData"},
                                     {"MessageType": "ShipStaticData", "Message": None}])
    def test_other_messages_are_ignored(self, msg):
        assert parse_static(msg, {"9904675"}) is None

    def test_at_sign_padding_and_inner_whitespace_are_cleaned(self):
        rec = parse_static(static_msg(name="LNG  ADVENTURE@@@@@@", destination="@@@@@@@@"), {"9904675"})
        assert rec["name"] == "LNG ADVENTURE" and rec["destination"] == ""

    def test_name_falls_back_to_metadata(self):
        msg = static_msg()
        msg["Message"]["ShipStaticData"]["Name"] = ""
        assert parse_static(msg, {"9904675"})["name"] == "PETR STOLYPIN"

    @pytest.mark.parametrize("code,label", [(84, "tanker"), (80, "tanker"), (70, "cargo"),
                                            (52, "tug"), (37, "pleasure craft"), (99, "other"),
                                            (0, ""), (None, ""), (15, "")])
    def test_ship_type_labels(self, code, label):
        assert ship_type_label(code) == label

    def test_subscription_is_worldwide_static_only(self):
        sub = subscription("k")
        assert sub == {"APIKey": "k", "BoundingBoxes": [[[-90, -180], [90, 180]]],
                       "FilterMessageTypes": ["ShipStaticData"]}


class TestCollector:
    def _collector(self, tmp_path, wanted=("9904675", "1048982")):
        return Collector(wanted, tmp_path / "ais_static.jsonl", echo=lambda *_: None)

    def _lines(self, tmp_path):
        p = tmp_path / "ais_static.jsonl"
        return [json.loads(ln) for ln in p.read_text().splitlines()] if p.exists() else []

    def test_only_watched_imos_are_written(self, tmp_path):
        c = self._collector(tmp_path)
        for m in (CONFIRMATION, static_msg(imo=9509346), POSITION, static_msg()):
            c.handle(json.dumps(m))
        assert [r["imo"] for r in self._lines(tmp_path)] == ["9904675"]
        assert c.messages == 4 and list(c.seen) == ["9904675"]

    def test_accepts_bytes_like_the_live_feed(self, tmp_path):
        c = self._collector(tmp_path)
        assert c.handle(json.dumps(static_msg()).encode())["imo"] == "9904675"

    def test_repeat_of_the_same_static_data_is_written_once(self, tmp_path):
        c = self._collector(tmp_path)
        for _ in range(3):
            c.handle(json.dumps(static_msg()))
        assert len(self._lines(tmp_path)) == 1

    def test_a_rename_is_written_again(self, tmp_path):
        c = self._collector(tmp_path)
        c.handle(json.dumps(static_msg(imo=1048982, name="HN 8366")))
        c.handle(json.dumps(static_msg(imo=1048982, name="LNG ADVENTURE")))
        assert [r["name"] for r in self._lines(tmp_path)] == ["HN 8366", "LNG ADVENTURE"]
        assert load_sightings(tmp_path / "ais_static.jsonl")["1048982"]["name"] == "LNG ADVENTURE"

    def test_complete_once_every_watched_imo_is_seen(self, tmp_path):
        c = self._collector(tmp_path)
        c.handle(json.dumps(static_msg()))
        assert not c.complete()
        c.handle(json.dumps(static_msg(imo=1048982)))
        assert c.complete()

    def test_error_message_raises(self, tmp_path):
        with pytest.raises(AisStreamError, match="Api Key Is Not Valid"):
            self._collector(tmp_path).handle(json.dumps({"error": "Api Key Is Not Valid"}))

    def test_junk_frames_are_ignored(self, tmp_path):
        c = self._collector(tmp_path)
        assert c.handle("not json") is None and c.handle(None) is None
        assert self._lines(tmp_path) == []

    def test_load_sightings_tolerates_junk_and_absence(self, tmp_path):
        p = tmp_path / "x.jsonl"
        p.write_text('{"imo": "1", "name": "A"}\nnope\n{"name": "no imo"}\n')
        assert list(load_sightings(p)) == ["1"]
        assert load_sightings(tmp_path / "absent.jsonl") == {}


class FakeSocket:
    """Scripted websocket: yields `frames`, then raises (a dropped connection)
    or idles until the deadline (`then="idle"`)."""

    def __init__(self, frames, clock, then="drop"):
        self.frames, self.clock, self.then = list(frames), clock, then
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send(self, data):
        self.sent.append(json.loads(data))

    async def recv(self):
        if self.frames:
            self.clock.t += 1
            return self.frames.pop(0)
        if self.then == "idle":
            self.clock.t += 60
            raise TimeoutError
        raise ConnectionError("socket dropped")


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class TestListen:
    def _run(self, tmp_path, sockets, seconds=600, wanted=("9904675", "1048982")):
        clock = Clock()
        made, sleeps = [], []
        queue = list(sockets)

        def connect(url):
            assert url == ais_static.STREAM_URL
            if not queue:
                raise ConnectionError("refused")
            frames, then = queue.pop(0)
            made.append(FakeSocket([json.dumps(f) for f in frames], clock, then))
            return made[-1]

        async def sleep(s):
            sleeps.append(s)
            clock.t += s

        c = Collector(wanted, tmp_path / "out.jsonl", echo=lambda *_: None)
        asyncio.run(listen("SECRET", c, seconds, connect=connect, clock=clock, sleep=sleep,
                           echo=lambda *_: None))
        return c, made, sleeps, clock

    def test_subscribes_then_collects_until_the_deadline(self, tmp_path):
        c, made, _, clock = self._run(tmp_path, [([CONFIRMATION, static_msg()], "idle")])
        assert made[0].sent == [subscription("SECRET")]
        assert list(c.seen) == ["9904675"]
        assert clock.t >= 600

    def test_stops_early_once_every_watched_imo_is_seen(self, tmp_path):
        frames = [static_msg(), static_msg(imo=1048982), static_msg(imo=9509346)]
        c, _, _, clock = self._run(tmp_path, [(frames, "idle")])
        assert c.complete() and clock.t < 600 and c.messages == 2

    def test_reconnects_after_a_dropped_socket(self, tmp_path):
        c, made, sleeps, _ = self._run(tmp_path, [([static_msg()], "drop"),
                                                  ([static_msg(imo=1048982)], "idle")])
        assert len(made) == 2 and sleeps == [5] and c.complete()

    def test_gives_up_after_repeated_connection_failures(self, tmp_path):
        c, made, sleeps, _ = self._run(tmp_path, [], seconds=10_000)
        assert made == [] and len(sleeps) == ais_static.MAX_RECONNECTS - 1 and c.seen == {}

    def test_a_refused_subscription_is_not_retried(self, tmp_path):
        with pytest.raises(AisStreamError):
            self._run(tmp_path, [([{"error": "Api Key Is Not Valid"}], "idle"),
                                 ([static_msg()], "idle")])


class TestWatchlistAndKey:
    def _backend(self):
        colmap = {"_header_row_idx": 1, "_data_starts_at": 2, "row_id": 0, "imo": 1,
                  "name": 2, "status": 3}
        rows = [["preamble"], ["id", "IMO", "Name", "Status"],
                ["1", "9904675", "Petr Stolypin", "active"],
                ["2", "1048982", "Hyundai Samho HI 8366", "On order "],
                ["3", "", "Samsung HI 2601", "on order"],
                ["4", "tbd", "Hudong Zhonghua", "on order"],
                ["5", "1176351", "Proposed One", "proposed"]]
        return Backend(path=None, rows=rows, colmap=colmap)

    def test_on_order_rows_with_an_imo_by_default_with_live_sheet_rows(self):
        assert backend_watchlist(self._backend()) == {
            "1048982": {"name": "Hyundai Samho HI 8366", "sheet_row": 4}}

    def test_statuses_are_selectable(self):
        assert set(backend_watchlist(self._backend(), ["on order", "Proposed"])) == {"1048982", "1176351"}

    def test_read_imos_from_a_file_or_a_list(self, tmp_path):
        f = tmp_path / "imos.txt"
        f.write_text("# priority first\n9904675  # stolypin\n\n1048982\n")
        assert ais_static._read_imos(str(f)) == ["9904675", "1048982"]
        assert ais_static._read_imos("9904675, 1048982,junk") == ["9904675", "1048982"]

    def test_env_key_wins_and_the_keychain_is_not_consulted(self, monkeypatch):
        monkeypatch.setenv(ais_static.KEY_ENV, " from-env ")
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("keychain consulted"))
        assert ais_static.api_key() == "from-env"

    def test_keychain_fallback_and_no_key(self, monkeypatch):
        monkeypatch.delenv(ais_static.KEY_ENV, raising=False)
        calls = []

        def run(cmd, **kw):
            calls.append(cmd)
            return SimpleNamespace(stdout="from-keychain\n")
        monkeypatch.setattr(subprocess, "run", run)
        assert ais_static.api_key() == "from-keychain"
        assert calls[0][:2] == ["security", "find-generic-password"]
        assert ais_static.KEYCHAIN_SERVICE in calls[0]

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=""))
        assert ais_static.api_key() is None

    def test_main_exits_without_a_key_and_never_prompts(self, monkeypatch):
        monkeypatch.setattr(ais_static, "api_key", lambda: None)
        monkeypatch.setattr(ais_static.sys, "argv", ["ais_static.py", "--imos", "9904675"])
        with pytest.raises(SystemExit) as exc:
            ais_static.main()
        assert "No aisstream.io API key" in str(exc.value.code)
