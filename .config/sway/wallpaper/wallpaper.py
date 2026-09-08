#!/usr/bin/env python3
"""Live data wallpaper for sway.

One wlr-layer-shell background surface per output, drawn with cairo at 1 Hz on
AC (5 s on battery), and not at all while a tiled window covers the workspace or
the output is powered off. See config.py for settings.

    wallpaper.py                 run under sway
    wallpaper.py --preview DIR   render every panel to PNG (no compositor needed)
    wallpaper.py --preview DIR --fields   render the ambient panel once per field
    kill -USR1 <pid>             reload config.py / theme
"""

import importlib
import json
import os
import signal
import subprocess
import sys
import time
from collections import deque
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config  # noqa: E402
import collectors as C  # noqa: E402
import draw  # noqa: E402
import fields  # noqa: E402
import sun  # noqa: E402
import geo  # noqa: E402


# ---------------------------------------------------------------- data model

class Data:
    """All collectors plus derived state, sampled once per tick."""

    def __init__(self):
        self.cpu, self.mem, self.net = C.Cpu(), C.Mem(), C.Net()
        self.power, self.thermal, self.disk = C.Power(), C.Thermal(), C.Disk()
        self.procs = C.Procs()
        self.kstat = C.Kernel()
        self.host, self.kernel = C.hostname(), C.kernel()
        self.dmi, self.cpu_model = C.dmi(), C.cpu_model()
        self.freq_range = (0.0, 0.0)
        self._ping = C.Cadenced(lambda: C.ping(config.PING_HOST) if config.PING_HOST else None, 30, None)
        self.load, self.nprocs, self.uptime = [0, 0, 0], "", ""
        self.phase = 0.0  # ripple phase, advances with cpu load
        self.scale = 1.0
        self.sun_times, self.sun_elev, self._sun_day = (None, None), 0.0, None
        self.subsolar = (0.0, 0.0)
        self.sockets = geo.Sockets(config.GEOIP_DB, config.GEOIP_ONLINE)
        self.quakes = geo.Quakes(config.QUAKE_FEED)
        self._last = time.monotonic()
        # slow collectors, each on its own cadence
        self._failed = C.Cadenced(C.failed_units, 60, [])
        self._updates = C.Cadenced(C.pending_updates, 1800, None)
        self._ports = C.Cadenced(C.listening_ports, 30, [])
        self._ssh = C.Cadenced(C.ssh_sessions, 30, 0)
        self._git = C.Cadenced(lambda: C.git_status(config.GIT_REPOS), 60, [])
        self._cal = C.Cadenced(lambda: C.calendar(config.CALENDAR_CMD), 300, [])
        self._top = C.Cadenced(lambda: C.top_procs(5), 30, [])
        self._containers = C.Cadenced(C.containers, 60, None)
        self.tree = []          # workspace map from sway
        self.journal = deque(maxlen=60)

    failed = property(lambda s: s._failed.value)
    ping = property(lambda s: s._ping.value)
    updates = property(lambda s: s._updates.value)
    ports = property(lambda s: s._ports.value)
    ssh = property(lambda s: s._ssh.value)
    git = property(lambda s: s._git.value)
    calendar = property(lambda s: s._cal.value)
    top = property(lambda s: s._top.value)
    containers = property(lambda s: s._containers.value)

    def sample(self, need_ops=False, need_procs=False):
        now = time.monotonic()
        dt, self._last = now - self._last, now
        for c in (self.cpu, self.mem, self.net, self.power, self.thermal, self.disk, self.kstat):
            c.sample()
        self.load, self.nprocs = C.loadavg()
        if need_procs:
            self.procs.sample()
        self.uptime = C.uptime()
        self.freq_range = C.cpu_freq_range()
        self._ping.get()
        # the ripple only moves on AC; speed follows cpu load (one wavelength per ~40 s idle)
        if self.power.on_ac:
            self.phase += dt * (1 / 40.0) * (1 + 4 * self.cpu.total)
        if self._sun_day != date.today():
            self._sun_day = date.today()
            self.sun_times = sun.sun_times(config.LAT, config.LON)
        self.sun_elev = sun.elevation(config.LAT, config.LON)
        self.subsolar = sun.subsolar()
        if need_ops:
            if config.SHOW_SOCKETS:
                self.sockets.poll()
            if config.SHOW_QUAKES:
                self.quakes.poll()
        if need_ops:
            for c in (self._failed, self._updates, self._ports, self._ssh, self._git, self._cal,
                      self._top, self._containers):
                c.get()


