"""
AIS static-data cross-check — "has this on-order vessel been delivered and named?"

A second, non-scraped source for the on-order rows, replacing the vesselfinder
per-IMO sweep that got this machine IP-banned on 2026-09-17 (see sweep.py).
It listens to aisstream.io's websocket feed for ShipStaticData (AIS message 5:
IMO, name, MMSI, ship type, destination) and keeps the messages whose IMO is on
the watch list.

**Cross-check only — never a citable [ref].** AIS static data is typed in by
the crew, carries no URL, and proves nothing the §3.8 gate could verify. Cited
refs stay shipvault, marinetraffic, class-society registers, or press, all
through the gate as usual. What a sighting buys is a lead: the IMO is
transmitting under this name, so go find the citable source.

**"Not seen" is not evidence of anything.** A static message repeats only every
~6 minutes and only while the vessel is transmitting within range of one of
aisstream's terrestrial receivers — a ship still at the outfitting quay with its
transponder off, or mid-ocean, never appears. A name can also be a yard label
("HN 8366", "SHI 2601") or a sea-trials placeholder, and a newbuild on trials
may transmit IMO 0.

aisstream filters server-side by MMSI and bounding box only, and an on-order
hull has no MMSI we know of, so the subscription is world-wide ShipStaticData
(~15 messages/s) and the IMO filter runs here.

Key: $AISSTREAM_API_KEY (the name ../lng-carriers-map uses), else the macOS
keychain item `aisstream-api-key` — same pattern as wayback_save.py. With no
key the script exits; it never asks for one. The key travels only inside the
websocket subscription message, never on a command line or in output.

Output: work/ais_static.jsonl (gitignored), appended — one record on an IMO's
first sighting per run and again whenever its name / MMSI / destination changes:
imo, name, mmsi, ship_type, ship_type_label, destination, callsign, lat, lon, ts.
The latest record per IMO wins (load_sightings()).

Usage:
    python scripts/ais_static.py                       # on-order IMOs from work/backend.csv, 20 min
    python scripts/ais_static.py --minutes 60
    python scripts/ais_static.py --imos 9904675,1048982
    python scripts/ais_static.py --imos work/imos.txt --statuses "on order,proposed"
"""
import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from backend_io import BackendNotPulled, load_backend
from paths import work_dir

STREAM_URL = "wss://stream.aisstream.io/v0/stream"
KEY_ENV = "AISSTREAM_API_KEY"
KEYCHAIN_SERVICE = "aisstream-api-key"
DEFAULT_MINUTES = 20        # a static message repeats every ~6 min: three chances
DEFAULT_STATUSES = ("on order",)
MAX_RECONNECTS = 5          # consecutive failed connections before giving up
RECV_TIMEOUT = 60           # seconds of silence before re-checking the deadline

# AIS ship-type code -> label, by first digit (ITU-R M.1371). LNG carriers
# transmit 80-89; anything else on a watched IMO is worth a second look.
_TYPE_DECADES = {2: "wing in ground", 4: "high-speed craft", 6: "passenger",
                 7: "cargo", 8: "tanker", 9: "other"}
_TYPE_30S = {30: "fishing", 31: "towing", 32: "towing", 33: "dredging", 34: "diving",
             35: "military", 36: "sailing", 37: "pleasure craft"}
_TYPE_50S = {50: "pilot", 51: "search and rescue", 52: "tug", 53: "port tender",
             54: "anti-pollution", 55: "law enforcement", 58: "medical", 59: "noncombatant"}


class AisStreamError(RuntimeError):
    """aisstream answered with an error message (bad key, malformed subscription)."""


def api_key() -> str | None:
    """The aisstream key from env or the macOS keychain, or None."""
    v = os.environ.get(KEY_ENV, "").strip()
    if v:
        return v
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-a", os.environ.get("USER", ""),
             "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def ship_type_label(code) -> str:
    if not isinstance(code, int) or code <= 0:
        return ""
    return _TYPE_30S.get(code) or _TYPE_50S.get(code) or _TYPE_DECADES.get(code // 10, "")


def _clean(s) -> str:
    """AIS text fields are space- / @-padded to a fixed width."""
    return re.sub(r"\s+", " ", str(s or "").replace("@", " ")).strip()


def _iso(time_utc: str) -> str:
    """aisstream's '2026-09-17 15:29:53.299471859 +0000 UTC' -> '2026-09-17T15:29:53Z'."""
    m = re.match(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})", time_utc or "")
    return f"{m.group(1)}T{m.group(2)}Z" if m else ""


