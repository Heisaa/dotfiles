# sway live wallpaper

A data-driven desktop background: one wlr-layer-shell surface per output,
drawn with cairo. Ambient hex field whose ripple speed follows CPU load, plus
readouts. Designed to cost nothing when you can't see it.

## Panels (config.py → PANELS)

| panel     | shows                                                                 |
|-----------|-----------------------------------------------------------------------|
| `ambient` | sparse laptop page: big clock, date/uptime/load/power/tasks, earth map with the sunlit hemisphere, top 3 processes, history graphs, network panel |
| `portrait` | everything, two columns for a vertical screen: system (clock, machine, cpu, memory lattice, top processes, services, repos), workspaces, network, kernel, storage, battery, history, earth map, journal |
| `ops`     | system vitals, failed units, pending updates, containers, top RSS, network/ifaces/wifi/vpn/ssh, listening ports, git repos, calendar |
| `log`     | workspace map for all outputs, journal warnings and errors (live via `journalctl -f`) |

## Ambient field (config.py → FIELD, per-output FIELDS)

| field      | what it is                                                          | ms/frame |
|------------|---------------------------------------------------------------------|----------|
| `contours` | drifting terrain iso-lines; CPU raises the relief, RAM sets line count | 18 |
| `traces`   | full-width seismograph traces of cpu, watts, net, temp              | 12 |
| `flow`     | streamlines of a slowly rotating vector field, weight follows CPU   | 15 |
| `hex`      | hex lattice with a CPU-paced ripple and sparkles                    | 9  |
| `radar`    | one sweep per minute, cores as rim ticks, network as fading blips   | 6  |
| `stars`    | one point per process: size = memory, brightness = CPU share        | 4  |
| `blank`    | nothing at all, readouts on pure black (alias `flat`)               | 0  |

    FIELD = "blank"
    FIELDS = {"DP-6": "flat"}   # optional per-output override

Change it and `pkill -USR1 -f wallpaper/wallpaper.py`. Preview all of them
with `wallpaper.py --preview /tmp/prev --fields`.

## Power behaviour

- 1 Hz redraw on AC, every 5 s on battery (ripple frozen on battery).
- No redraw at all while a tiled or fullscreen window covers the visible
  workspace of that output, or while the output is powered off (sway IPC
  subscription, not polling). Data is still sampled every 5 s so the
  sparklines stay continuous.
- Slow collectors run on their own cadence: failed units / git 60 s, ports and
  ssh 30 s, calendar 5 min, package updates 30 min.
- A full frame is ~10 ms of cairo work; the hex outline grid is cached.

## Dependencies

python3, PyGObject, pycairo, GTK 3, gtk-layer-shell, and a monospace font
(JetBrains Mono preferred, falls back to DejaVu Sans Mono).

    # Arch
    sudo pacman -S python-gobject python-cairo gtk3 gtk-layer-shell ttf-jetbrains-mono
    # Debian/Ubuntu
    sudo apt install python3-gi python3-gi-cairo python3-cairo gir1.2-gtk-3.0 gir1.2-gtklayershell-0.1 fonts-jetbrains-mono

Optional, used if present: `iw` (SSID), `ss` (ports, ssh sessions),
`checkupdates`/`apt`/`dnf` (pending updates), `docker`, `khal` or whatever
you put in `CALENDAR_CMD`.

## Running

The sway config has `exec_always ~/.config/sway/wallpaper/wallpaper.sh`, so it
starts with sway and restarts on reload. Remove any `output * bg ...` line.

    wallpaper/wallpaper.py --preview /tmp/prev     # render PNGs with fake data, no sway needed
    wallpaper/wallpaper.py --preview /tmp/prev --real
    kill -USR1 $(pgrep -f wallpaper/wallpaper.py)  # reload config.py and re-detect theme
    tail -f $XDG_RUNTIME_DIR/sway-wallpaper.log

## Earth map

Dot-matrix equirectangular map: land dots are bright where the sun is up,
dim in civil twilight, faint at night; ocean dots only show in daylight. The
terminator is drawn as a line, the subsolar point is the bright disc and home
(`LAT, LON`) is the ring. The dot surface is re-rendered at most once a
minute (~10 ms) and painted otherwise (<1 ms).

Overlays (config.py → SHOW_SOCKETS, SHOW_QUAKES):

- **open connections**: every established TCP peer with a public address is
  drawn as a great-circle arc from home to its city, dot size by connection
  count. Peers are located with a local MaxMind-format db (`GEOIP_DB`, needs
  `python-maxminddb`; the free DB-IP city lite works) or, by default, by
  ip-api.com over plain http in batches of up to 100, at most one request per
  5 s, results cached in `~/.cache/sway-wallpaper/geoip.json`. Set
  `GEOIP_ONLINE = False` to send nothing and use only the cache.
- **earthquakes**: the USGS feed (`QUAKE_FEED`, default `2.5_day`) every
  15 min; rings sized by magnitude that fade over 24 h, M5+ labelled. Counts
  and the strongest quake go in the footer line under the map.

Both fetch in daemon threads; offline they simply stay empty.

## Colours

Always pure black. `TINT` in config.py picks the single hue used for text and
graphs: `mono` (white/grey, eDEX-style), `green`, `blue` or `amber`. Alerts
go brighter rather than changing colour. Preview one with
`WALLPAPER_TINT=green wallpaper.py --preview /tmp/prev`.

## Files

- `wallpaper.py` GTK/layer-shell app, sway IPC gating, journal follower, preview mode
- `draw.py`      palettes, text/sparkline helpers, the three panels
- `fields.py`    the ambient fields listed above
- `collectors.py` /proc and /sys readers plus rate-limited subprocess collectors
- `sun.py`       sunrise/sunset/elevation, subsolar point
- `geo.py`       open-connection geolocation and the USGS quake feed
- `earth.py`     0.5° land mask (Natural Earth 110m, embedded), `python3 earth.py land.geojson` rebuilds it
- `config.py`    the settings you edit