# ---------------------------------------------------------------- sway IPC

def swaymsg(kind):
    try:
        return json.loads(subprocess.run(["swaymsg", "-t", kind, "-r"], capture_output=True,
                                         text=True, timeout=3).stdout or "null")
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def parse_tree(tree):
    """Per-output visibility and a compact workspace map.

    Returns {output_name: {"covered": bool, "power": bool, "workspaces": [...]}}"""
    result = {}
    if not tree:
        return result

    def windows(node):
        out = []
        for n in node.get("nodes", []) + node.get("floating_nodes", []):
            if n.get("name") and (n.get("app_id") or n.get("window_properties") or n.get("pid")):
                out.append(n.get("app_id") or n.get("window_properties", {}).get("class") or n["name"])
            out += windows(n)
        return out

    for out in tree.get("nodes", []):
        if out.get("type") != "output" or out.get("name") == "__i3":
            continue
        wss = []
        covered = False
        for ws in out.get("nodes", []):
            if ws.get("type") != "workspace":
                continue
            vis = bool(ws.get("visible"))
            tiled = [n for n in ws.get("nodes", []) if n.get("type") == "con"]
            fullscreen = any(n.get("fullscreen_mode") for n in ws.get("floating_nodes", []))
            if vis and (tiled or fullscreen):
                covered = True
            wss.append({"name": ws.get("name", "?"), "visible": vis, "focused": bool(ws.get("focused")),
                        "windows": windows(ws)[:6]})
        result[out["name"]] = {"covered": covered, "power": out.get("dpms", out.get("power", True)),
                               "workspaces": wss,
                               "mode": (f'{out["current_mode"]["width"]}x{out["current_mode"]["height"]}'
                                        if out.get("current_mode") else "")}
    return result


# ---------------------------------------------------------------- GTK app