def parse_static(msg: dict, wanted: set) -> dict | None:
    """The sighting record for a ShipStaticData message whose IMO is in
    `wanted` (a set of IMO strings); None for every other message."""
    if not isinstance(msg, dict) or msg.get("MessageType") != "ShipStaticData":
        return None
    body = (msg.get("Message") or {}).get("ShipStaticData") or {}
    imo = body.get("ImoNumber")
    if not isinstance(imo, int) or imo <= 0 or str(imo) not in wanted:
        return None
    meta = msg.get("MetaData") or {}
    code = body.get("Type")
    return {
        "imo": str(imo),
        "name": _clean(body.get("Name") or meta.get("ShipName")),
        "mmsi": body.get("UserID") or meta.get("MMSI"),
        "ship_type": code,
        "ship_type_label": ship_type_label(code),
        "destination": _clean(body.get("Destination")),
        "callsign": _clean(body.get("CallSign")),
        "lat": meta.get("latitude"),
        "lon": meta.get("longitude"),
        "ts": _iso(meta.get("time_utc", "")),
    }


def subscription(key: str) -> dict:
    return {"APIKey": key,
            "BoundingBoxes": [[[-90, -180], [90, 180]]],
            "FilterMessageTypes": ["ShipStaticData"]}


class Collector:
    """Filters raw feed messages to the watch list and appends sightings to the
    JSONL — on first sighting, and again when name / MMSI / destination change."""

    _IDENTITY = ("name", "mmsi", "destination")

    def __init__(self, wanted, out_path, echo=print):
        self.wanted = {str(i) for i in wanted}
        self.out_path = Path(out_path)
        self.echo = echo
        self.seen: dict[str, dict] = {}
        self.messages = 0

    def complete(self) -> bool:
        return bool(self.wanted) and len(self.seen) == len(self.wanted)

    def handle(self, raw) -> dict | None:
        try:
            msg = json.loads(raw)
        except (ValueError, TypeError):
            return None
        if isinstance(msg, dict) and msg.get("error"):
            raise AisStreamError(str(msg["error"]))
        self.messages += 1
        rec = parse_static(msg, self.wanted)
        if rec is None:
            return None
        prev = self.seen.get(rec["imo"])
        self.seen[rec["imo"]] = rec
        if prev and all(prev[k] == rec[k] for k in self._IDENTITY):
            return None
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.out_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.echo(f"seen IMO {rec['imo']}: {rec['name'] or '(no name)'} — MMSI {rec['mmsi']}, "
                  f"{rec['ship_type_label'] or 'type ' + str(rec['ship_type'])}, "
                  f"dest {rec['destination'] or '-'}")
        return rec


async def listen(key: str, collector: Collector, seconds: float, *, connect=None,
                 clock=None, sleep=None, echo=print) -> None:
    """Feed `collector` from the stream for `seconds`, or until every watched
    IMO has been seen. Reconnects when the socket drops; gives up after
    MAX_RECONNECTS consecutive failures. `connect` / `clock` / `sleep` are
    injectable for tests."""
    if connect is None:
        import websockets       # lazy: parsing and tests don't need the package
        connect = websockets.connect
    clock = clock or time.monotonic
    sleep = sleep or asyncio.sleep
    deadline = clock() + seconds
    failures = 0
    while clock() < deadline and not collector.complete():
        try:
            async with connect(STREAM_URL) as ws:
                await ws.send(json.dumps(subscription(key)))
                while (remaining := deadline - clock()) > 0 and not collector.complete():
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, RECV_TIMEOUT))
                    except asyncio.TimeoutError:
                        continue
                    failures = 0
                    collector.handle(raw)
        except AisStreamError:
            raise
        except Exception as e:  # noqa: BLE001 — a dropped socket is routine on a long listen
            failures += 1
            if failures >= MAX_RECONNECTS:
                echo(f"giving up after {failures} failed connections: {e!r}")
                return
            echo(f"connection lost ({e!r}); reconnecting ({failures}/{MAX_RECONNECTS})")
            await sleep(5 * failures)


