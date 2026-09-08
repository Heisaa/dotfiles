"""Things that live on the earth map besides the sun: where the machine's open
TCP connections go, and the last day of earthquakes. Network fetches run in
daemon threads so the draw loop never blocks; results are plain attributes."""

import ipaddress
import json
import os
import threading
import time
import urllib.request

import collectors as C

CACHE_DIR = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "sway-wallpaper")
USGS = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{feed}.geojson"
IP_API = "http://ip-api.com/batch?fields=status,query,country,countryCode,city,lat,lon"


def _fetch(url, data=None, timeout=15):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "sway-wallpaper/1.0"})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


class Quakes:
    """USGS feed: list of (lat, lon, mag, epoch_seconds, place), strongest first."""

    def __init__(self, feed="2.5_day", every=900):
        self.feed, self.every = feed, every
        self.rows, self.at, self.ok = [], 0.0, None
        self._busy = False

    def poll(self):
        if self._busy or time.monotonic() - self.at < self.every:
            return
        self._busy = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            gj = _fetch(USGS.format(feed=self.feed))
            rows = []
            for f in gj.get("features", []):
                lon, lat = f["geometry"]["coordinates"][:2]
                pr = f["properties"]
                if pr.get("mag") is None:
                    continue
                rows.append((lat, lon, float(pr["mag"]), pr["time"] / 1000.0, pr.get("place") or ""))
            rows.sort(key=lambda r: -r[2])
            self.rows, self.ok = rows, True
        except Exception:  # noqa: BLE001 - offline is normal
            self.ok = False
        finally:
            self.at = time.monotonic()
            self._busy = False


class Sockets:
    """Established TCP peers with a location: list of (ip, lat, lon, city, cc, n).
    Locations come from a local MaxMind-format db if configured (needs the
    `maxminddb` module), else from ip-api.com in batches, cached on disk."""

    def __init__(self, db_path="", online=True, every=10):
        self.every, self.online = every, online
        self.rows, self.total, self.at = [], 0, 0.0
        self._cache = {}
        self._pending, self._busy, self._last_query = set(), False, 0.0
        self._reader = None
        if db_path:
            try:
                import maxminddb
                self._reader = maxminddb.open_database(os.path.expanduser(db_path))
            except Exception:  # noqa: BLE001
                self._reader = None
        self._cache_file = os.path.join(CACHE_DIR, "geoip.json")
        try:
            with open(self._cache_file) as f:
                self._cache = json.load(f)
        except (OSError, ValueError):
            pass

    def poll(self):
        if time.monotonic() - self.at < self.every:
            return
        self.at = time.monotonic()
        peers = {}
        for line in C.run(["ss", "-tnH", "state", "established"]).splitlines():
            f = line.split()
            if len(f) < 4:
                continue
            host = f[3].rsplit(":", 1)[0].strip("[]").split("%")[0]
            try:
                if not ipaddress.ip_address(host).is_global:
                    continue
            except ValueError:
                continue
            peers[host] = peers.get(host, 0) + 1
        self.total = sum(peers.values())
        rows, missing = [], []
        for ip, n in peers.items():
            loc = self._cache.get(ip)
            if loc is None and self._reader is not None:
                loc = self._local(ip)
                self._cache[ip] = loc
            if loc is None:
                missing.append(ip)
            elif loc:
                rows.append((ip, loc[0], loc[1], loc[2], loc[3], n))
        self.rows = rows
        if missing and self.online and self._reader is None and not self._busy \
                and time.monotonic() - self._last_query > 5:
            self._busy = True
            threading.Thread(target=self._lookup, args=(missing[:100],), daemon=True).start()

    def _local(self, ip):
        try:
            r = self._reader.get(ip) or {}
            loc = r.get("location", {})
            if "latitude" not in loc:
                return ()
            return (loc["latitude"], loc["longitude"], r.get("city", {}).get("names", {}).get("en", ""),
                    r.get("country", {}).get("iso_code", ""))
        except Exception:  # noqa: BLE001
            return ()

    def _lookup(self, ips):
        try:
            res = _fetch(IP_API, data=json.dumps(ips).encode())
            for r in res:
                ip = r.get("query")
                if not ip:
                    continue
                self._cache[ip] = (r["lat"], r["lon"], r.get("city", ""), r.get("countryCode", "")) \
                    if r.get("status") == "success" else ()   # () = known unknown, don't ask again
            os.makedirs(CACHE_DIR, exist_ok=True)
            tmp = self._cache_file + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self._cache, f)
            os.replace(tmp, self._cache_file)
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._last_query = time.monotonic()
            self._busy = False
            self.at = 0.0  # re-poll promptly so the new locations show