def run_app():
    import gi
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell  # must load before Gtk so it can hook the Wayland backend
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, GLib, Gtk
    import cairo

    data = Data()
    outputs_by_pos = {}  # (x, y) -> sway output name
    state = {}           # sway output name -> parse_tree entry
    windows = {}         # Gdk.Monitor -> Surface

    class Surface:
        def __init__(self, monitor):
            self.monitor = monitor
            self.name = None
            self.win = Gtk.Window()
            GtkLayerShell.init_for_window(self.win)
            GtkLayerShell.set_layer(self.win, GtkLayerShell.Layer.BACKGROUND)
            GtkLayerShell.set_monitor(self.win, monitor)
            GtkLayerShell.set_exclusive_zone(self.win, -1)
            for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM,
                         GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
                GtkLayerShell.set_anchor(self.win, edge, True)
            try:
                GtkLayerShell.set_keyboard_mode(self.win, GtkLayerShell.KeyboardMode.NONE)
            except AttributeError:
                GtkLayerShell.set_keyboard_interactivity(self.win, False)
            self.area = Gtk.DrawingArea()
            self.area.connect("draw", self.on_draw)
            self.win.add(self.area)
            self.win.connect("realize", lambda w: w.get_window().input_shape_combine_region(cairo.Region(), 0, 0))
            self.win.show_all()
            self.field = None
            self.dirty = True
            self.resolve_name()

        def resolve_name(self):
            g = self.monitor.get_geometry()
            self.name = outputs_by_pos.get((g.x, g.y)) or (self.monitor.get_model() or "?")

        @property
        def panel(self):
            return config.PANELS.get(self.name, config.DEFAULT_PANEL)

        @property
        def field_name(self):
            return getattr(config, "FIELDS", {}).get(self.name, config.FIELD)

        def visible(self):
            st = state.get(self.name)
            if not st:
                return True
            return st["power"] and not (config.SLEEP_WHEN_COVERED and st["covered"])

        def on_draw(self, area, cr):
            w, h = area.get_allocated_width(), area.get_allocated_height()
            if not self.field or (self.field.w, self.field.h) != (w, h):
                self.field = fields.make(self.field_name, w, h, r=config.HEX_RADIUS, density=config.HEX_DENSITY)
            data.scale = self.monitor.get_scale_factor()
            data.tree = [dict(name=n, **st) for n, st in state.items()]
            try:
                draw.PANELS.get(self.panel, draw.panel_ambient)(cr, w, h, data, draw.palette(config.TINT), time.time(), self.field)
            except Exception as e:  # noqa: BLE001 - keep the surface alive; report once per tick
                print("draw error:", repr(e), file=sys.stderr)
            self.dirty = False
            return True

    def refresh_outputs():
        outs = swaymsg("get_outputs") or []
        outputs_by_pos.clear()
        for o in outs:
            r = o.get("rect", {})
            outputs_by_pos[(r.get("x"), r.get("y"))] = o["name"]
        for s in windows.values():
            s.resolve_name()

    def refresh_state():
        state.clear()
        state.update(parse_tree(swaymsg("get_tree")))

    display = Gdk.Display.get_default()

    def add_monitor(d, mon):
        refresh_outputs()
        windows[mon] = Surface(mon)

    def remove_monitor(d, mon):
        s = windows.pop(mon, None)
        if s:
            s.win.destroy()

    refresh_outputs()
    refresh_state()
    for i in range(display.get_n_monitors()):
        add_monitor(display, display.get_monitor(i))
    display.connect("monitor-added", add_monitor)
    display.connect("monitor-removed", remove_monitor)

    # sway events: workspace/window changes decide whether we are visible at all
    def start_subscribe():
        proc = subprocess.Popen(["swaymsg", "-t", "subscribe", "-m", '["workspace","output","window","mode"]'],
                                stdout=subprocess.PIPE, text=True)
        pending = {"id": None}

        def flush():
            pending["id"] = None
            was = {n: s.visible() for n, s in ((s.name, s) for s in windows.values())}
            refresh_state()
            for s in windows.values():
                if s.visible() and (not was.get(s.name) or s.panel == "log"):
                    s.area.queue_draw()
            return False

        def on_line(src, cond):
            line = proc.stdout.readline()
            if not line:
                GLib.timeout_add(2000, start_subscribe)
                return False
            if '"output"' in line or '"change": "unspecified"' in line:
                refresh_outputs()
            if pending["id"] is None:  # coalesce bursts of events into one tree query
                pending["id"] = GLib.timeout_add(150, flush)
            return True

        GLib.io_add_watch(proc.stdout, GLib.IO_IN | GLib.IO_HUP, on_line)
        return False

    start_subscribe()

    # journal follower for the log panel; only started when some output shows it
    if True:  # the ambient panel shows a journal tail too, so always follow
        try:
            jp = subprocess.Popen(["journalctl", "-f", "-n", "60", "-p", "4", "-o", "json", "--no-pager", "-q"],
                                  stdout=subprocess.PIPE, text=True)

            def on_journal(src, cond):
                line = jp.stdout.readline()
                if not line:
                    return False
                try:
                    j = json.loads(line)
                except ValueError:
                    return True
                ts = time.strftime("%H:%M", time.localtime(int(j.get("__REALTIME_TIMESTAMP", 0)) / 1e6))
                unit = j.get("SYSLOG_IDENTIFIER") or j.get("_SYSTEMD_UNIT") or "?"
                msg = j.get("MESSAGE", "")
                if isinstance(msg, list):
                    msg = bytes(msg).decode("utf-8", "replace")
                data.journal.append((int(j.get("PRIORITY", 6)), ts, unit, str(msg).replace("\n", " ")))
                return True

            GLib.io_add_watch(jp.stdout, GLib.IO_IN | GLib.IO_HUP, on_journal)
        except OSError:
            pass

    # the tick
    tick = {"id": None}

    def do_tick():
        vis = [s for s in windows.values() if s.visible()]
        # hidden: sample every 5 s so the history stays continuous, draw nothing
        data.sample(need_ops=any(s.panel in ("ops", "ambient", "portrait") for s in vis),
                    need_procs=any(s.panel in ("ambient", "portrait") or s.field_name in fields.NEEDS_PROCS for s in vis))
        for s in vis:
            s.area.queue_draw()
        on_ac = not data.power.present or data.power.on_ac
        interval = (config.TICK_AC if on_ac else config.TICK_BATTERY) if vis else max(5.0, config.TICK_BATTERY)
        tick["id"] = GLib.timeout_add(int(interval * 1000), do_tick)
        return False

    do_tick()

    def reload(*_):
        importlib.reload(config)
        draw._font_cache.clear()
        for s in windows.values():
            s.field = None
            s.area.queue_draw()
        return True

    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, reload)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda *_: Gtk.main_quit())
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, lambda *_: Gtk.main_quit())
    Gtk.main()