def backend_watchlist(backend, statuses=DEFAULT_STATUSES) -> dict:
    """IMO -> {name, sheet_row} for backend rows in `statuses` that carry an IMO.
    sheet_row is the LIVE tab row (report-live-rows rule), not the column-A id."""
    cm = backend.colmap
    statuses = {s.strip().lower() for s in statuses}
    out = {}
    for idx in range(backend.data_start, len(backend.rows)):
        row = backend.rows[idx]
        imo = backend.cell(row, cm.get("imo"))
        if imo.isdigit() and backend.cell(row, cm.get("status")).lower() in statuses:
            out.setdefault(imo, {"name": backend.cell(row, cm.get("name")), "sheet_row": idx + 1})
    return out


def load_sightings(path) -> dict:
    """Latest sighting per IMO from an ais_static JSONL ({} if absent)."""
    out = {}
    p = Path(path)
    if not p.exists():
        return out
    with open(p, encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
                out[str(rec["imo"])] = rec
            except (ValueError, KeyError, TypeError):
                continue
    return out


def _read_imos(arg: str) -> list[str]:
    """A file (one IMO per line, # comments ok) or a comma/space-separated list."""
    p = Path(arg)
    text = p.read_text(encoding="utf-8") if p.is_file() else arg
    lines = [ln.split("#", 1)[0] for ln in text.splitlines()]
    return [x for x in re.split(r"[,\s]+", " ".join(lines)) if x.isdigit()]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--imos", default="", help="file of IMOs or a comma-separated list "
                                               "(default: backend rows in --statuses)")
    ap.add_argument("--statuses", default=",".join(DEFAULT_STATUSES),
                    help='backend Status values to watch (default "on order")')
    ap.add_argument("--minutes", type=float, default=DEFAULT_MINUTES,
                    help=f"how long to listen (default {DEFAULT_MINUTES}; static messages "
                         f"repeat every ~6 min, only for vessels transmitting in range)")
    ap.add_argument("--out", default=str(work_dir() / "ais_static.jsonl"))
    args = ap.parse_args()

    key = api_key()
    if not key:
        sys.exit(f"No aisstream.io API key. Set {KEY_ENV}, or store it with\n"
                 f"  security add-generic-password -a \"$USER\" -s {KEYCHAIN_SERVICE} -w '<key>'")

    try:
        watch = backend_watchlist(load_backend(), args.statuses.split(","))
    except BackendNotPulled as e:
        if not args.imos:
            sys.exit(str(e))
        watch = {}
    if args.imos:
        imos = _read_imos(args.imos)
        watch = {i: watch.get(i, {"name": "", "sheet_row": ""}) for i in imos}
    if not watch:
        sys.exit("no IMOs to watch")

    print(f"watching {len(watch)} IMO(s) for {args.minutes:g} min -> {args.out}")
    collector = Collector(watch, args.out)
    try:
        asyncio.run(listen(key, collector, args.minutes * 60))
    except AisStreamError as e:
        sys.exit(f"aisstream refused the subscription: {e}")
    except KeyboardInterrupt:
        print("interrupted")

    print(f"\n{collector.messages} static message(s) heard; "
          f"{len(collector.seen)} of {len(watch)} watched IMO(s) seen")
    if collector.seen:
        print("live row | IMO | backend name | AIS name | type | destination")
        for imo, rec in sorted(collector.seen.items(), key=lambda kv: str(watch[kv[0]]["sheet_row"]).zfill(6)):
            w = watch[imo]
            print(f"{w['sheet_row'] or '-'} | {imo} | {w['name'] or '-'} | {rec['name'] or '-'} | "
                  f"{rec['ship_type_label'] or rec['ship_type']} | {rec['destination'] or '-'}")
    print("Not seen is not evidence of anything. A sighting is a lead, never a [ref] — "
          "cite shipvault / marinetraffic / class / press through the §3.8 gate.")


if __name__ == "__main__":
    main()
