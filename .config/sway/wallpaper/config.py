"""User settings for the sway wallpaper. Edit freely; the program reloads on SIGUSR1."""

# Which panel each output shows. Keys are sway output names (swaymsg -t get_outputs).
# Panels: "ambient" (sparse: clock, vitals, network), "portrait" (everything, for a
# vertical screen), "ops" (system/network/git/calendar), "log" (workspace map +
# journal). Unlisted outputs get DEFAULT_PANEL.
PANELS = {
    "eDP-1": "ambient",
    "DP-6": "ops",
    "DP-4": "portrait",
}
DEFAULT_PANEL = "ambient"

# Home location: the ring on the earth map and the sunrise/sunset times (Stockholm by default).
LAT, LON = 59.33, 18.07

# Earth map overlays. Open TCP connections are drawn as arcs from home to the
# peer's city; peers are located with a local MaxMind-format database if
# GEOIP_DB is set (needs the python `maxminddb` module; the free DB-IP city
# lite works), otherwise via ip-api.com (plain http, batched, cached in
# ~/.cache/sway-wallpaper/geoip.json). Set GEOIP_ONLINE = False to stop the
# lookups and only draw what is already cached.
SHOW_SOCKETS = True
GEOIP_DB = ""
GEOIP_ONLINE = True

# Earthquakes from the USGS feed, drawn as rings that fade over the day.
# Feeds: "2.5_day", "4.5_day", "significant_week", "all_hour", ...
SHOW_QUAKES = True
QUAKE_FEED = "2.5_day"

# Repositories to watch on the ops panel.
GIT_REPOS = ["~/dotfiles"]

# Command whose output lines are shown under "calendar" on the ops panel.
# Examples: "khal list now 2d --format '{start-time} {title}'"  or  "gcalcli agenda --nocolor --tsv"
CALENDAR_CMD = "khal list now 2d --format '{start-date-long} {start-time} {title}' 2>/dev/null"

# Redraw cadence in seconds. On battery the wallpaper ticks slower and the ripple stops.
TICK_AC = 1.0
TICK_BATTERY = 5.0

# Ambient field behind the readouts: "contours", "stars", "traces", "radar", "flow",
# "hex", or "blank" (nothing, pure black). Per-output override: FIELDS = {"DP-6": "flat"}.
FIELD = "blank"
FIELDS = {}

# Hex field only: circumradius in logical px and how much of the lattice to keep (0..1).
HEX_RADIUS = 16
HEX_DENSITY = 1.0

# Colour tint on the black background: "mono" (white/grey), "green", "blue", "amber".
TINT = "mono"

# Host pinged for the latency readout (set to "" to disable).
PING_HOST = "1.1.1.1"

# Set to False to keep rendering even when a tiled window covers the workspace.
SLEEP_WHEN_COVERED = True