# ---------------------------------------------------------------- preview

def preview(outdir, fake=True, theme=None, all_fields=False):
    """Render each panel to PNG. With fake=True the sparklines are filled with
    synthetic history so the layout can be judged without a running desktop."""
    import math
    import random
    import cairo

    os.makedirs(outdir, exist_ok=True)
    data = Data()
    data.sample(need_ops=True, need_procs=True)
    time.sleep(0.5)
    data.sample(need_ops=True, need_procs=True)
    if fake:
        rnd = random.Random(1)
        for i in range(C.HIST):
            data.cpu.hist.append(0.12 + 0.25 * abs(math.sin(i / 9)) + rnd.random() * 0.15)
            data.cpu.hist_a.append(0.20 + 0.10 * abs(math.sin(i / 7)) + rnd.random() * 0.08)
            data.cpu.hist_b.append(0.15 + (0.5 if i % 90 in (40, 41, 42, 75, 76) else 0.0) + rnd.random() * 0.06)
            data.mem.hist.append(0.45 + 0.05 * math.sin(i / 30))
            data.net.rx_hist.append(rnd.random() ** 3 * 4e6)
            data.net.tx_hist.append(rnd.random() ** 3 * 8e5)
            data.thermal.hist.append(48 + 8 * math.sin(i / 20) + rnd.random() * 3)
            data.power.hist.append(7 + 4 * abs(math.sin(i / 15)) + rnd.random())
        data.cpu.total, data.cpu.cores = 0.31, [rnd.random() * 0.7 for _ in range(16)]
        data.cpu.freq_mhz = 3200
        data.thermal.temp, data.thermal.fan_rpm = 52, 2100
        data.power.present, data.power.on_ac, data.power.status = True, False, "Discharging"
        data.power.level, data.power.watts, data.power.hours_left = 68, 9.4, 5.3
        data.power.health, data.power.cycles = 0.91, "212"
        data.net.wifi, data.net.ssid, data.net.rx, data.net.tx = ("wlan0", 0.72, -58), "hemnet", 2.4e5, 3.1e4
        data.net.ifaces, data.net.vpn = [("wlan0", "192.168.1.42", "wifi"), ("wg0", "10.8.0.2", "vpn")], True
        data._failed.value = ["fwupd-refresh.service"]
        data._updates.value = 14
        data._ports.value = [("tcp", 22), ("tcp", 631), ("udp", 5353), ("tcp", 8080), ("tcp", 3000), ("udp", 68)]
        data._ssh.value = 1
        data._git.value = [("dotfiles", "main", 3, 1, 0), ("project", "feat/wallpaper", 0, 0, 2), ("notes", "main", 0, 0, 0)]
        data._cal.value = ["today 14:00 standup", "today 16:30 dentist", "tomorrow 09:00 sprint review"]
        data._containers.value = ["postgres", "redis"]
        data.phase = 0.37
        data.sockets.total, data.sockets.rows = 23, [
            ("140.82.121.4", 50.12, 8.68, "Frankfurt", "DE", 4), ("151.101.1.69", 37.77, -122.42, "San Francisco", "US", 6),
            ("13.107.42.14", 47.61, -122.33, "Seattle", "US", 2), ("104.16.132.229", 34.05, -118.24, "Los Angeles", "US", 1),
            ("2a00:1450::", 59.33, 18.07, "Stockholm", "SE", 5), ("52.85.1.1", 1.29, 103.85, "Singapore", "SG", 1),
            ("185.199.108.153", 35.68, 139.69, "Tokyo", "JP", 1), ("54.72.1.1", 53.35, -6.26, "Dublin", "IE", 3)]
        tnow = time.time()
        data.quakes.rows, data.quakes.ok = [
            (-8.16, 120.60, 6.1, tnow - 3 * 3600, "Ruteng, Indonesia"), (-58.12, -26.26, 5.1, tnow - 9 * 3600, "South Sandwich Islands"),
            (38.4, 142.1, 4.8, tnow - 20 * 3600, "Japan"), (-33.2, -71.5, 4.6, tnow - 1 * 3600, "Chile"),
            (61.3, -150.1, 3.2, tnow - 5 * 3600, "Alaska"), (36.1, -117.8, 2.9, tnow - 12 * 3600, "California"),
            (-18.9, 168.9, 4.9, tnow - 15 * 3600, "Vanuatu"), (40.2, 24.1, 3.4, tnow - 7 * 3600, "Greece"),
            (28.3, 87.1, 4.1, tnow - 22 * 3600, "Nepal"), (19.4, -155.3, 2.6, tnow - 2 * 3600, "Hawaii")], True
        k = data.kstat
        k.ctxt, k.intr, k.forks, k.running, k.blocked = 14230.0, 3120.0, 12.0, 3, 0
        k.fds, k.fds_max, k.tcp, k.udp, k.entropy = 18432, 9223372036854775807, 42, 9, 256
        for i in range(C.HIST):
            k.ctxt_hist.append(9000 + 6000 * abs(math.sin(i / 13)) + rnd.random() * 2000)
        data.net.bitrate = "866 Mb/s"
        data._ping.value = 6.2
        data.freq_range = (1.19, 3.47)
        data.dmi = ("Dell Inc.", "XPS 15 9530", "Notebook")
        data.procs.threads = 1840
        if data.procs.rows:  # give a few processes a visible cpu share
            rows = data.procs.rows
            for k in rnd.sample(range(len(rows)), min(8, len(rows))):
                pid, comm, rss, _ = rows[k]
                rows[k] = (pid, comm, rss, rnd.random() ** 2 * 0.9)
            data.procs.top = sorted(rows, key=lambda r: r[3], reverse=True)[:8]
        data.tree = [
            {"name": "eDP-1", "mode": "2880x1800", "covered": False, "power": True, "workspaces": [
                {"name": "1", "visible": True, "focused": True, "windows": ["foot", "firefox"]},
                {"name": "2", "visible": False, "focused": False, "windows": ["code"]}]},
            {"name": "DP-6", "mode": "1920x1080", "covered": True, "power": True, "workspaces": [
                {"name": "3", "visible": True, "focused": False, "windows": ["firefox", "signal"]}]},
            {"name": "DP-4", "mode": "1080x1920", "covered": False, "power": True, "workspaces": [
                {"name": "4", "visible": True, "focused": False, "windows": []}]},
        ]
        for i in range(24):
            data.journal.append((4 if i % 4 else 3, f"{9 + i // 6:02d}:{(i * 7) % 60:02d}",
                                 ["kernel", "systemd", "NetworkManager", "sway"][i % 4],
                                 ["usb 1-3: device descriptor read/64, error -71",
                                  "Failed to start Refresh fwupd metadata and update motd.",
                                  "<warn> device (wlan0): supplicant interface state: scanning -> authenticating",
                                  "[1234] xdg_output: unsupported version 3"][i % 4]))
    sizes = {"ambient": (1920, 1200), "portrait": (1080, 1920), "ops": (1920, 1080), "log": (1080, 1920)}
    jobs = [(f"ambient-{f}", "ambient", f) for f in fields.FIELDS] if all_fields else \
        [(n, n, config.FIELD) for n in draw.PANELS]
    for stem, name, fname in jobs:
        fn, (w, h) = draw.PANELS[name], sizes[name]
        for th in ([theme] if theme else [config.TINT]):
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
            cr = cairo.Context(surf)
            field = fields.make(fname, w, h, r=config.HEX_RADIUS, density=config.HEX_DENSITY)
            t0 = time.perf_counter()
            fn(cr, w, h, data, draw.palette(th), time.time(), field)
            t1 = time.perf_counter()
            fn(cr, w, h, data, draw.palette(th), time.time(), field)
            t2 = time.perf_counter()
            path = os.path.join(outdir, f"{stem}-{th}.png")
            surf.write_to_png(path)
            print(f"{os.path.basename(path)}: first {1000 * (t1 - t0):.1f} ms, again {1000 * (t2 - t1):.1f} ms")


if __name__ == "__main__":
    if "--preview" in sys.argv:
        i = sys.argv.index("--preview")
        preview(sys.argv[i + 1] if len(sys.argv) > i + 1 else "preview", fake="--real" not in sys.argv,
                theme=os.environ.get("WALLPAPER_TINT"), all_fields="--fields" in sys.argv)
    else:
        run_app()
