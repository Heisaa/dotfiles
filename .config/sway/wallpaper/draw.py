"""Panel rendering. Every panel is a function (cr, w, h, data, theme, t) that
draws with cairo in logical pixels; nothing here knows about GTK."""

import math
from datetime import datetime, timezone

import cairo
import gi

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo  # noqa: E402

import config  # noqa: E402
import earth  # noqa: E402

FONT = "JetBrains Mono, DejaVu Sans Mono, monospace"

def _tint(ink, dim, faint, accent, warn):
    return dict(bg=(0.0, 0.0, 0.0), grid=(*faint, 0.5), ink=ink, dim=dim, faint=faint, accent=accent,
                ok=dim, warn=warn, bad=(1.0, 1.0, 1.0), crest=accent)


# Everything sits on pure black. A tint is one hue in four intensities; alerts go
# brighter rather than to another colour, which keeps the monochrome discipline.
PALETTES = {
    "mono": _tint(ink=(0.88, 0.90, 0.92), dim=(0.52, 0.55, 0.58), faint=(0.24, 0.26, 0.28),
                  accent=(0.93, 0.95, 0.97), warn=(1.0, 1.0, 1.0)),
    "green": _tint(ink=(0.58, 0.95, 0.68), dim=(0.30, 0.56, 0.38), faint=(0.12, 0.26, 0.16),
                   accent=(0.40, 1.0, 0.58), warn=(0.85, 1.0, 0.88)),
    "blue": _tint(ink=(0.66, 0.86, 1.0), dim=(0.36, 0.52, 0.64), faint=(0.14, 0.22, 0.30),
                  accent=(0.50, 0.82, 1.0), warn=(0.88, 0.96, 1.0)),
    "amber": _tint(ink=(1.0, 0.84, 0.58), dim=(0.62, 0.50, 0.34), faint=(0.28, 0.22, 0.14),
                   accent=(1.0, 0.76, 0.40), warn=(1.0, 0.94, 0.82)),
}
PALETTES["dark"] = PALETTES["light"] = PALETTES["mono"]


def palette(name):
    return PALETTES.get(name, PALETTES["mono"])


def rgba(c, a=1.0):
    return (c[0], c[1], c[2], (c[3] if len(c) > 3 else 1.0) * a)


def col(cr, c, a=1.0):
    cr.set_source_rgba(*rgba(c, a))


_font_cache = {}


def _font(size, weight):
    key = (size, weight)
    if key not in _font_cache:
        fd = Pango.FontDescription(FONT)
        fd.set_absolute_size(size * Pango.SCALE)
        fd.set_weight({"light": Pango.Weight.LIGHT, "bold": Pango.Weight.BOLD,
                       "medium": Pango.Weight.MEDIUM}.get(weight, Pango.Weight.NORMAL))
        _font_cache[key] = fd
    return _font_cache[key]


def text(cr, x, y, s, size=11, color=(1, 1, 1), a=1.0, weight="normal", align="left",
         spacing=0.0, valign="top"):
    """Draw a string; returns (width, height). `spacing` is letter spacing in px."""
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(_font(size, weight))
    if spacing:
        from gi.repository import GLib
        layout.set_markup(f'<span letter_spacing="{int(spacing * Pango.SCALE)}">{GLib.markup_escape_text(s)}</span>', -1)
    else:
        layout.set_text(s, -1)
    _, log = layout.get_pixel_extents()
    tw, th = log.width, log.height
    if align == "right":
        x -= tw
    elif align == "center":
        x -= tw / 2
    if valign == "bottom":
        y -= th
    elif valign == "middle":
        y -= th / 2
    col(cr, color, a)
    cr.move_to(x, y)
    PangoCairo.show_layout(cr, layout)
    return tw, th


def hline(cr, x1, x2, y, color, a=1.0, width=1.0):
    col(cr, color, a)
    cr.set_line_width(width)
    cr.move_to(x1, y + 0.5)
    cr.line_to(x2, y + 0.5)
    cr.stroke()


def spark(cr, x, y, w, h, values, vmax, color, fill=0.12, line=1.2):
    """Sparkline of the last `w` values (one px per sample), anchored at the right edge."""
    vals = list(values)[-int(w):]
    if not vals or vmax <= 0:
        return
    n = len(vals)
    x0 = x + w - n
    pts = [(x0 + i, y + h - min(1.0, v / vmax) * h) for i, v in enumerate(vals)]
    if fill:
        cr.move_to(pts[0][0], y + h)
        for px, py in pts:
            cr.line_to(px, py)
        cr.line_to(pts[-1][0], y + h)
        cr.close_path()
        col(cr, color, fill)
        cr.fill()
    cr.set_line_width(line)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    col(cr, color)
    cr.move_to(*pts[0])
    for p in pts[1:]:
        cr.line_to(*p)
    cr.stroke()
    # current-value marker
    cr.arc(pts[-1][0], pts[-1][1], 1.8, 0, math.tau)
    cr.fill()


def hbar(cr, x, y, w, h, frac, color, track, ta=0.25):
    col(cr, track, ta)
    cr.rectangle(x, y, w, h)
    cr.fill()
    col(cr, color)
    cr.rectangle(x, y, max(0.0, min(1.0, frac)) * w, h)
    cr.fill()


def ring(cr, cx, cy, r, frac, color, track, width=2.0, ta=0.25, start=-math.pi / 2):
    cr.set_line_width(width)
    col(cr, track, ta)
    cr.arc(cx, cy, r, 0, math.tau)
    cr.stroke()
    if frac > 0:
        col(cr, color)
        cr.arc(cx, cy, r, start, start + math.tau * max(0.0, min(1.0, frac)))
        cr.stroke()


def fmt_bytes(n, per_s=False):
    units = ["B", "K", "M", "G", "T"]
    i = 0
    n = float(n)
    while n >= 1000 and i < len(units) - 1:
        n /= 1024
        i += 1
    s = f"{n:.0f}" if n >= 100 or i == 0 else f"{n:.1f}"
    return f"{s}{units[i]}" + ("/s" if per_s else "")


def level_color(frac, p, hi=0.85, mid=0.6):
    return p["bad"] if frac >= hi else p["warn"] if frac >= mid else p["ink"]


# ---------------------------------------------------------------- shared bits

def clock_fmt(data):
    """Seconds only when the wallpaper actually ticks every second (on AC)."""
    pw = data.power
    on_ac = not pw.present or pw.on_ac
    tick = config.TICK_AC if on_ac else config.TICK_BATTERY
    return "%H:%M:%S" if tick <= 1.0 else "%H:%M"


def heading(cr, x, y, s, p, w=None):
    text(cr, x, y, s.upper(), 10, p["accent"], 0.9, "medium", spacing=2.5)
    if w:
        hline(cr, x, x + w, y + 18, p["faint"], 0.35)
    return y + 30


def block_spark(cr, x, y, w, h, label, value, hist, vmax, color, p, sub=None):
    """A labelled sparkline block: label top-left, value top-right, graph below."""
    text(cr, x, y, label, 10, p["dim"], 1.0, "medium", spacing=2)
    text(cr, x + w, y, value, 12, p["ink"], 1.0, align="right")
    if sub:
        text(cr, x + w, y + 15, sub, 9, p["dim"], 1.0, align="right")
    gy = y + 32
    hline(cr, x, x + w, gy + h, p["faint"], 0.35)
    spark(cr, x, gy, w, h, hist, vmax, color)


_earth_cache = {}


def earth_map(cr, x, y, w, data, p, pitch=3.5):
    """Dot-matrix world map (equirectangular) with the sunlit hemisphere. Land dots
    are bright where the sun is up, dim in twilight and faint at night; ocean dots
    only appear where it is day. The subsolar point and home are marked. Header:
    date and UTC; footer: local sunrise, elevation, sunset. Returns the height."""
    h = w / 2
    now = datetime.now().astimezone()
    utc = datetime.now(timezone.utc)
    decl, slon = data.subsolar
    text(cr, x, y, now.strftime("%A %-d %B").upper(), 9, p["dim"], 1.0, "medium", spacing=2)
    text(cr, x + w, y, utc.strftime("%H:%M UTC"), 9, p["dim"], 1.0, "medium", spacing=2, align="right")
    my = y + 22
    # the dots move ~0.25 deg/min; re-render the cached surface at most once a minute
    slot = (w, pitch, data.scale)
    key = (id(p), round(slon * 4), round(decl * 4))
    hit = _earth_cache.get(slot)
    if hit is None or hit[0] != key:
        hit = (key, _render_earth(w, h, pitch, decl, slon, p, data.scale))
        _earth_cache[slot] = hit
    surf = hit[1]
    cr.set_source_surface(surf, x, my)
    cr.paint()

    def proj(lat, lon):
        return x + (lon + 180) / 360 * w, my + (90 - lat) / 180 * h

    cr.new_path()
    cr.save()
    cr.rectangle(x, my, w, h)
    cr.clip()
    # open connections: great-circle arcs from home to each peer, a dot at the peer
    socks = data.sockets.rows if config.SHOW_SOCKETS else []
    if socks:
        cr.set_line_width(1.0)
        col(cr, p["dim"], 0.55)
        for _ip, lat, lon, _city, _cc, _n in socks:
            _great_circle(cr, proj, config.LAT, config.LON, lat, lon)
        cr.stroke()
        for _ip, lat, lon, _city, _cc, n in socks:
            px_, py_ = proj(lat, lon)
            col(cr, p["ink"])
            cr.arc(px_, py_, 1.6 + min(4, n) * 0.35, 0, math.tau)
            cr.fill()
    # earthquakes: rings sized by magnitude, fading over 24 h
    quakes = data.quakes.rows if config.SHOW_QUAKES else []
    if quakes:
        tnow = datetime.now().timestamp()
        cr.set_line_width(1.0)
        for lat, lon, mag, when, _place in quakes:
            age = max(0.0, min(1.0, (tnow - when) / 86400))
            a = 0.25 + 0.75 * (1 - age)
            qx, qy = proj(lat, lon)
            r = 2.5 + max(0.0, mag - 2.5) * 2.2
            col(cr, p["accent"] if mag >= 5 else p["dim"], a)
            cr.arc(qx, qy, r, 0, math.tau)
            cr.stroke()
            if mag >= 5:
                col(cr, p["accent"], a * 0.35)
                cr.arc(qx, qy, r * 1.8, 0, math.tau)
                cr.stroke()
                text(cr, qx + r + 3, qy, f"M{mag:.1f}", 8, p["accent"], a, valign="middle")
                cr.new_path()
    cr.restore()
    cr.new_path()

    # home
    hx, hy = proj(config.LAT, config.LON)
    cr.new_path()
    cr.set_line_width(1.0)
    col(cr, p["ink"])
    cr.arc(hx, hy, 3.5, 0, math.tau)
    cr.stroke()
    cr.arc(hx, hy, 1.0, 0, math.tau)
    cr.fill()
    # subsolar point
    sx, sy = proj(decl, slon)
    col(cr, p["accent"])
    cr.arc(sx, sy, 3.5, 0, math.tau)
    cr.fill()
    col(cr, p["accent"], 0.18)
    cr.arc(sx, sy, 10, 0, math.tau)
    cr.fill()

    fy = my + h + 8
    rise, sett = data.sun_times
    if rise and sett:
        text(cr, x, fy, "RISE " + rise.strftime("%H:%M"), 9, p["dim"], 1.0, spacing=1)
        text(cr, x + w, fy, "SET " + sett.strftime("%H:%M"), 9, p["dim"], 1.0, spacing=1, align="right")
    else:
        text(cr, x, fy, "POLAR DAY" if data.sun_elev > 0 else "POLAR NIGHT", 9, p["dim"], 1.0, spacing=1)
    text(cr, x + w / 2, fy, f"SUN {data.sun_elev:+.0f}°", 9, p["ink"] if data.sun_elev > 0 else p["faint"], 1.0,
         spacing=1, align="center")
    fy += 14
    if socks or quakes or (config.SHOW_SOCKETS and data.sockets.total):
        fy += 2
        if config.SHOW_SOCKETS:
            sites = len({(r[3], r[4]) for r in socks})
            text(cr, x, fy, f"{data.sockets.total} CONN · {sites} SITES", 9, p["faint"], 1.0, spacing=1)
        if quakes:
            lat, lon, mag, when, place = quakes[0]
            place = place.split(" of ", 1)[-1] if " of " in place else place
            text(cr, x + w, fy, f"{len(quakes)} QUAKES · M{mag:.1f} {place[:24].upper()}", 9, p["faint"], 1.0,
                 spacing=1, align="right")
        fy += 14
    return fy - y


def _great_circle(cr, proj, lat1, lon1, lat2, lon2, steps=24):
    """Add the shorter great-circle path between two points to the current path,
    broken where it crosses the dateline."""
    p1 = (math.radians(lat1), math.radians(lon1))
    p2 = (math.radians(lat2), math.radians(lon2))
    v1 = (math.cos(p1[0]) * math.cos(p1[1]), math.cos(p1[0]) * math.sin(p1[1]), math.sin(p1[0]))
    v2 = (math.cos(p2[0]) * math.cos(p2[1]), math.cos(p2[0]) * math.sin(p2[1]), math.sin(p2[0]))
    dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(v1, v2))))
    om = math.acos(dot)
    if om < 1e-6:
        return
    prev_lon, first = None, True
    for i in range(steps + 1):
        t = i / steps
        a, b = math.sin((1 - t) * om) / math.sin(om), math.sin(t * om) / math.sin(om)
        vx, vy, vz = (a * v1[k] + b * v2[k] for k in range(3))
        lat, lon = math.degrees(math.atan2(vz, math.hypot(vx, vy))), math.degrees(math.atan2(vy, vx))
        if prev_lon is not None and abs(lon - prev_lon) > 180:
            first = True
        px_, py_ = proj(lat, lon)
        (cr.move_to if first else cr.line_to)(px_, py_)
        first, prev_lon = False, lon


def _render_earth(w, h, pitch, decl, slon, p, scale):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(w * scale) + 1, int(h * scale) + 1)
    surf.set_device_scale(scale, scale)
    cr = cairo.Context(surf)
    nx, ny = int(w / pitch), int(h / pitch)
    px, py = w / nx, h / ny
    sd, cd = math.sin(math.radians(decl)), math.cos(math.radians(decl))
    lons = [-180 + (i + 0.5) * 360 / nx for i in range(nx)]
    coslon = [math.cos(math.radians(lo - slon)) for lo in lons]
    twilight = math.sin(math.radians(-6))
    land_s, ocean_s = px * 0.5, px * 0.28
    # six classes: (land?, day/twilight/night) -> one fill each
    classes = {("land", 0): (p["ink"], 0.95), ("land", 1): (p["dim"], 1.0), ("land", 2): (p["faint"], 0.9),
               ("sea", 0): (p["faint"], 0.55), ("sea", 1): (p["faint"], 0.28)}
    paths = {k: [] for k in classes}
    for j in range(ny):
        lat = 90 - (j + 0.5) * 180 / ny
        a, b = math.sin(math.radians(lat)) * sd, math.cos(math.radians(lat)) * cd
        cy = (j + 0.5) * py
        for i in range(nx):
            cosz = a + b * coslon[i]
            phase = 0 if cosz > 0 else 1 if cosz > twilight else 2
            land = earth.is_land(lat, lons[i])
            if not land and phase == 2:
                continue
            paths[("land" if land else "sea", phase)].append(((i + 0.5) * px, cy))
    for k, pts in paths.items():
        if not pts:
            continue
        s = land_s if k[0] == "land" else ocean_s
        for cx, cy in pts:
            cr.rectangle(cx - s / 2, cy - s / 2, s, s)
        col(cr, *classes[k])
        cr.fill()
    # terminator
    cr.set_line_width(1.0)
    col(cr, p["dim"], 0.6)
    if abs(decl) < 0.05:
        for lo in (slon - 90, slon + 90):
            xx = ((lo + 180) % 360) / 360 * w
            cr.move_to(xx, 0)
            cr.line_to(xx, h)
    else:
        td = math.tan(math.radians(decl))
        prev = None
        for i in range(nx * 2 + 1):
            lo = -180 + i * 180 / nx
            lat = math.degrees(math.atan(-math.cos(math.radians(lo - slon)) / td))
            pt = ((lo + 180) / 360 * w, (90 - lat) / 180 * h)
            (cr.line_to if prev else cr.move_to)(*pt)
            prev = pt
    cr.stroke()
    return surf


# ---------------------------------------------------------------- panels

def fmt_rate(n):
    return f"{n / 1000:.1f}k" if n >= 1000 else f"{n:.0f}"


def frame(cr, x, y, w, h, left, right, p):
    """Panel header (two small labels and a rule). If h is given the chamfered
    outline is drawn now; otherwise call frame_close() once the content height
    is known. Returns the content y."""
    text(cr, x, y, left.upper(), 9, p["dim"], 1.0, "medium", spacing=2)
    text(cr, x + w, y, right.upper(), 9, p["dim"], 1.0, "medium", spacing=2, align="right")
    hline(cr, x, x + w, y + 16, p["dim"], 0.8)
    if h:
        frame_close(cr, x, y, w, h, p)
    return y + 30


def frame_close(cr, x, y, w, h, p):
    ch = 8
    col(cr, p["faint"], 0.9)
    cr.set_line_width(1.0)
    cr.move_to(x + 0.5, y + 16.5)
    cr.line_to(x + 0.5, y + h - ch)
    cr.line_to(x + ch + 0.5, y + h + 0.5)
    cr.line_to(x + w - ch - 0.5, y + h + 0.5)
    cr.line_to(x + w - 0.5, y + h - ch)
    cr.line_to(x + w - 0.5, y + 16.5)
    cr.stroke()


def section(cr, x, y, w, title, right, p):
    """A section title inside a panel: bold-ish label left, dim note right, rule below."""
    text(cr, x, y, title.upper(), 12, p["ink"], 1.0, "medium", spacing=1)
    if right:
        text(cr, x + w, y + 2, right, 9, p["dim"], 1.0, align="right")
    hline(cr, x, x + w, y + 20, p["faint"], 0.9)
    return y + 30


def stat_row(cr, x, y, w, items, p, big=13):
    """Evenly spaced LABEL-over-value cells, like the eDEX header rows."""
    n = len(items)
    cw = w / n
    for i, (label, value) in enumerate(items):
        cx = x + i * cw
        text(cr, cx, y, label.upper(), 9, p["dim"], 1.0, spacing=1)
        text(cr, cx, y + 14, str(value), big, p["ink"], 0.95)
    return y + 14 + big + 12


def grid_spark(cr, x, y, w, h, series, vmax, p, label=None):
    """A line graph on a faint grid, white line, no fill. `series` is a list of
    (values, alpha) so several traces can share the axes."""
    col(cr, p["faint"], 0.5)
    cr.set_line_width(1.0)
    for k in range(1, 4):
        gy = y + h * k / 4
        cr.move_to(x, gy + 0.5)
        cr.line_to(x + w, gy + 0.5)
    for k in range(1, 6):
        gx = x + w * k / 6
        cr.move_to(int(gx) + 0.5, y)
        cr.line_to(int(gx) + 0.5, y + h)
    cr.stroke()
    hline(cr, x, x + w, y + h, p["dim"], 0.7)
    for vals, a in series:
        vals = list(vals)
        n = len(vals)
        if n < 2:
            continue
        step = w / (n - 1)
        col(cr, p["ink"], a)
        cr.set_line_width(1.3)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        for i, v in enumerate(vals):
            py = y + h - min(1.0, v / vmax) * (h - 2) - 1
            (cr.move_to if i == 0 else cr.line_to)(x + i * step, py)
        cr.stroke()
    if label:
        text(cr, x + w, y + 2, label, 8, p["dim"], 1.0, align="right")


def dot_grid(cr, x, y, w, h, frac, p, cols=72, rows=8):
    """The memory map: a lattice of dots, lit in proportion to use. The lit set
    is a stable hash so it flickers only where use actually changes."""
    n = cols * rows
    lit = int(frac * n)
    order = sorted(range(n), key=lambda i: (i * 2654435761) % 1000003)
    lit_set = set(order[:lit])
    dx, dy = w / cols, h / rows
    for i in range(n):
        r, c = divmod(i, cols)
        px, py = x + c * dx + dx / 2, y + r * dy + dy / 2
        on = i in lit_set
        col(cr, p["accent"] if on else p["dim"], 1.0 if on else 0.55)
        cr.rectangle(px - 1.5, py - 1.5, 3, 3) if on else cr.rectangle(px - 1, py - 1, 2, 2)
        cr.fill()


def bar(cr, x, y, w, frac, p, ticks=True):
    hline(cr, x, x + w, y, p["faint"], 1.0)
    col(cr, p["ink"], 0.9)
    cr.rectangle(x, y - 1, max(0.0, min(1.0, frac)) * w, 3)
    cr.fill()
    if ticks:
        for k in range(0, 5):
            tx = int(x + w * k / 4) + 0.5
            col(cr, p["dim"], 0.8)
            cr.move_to(tx, y - 3)
            cr.line_to(tx, y + 4)
            cr.stroke()


# ---------------------------------------------------------------- blocks
# Each block draws a framed panel at (x, y, w). With h=None the frame wraps the
# content; otherwise it is exactly h tall. All return the y just below the frame.

def block_system(cr, x, y0, w, data, p, h=None, clock=True):
    now = datetime.now()
    pw, mem = data.power, data.mem
    y = frame(cr, x, y0, w, h, "panel", "system", p)
    ix, iw = x + 16, w - 32
    if clock:
        y += 6
        text(cr, ix, y, now.strftime(clock_fmt(data)), 54, p["ink"], 1.0, "light", spacing=6)
        y += 74
    y = stat_row(cr, ix, y, iw, [(now.strftime("%Y"), now.strftime("%b %d").upper()), ("uptime", data.uptime),
                                 ("type", "linux"), ("power", f"{pw.level}%" if pw.present else "ac")], p)
    hline(cr, ix, ix + iw, y - 4, p["faint"], 0.9)
    y += 6
    vendor, model, chassis = data.dmi
    y = stat_row(cr, ix, y, iw, [("manufacturer", vendor[:16]), ("model", model[:16]), ("chassis", chassis)], p, big=11)
    hline(cr, ix, ix + iw, y - 4, p["faint"], 0.9)
    y += 8
    y = section(cr, ix, y, iw, "cpu usage", data.cpu_model[:34], p)
    cores = data.cpu.cores or [data.cpu.total]
    half = max(1, len(cores) // 2) if len(cores) > 1 else 1
    groups = [cores[:half], cores[half:]] if len(cores) > 1 else [cores]
    hist_groups = [data.cpu.hist_a, data.cpu.hist_b] if len(cores) > 1 else [data.cpu.hist]
    for gi, (grp, hist) in enumerate(zip(groups, hist_groups)):
        if not grp:
            continue
        lo = 1 + gi * half
        text(cr, ix, y, f"# {lo} - {lo + len(grp) - 1}", 10, p["ink"], 0.9, "medium")
        text(cr, ix, y + 15, f"Avg. {sum(grp) / len(grp) * 100:.0f}%", 9, p["dim"])
        grid_spark(cr, ix + 76, y, iw - 76, 40, [(hist, 0.9)], 1.0, p)
        y += 54
    fmin, fmax = data.freq_range
    y = stat_row(cr, ix, y, iw, [("temp", f"{data.thermal.temp:.0f}°C" if data.thermal.temp else "—"),
                                 ("min", f"{fmin:.2f}GHz"), ("max", f"{fmax:.2f}GHz"),
                                 ("tasks", data.nprocs.split("/")[-1])], p, big=11)
    hline(cr, ix, ix + iw, y - 4, p["faint"], 0.9)
    y += 8
    y = section(cr, ix, y, iw, "memory", f"USING {fmt_bytes(mem.used)} OUT OF {fmt_bytes(mem.total)}", p)
    dot_grid(cr, ix, y, iw, 64, mem.used / mem.total, p)
    y += 74
    text(cr, ix, y, "SWAP", 10, p["ink"], 0.9, "medium", spacing=1)
    text(cr, ix + iw, y, f"{fmt_bytes(mem.swap_used)} / {fmt_bytes(mem.swap_total)}" if mem.swap_total else "none", 9, p["dim"], 1.0, align="right")
    bar(cr, ix + 52, y + 7, iw - 52 - 84, (mem.swap_used / mem.swap_total) if mem.swap_total else 0.0, p, ticks=False)
    y += 26
    y = section(cr, ix, y, iw, "top processes", "PID | NAME | CPU | MEM", p)
    for pid, comm, rss, cpu in data.procs.top[:7]:
        text(cr, ix, y, str(pid), 11, p["dim"])
        text(cr, ix + 64, y, comm[:20], 12, p["ink"], 0.95)
        text(cr, ix + iw - 56, y, f"{cpu * 100:.1f}%", 11, p["ink"], 0.9, align="right")
        text(cr, ix + iw, y, f"{rss / mem.total * 100:.1f}%", 11, p["dim"], 1.0, align="right")
        y += 20
    y += 8
    n_failed = len(data.failed)
    upd, cont = data.updates, data.containers
    y = section(cr, ix, y, iw, "services", "systemd · packages · containers", p)
    y = stat_row(cr, ix, y, iw, [("failed units", n_failed if n_failed else "none"),
                                 ("updates", "—" if upd is None else (upd or "none")),
                                 ("containers", "—" if cont is None else len(cont)),
                                 ("ssh", data.ssh or "none")], p, big=11)
    for u in data.failed[:3]:
        text(cr, ix, y, u, 10, p["bad"], 0.9)
        y += 16
    for c in (cont or [])[:3]:
        text(cr, ix, y, c, 10, p["ink"], 0.8)
        y += 16
    y += 6
    y = section(cr, ix, y, iw, "repositories", "branch · state", p)
    if not data.git:
        text(cr, ix, y, "none configured", 10, p["faint"])
        y += 18
    for name, branch, dirty, ahead, behind in data.git[:6]:
        state = ([f"{dirty} changed"] if dirty else []) + ([f"↑{ahead}"] if ahead else []) + ([f"↓{behind}"] if behind else [])
        text(cr, ix, y, name, 11, p["ink"], 0.95)
        text(cr, ix + iw * 0.42, y, branch, 10, p["dim"])
        text(cr, ix + iw, y, "  ".join(state) or "clean", 10, p["ink"] if (dirty or ahead) else p["dim"], 1.0, align="right")
        y += 20
    if h is None:
        h = y + 8 - y0
        frame_close(cr, x, y0, w, h, p)
    return y0 + h


def block_network(cr, x, y0, w, data, p, h=None, graph_h=150):
    net = data.net
    y = frame(cr, x, y0, w, h, "panel", "network", p)
    ix, iw = x + 16, w - 32
    iface = net.wifi[0] if net.wifi else (net.ifaces[0][0] if net.ifaces else "none")
    ip = next((i for n, i, k in net.ifaces if n == iface), "—")
    y = section(cr, ix, y, iw, "network status", f"Interface: {iface}", p)
    online = bool(net.ifaces)
    cells = [("state", "ONLINE" if online else "OFFLINE"), ("ipv4", ip),
             ("ping", f"{data.ping:.0f}ms" if data.ping is not None else "—")]
    if net.wifi and iw > 500:
        cells += [("signal", f"{net.wifi[2]:.0f} dBm"), ("link", net.bitrate or "—")]
    cells.append(("vpn", "UP" if net.vpn else "DOWN"))
    y = stat_row(cr, ix, y, iw, cells, p)
    if net.wifi and iw <= 500:
        y = stat_row(cr, ix, y, iw, [("ssid", net.ssid or "—"), ("signal", f"{net.wifi[2]:.0f} dBm"), ("link", net.bitrate or "—")], p, big=11)
    elif net.wifi and net.ssid:
        text(cr, ix, y - 6, f"SSID {net.ssid}", 9, p["dim"], 1.0, spacing=1)
        y += 10
    hline(cr, ix, ix + iw, y - 4, p["faint"], 0.9)
    y += 8
    netmax = max(200 * 1024, max(net.rx_hist) * 1.2, max(net.tx_hist) * 1.2)
    y = section(cr, ix, y, iw, "network traffic", f"UP {fmt_bytes(net.tx, True)}  DOWN {fmt_bytes(net.rx, True)}", p)
    if h:
        graph_h = h - (y - y0) - 96
    grid_spark(cr, ix, y, iw, graph_h, [(list(net.rx_hist)[-300:], 0.9), (list(net.tx_hist)[-300:], 0.45)], netmax, p,
               label=fmt_bytes(netmax, True))
    y += graph_h + 10
    ports = data.ports
    text(cr, ix, y, "LISTENING", 9, p["dim"], 1.0, spacing=1)
    text(cr, ix + iw, y, f"{len(ports)} sockets", 9, p["dim"], 1.0, align="right")
    y += 16
    pc = max(4, iw // 90)
    pw_ = iw / pc
    rows = 0
    for i, (proto, port) in enumerate(ports[:pc * 2]):
        r_, c_ = divmod(i, pc)
        rows = max(rows, r_ + 1)
        text(cr, ix + c_ * pw_, y + r_ * 18, str(port), 11, p["ink"], 0.9)
        text(cr, ix + c_ * pw_ + 40, y + r_ * 18 + 2, proto, 8, p["dim"])
    y += max(1, rows) * 18
    if h is None:
        h = y + 10 - y0
        frame_close(cr, x, y0, w, h, p)
    return y0 + h


def block_history(cr, x, y0, w, data, p, h=None, graph_h=100):
    pw, mem = data.power, data.mem
    y = frame(cr, x, y0, w, h, "panel", "history", p)
    ix, iw = x + 16, w - 32
    blocks = [("cpu", f"{data.cpu.total * 100:.0f}%", data.cpu.hist, 1.0),
              ("memory", f"{mem.used / mem.total * 100:.0f}%", mem.hist, 1.0)]
    if pw.present:
        blocks.append(("power", f"{pw.watts:.1f}W" if not pw.on_ac else pw.status.lower(), pw.hist, max(15.0, max(pw.hist) * 1.1)))
    if data.thermal.temp:
        blocks.append(("thermal", f"{data.thermal.temp:.0f}°C", data.thermal.hist, 100.0))
    per_row = len(blocks) if iw >= 600 else 2
    rows = math.ceil(len(blocks) / per_row)
    bw = (iw - (per_row - 1) * 24) / per_row
    if h:
        graph_h = (h - 30 - 8 - rows * 34) / rows
    for i, (label, val, hist, vmax) in enumerate(blocks):
        r_, c_ = divmod(i, per_row)
        bx = ix + c_ * (bw + 24)
        by = y + r_ * (graph_h + 34)
        text(cr, bx, by, label.upper(), 9, p["dim"], 1.0, spacing=1)
        text(cr, bx + bw, by, val, 11, p["ink"], 0.95, align="right")
        grid_spark(cr, bx, by + 20, bw, graph_h, [(list(hist)[-int(bw):], 0.9)], vmax, p)
    y += rows * (graph_h + 34)
    if h is None:
        h = y - y0
        frame_close(cr, x, y0, w, h, p)
    return y0 + h


def block_workspaces(cr, x, y0, w, data, p, h=None):
    y = frame(cr, x, y0, w, h, "panel", "workspaces", p)
    ix, iw = x + 16, w - 32
    for out in data.tree:
        text(cr, ix, y, out["name"], 10, p["dim"], 1.0, "medium", spacing=1)
        text(cr, ix + iw, y, out.get("mode", ""), 9, p["faint"], 1.0, align="right")
        y += 18
        for ws in out["workspaces"]:
            active = ws["visible"]
            col(cr, p["ink"] if active else p["faint"], 0.9)
            cr.rectangle(ix + 4, y + 3, 3, 10)
            cr.fill()
            text(cr, ix + 16, y, ws["name"], 10, p["ink"] if active else p["dim"], 1.0, "medium" if ws["focused"] else "normal")
            if ws["windows"]:
                text(cr, ix + 44, y, " · ".join(ws["windows"])[:int((iw - 60) / 6.2)], 10, p["dim"] if active else p["faint"])
            y += 17
        y += 6
    if h is None:
        h = y + 4 - y0
        frame_close(cr, x, y0, w, h, p)
    return y0 + h


def block_kernel(cr, x, y0, w, data, p, h=None):
    pw = data.power
    y = frame(cr, x, y0, w, h, "panel", "kernel", p)
    ix, iw = x + 16, w - 32
    k = data.kstat
    y = section(cr, ix, y, iw, "counters", data.kernel[:22], p)
    y = stat_row(cr, ix, y, iw, [("ctx/s", fmt_rate(k.ctxt)), ("irq/s", fmt_rate(k.intr)), ("forks/s", f"{k.forks:.0f}")], p, big=11)
    y = stat_row(cr, ix, y, iw, [("run", k.running), ("blocked", k.blocked), ("threads", data.procs.threads)], p, big=11)
    y = stat_row(cr, ix, y, iw, [("files", k.fds), ("tcp", k.tcp), ("udp", k.udp)], p, big=11)
    y = stat_row(cr, ix, y, iw, [("entropy", k.entropy), ("disk r", fmt_bytes(data.disk.read_bps, True)),
                                 ("disk w", fmt_bytes(data.disk.write_bps, True))], p, big=11)
    grid_spark(cr, ix, y, iw, 44, [(list(k.ctxt_hist)[-180:], 0.9)], max(k.ctxt_hist) or 1, p, label="ctx")
    y += 56
    y = section(cr, ix, y, iw, "storage", "", p)
    for label, used, total in (("/", data.disk.root_used, data.disk.root_total), ("~", data.disk.home_used, data.disk.home_total)):
        if not total:
            continue
        text(cr, ix, y, label, 11, p["ink"], 0.9, "medium")
        text(cr, ix + iw, y, f"{fmt_bytes(used)} / {fmt_bytes(total)}", 9, p["dim"], 1.0, align="right")
        bar(cr, ix + 20, y + 7, iw - 20 - 100, used / total, p, ticks=False)
        y += 22
    if pw.present and pw.health:
        y += 6
        y = section(cr, ix, y, iw, "battery", "", p)
        y = stat_row(cr, ix, y, iw, [("health", f"{pw.health * 100:.0f}%"), ("cycles", pw.cycles or "—"),
                                     ("draw", f"{pw.watts:.1f}W" if not pw.on_ac else pw.status.lower())], p, big=11)
    if h is None:
        h = y + 4 - y0
        frame_close(cr, x, y0, w, h, p)
    return y0 + h


def block_journal(cr, x, y0, w, data, p, h):
    y = frame(cr, x, y0, w, h, "panel", "journal", p)
    ix, iw = x + 16, w - 32
    avail = int((y0 + h - y - 10) / 16)
    lines = list(data.journal)[-avail:][::-1]
    if not lines:
        text(cr, ix, y, "quiet", 10, p["faint"])
    for i, (prio, ts, unit, msg) in enumerate(lines):
        fade = max(0.3, 1.0 - i / max(1, avail) * 0.8)
        text(cr, ix, y, ts, 9, p["dim"], fade)
        text(cr, ix + 38, y, unit[:14], 9, p["bad"] if prio <= 3 else p["ink"], fade * 0.9)
        text(cr, ix + 38 + 96, y, msg[:int((iw - 134) / 5.6)], 9, p["dim"], fade)
        y += 16
    return y0 + h


def sun_block(cr, x, y, w, data, p):
    pw = data.power
    hh = earth_map(cr, x, y, w, data, p)
    cx, yy = x + w / 2, y + hh + 10
    text(cr, cx, yy, data.host.upper(), 9, p["dim"], 1.0, "medium", spacing=2, align="center")
    text(cr, cx, yy + 16, f"load {data.load[0]:.2f} {data.load[1]:.2f} {data.load[2]:.2f}", 9, p["faint"], 1.0, align="center")
    text(cr, cx, yy + 32, "BATTERY" if (pw.present and not pw.on_ac) else "AC POWER", 9, p["dim"], 1.0, "medium", spacing=2, align="center")
    return yy + 46


# ---------------------------------------------------------------- panels

def panel_ambient(cr, w, h, data, p, t, field):
    """The laptop screen: sparse. Clock and a few vitals; the detail lives on the
    portrait panel."""
    col(cr, p["bg"])
    cr.paint()
    field.draw(cr, p, data, data.scale, 1.0)
    m = 64
    now = datetime.now()
    pw, mem, net = data.power, data.mem, data.net
    top, bottom = m, h - m

    # clock, top-left, large
    text(cr, m, top, now.strftime(clock_fmt(data)), 96, p["ink"], 1.0, "light", spacing=10)
    y = top + 128
    y = stat_row(cr, m, y, 820, [(now.strftime("%A").upper(), now.strftime("%-d %B").upper()), ("uptime", data.uptime),
                                 ("load", f"{data.load[0]:.2f} {data.load[1]:.2f} {data.load[2]:.2f}"),
                                 ("power", (f"{pw.level}%" + ("" if pw.on_ac else f" · {pw.watts:.1f}W")) if pw.present else "ac"),
                                 ("tasks", data.nprocs.split("/")[-1])], p)
    hline(cr, m, m + 820, y - 4, p["faint"], 0.9)

    # earth, top-right
    earth_map(cr, w - m - 440, top + 4, 440, data, p)

    # bottom-left: history (wide), bottom-right: network (narrower), staggered heights
    g = 36
    hw = int((w - 2 * m - g) * 0.58)
    nw = w - 2 * m - g - hw
    hh = 230
    block_history(cr, m, bottom - hh, hw, data, p, h=hh, graph_h=hh - 74)
    nh = 300
    block_network(cr, m + hw + g, bottom - nh, nw, data, p, h=nh)

    # a thin strip of the top three processes above the history panel
    y = bottom - hh - 30 - 20 * 3 - 8
    text(cr, m, y, "TOP", 9, p["dim"], 1.0, spacing=1)
    y += 16
    for pid, comm, rss, cpu in data.procs.top[:3]:
        text(cr, m, y, comm[:20], 11, p["ink"], 0.9)
        text(cr, m + 220, y, f"{cpu * 100:.1f}%", 10, p["dim"], 1.0, align="right")
        text(cr, m + 300, y, fmt_bytes(rss), 10, p["dim"], 1.0, align="right")
        y += 20


def panel_portrait(cr, w, h, data, p, t, field):
    """The vertical screen: everything, in two columns."""
    col(cr, p["bg"])
    cr.paint()
    field.draw(cr, p, data, data.scale, 1.0)
    m = 40
    g = 24
    cw = (w - 2 * m - g) // 2
    lx, rx = m, m + cw + g
    top, bottom = m, h - m

    ly = block_system(cr, lx, top, cw, data, p)
    ly = block_workspaces(cr, lx, ly + g, cw, data, p)

    ry = block_network(cr, rx, top, cw, data, p, graph_h=120)
    ry = block_kernel(cr, rx, ry + g, cw, data, p)
    ry = block_history(cr, rx, ry + g, cw, data, p, graph_h=64)
    ry = sun_block(cr, rx, ry + g, cw, data, p)

    jy = max(ly, ry) + g
    if bottom - jy > 120:
        block_journal(cr, lx, jy, w - 2 * m, data, p, h=bottom - jy)


def panel_ops(cr, w, h, data, p, t, field):
    col(cr, p["bg"])
    cr.paint()
    field.draw(cr, p, data, data.scale, 0.5)

    m = 72
    text(cr, m, m, "OPERATIONS", 11, p["ink"], 0.9, "medium", spacing=3)
    text(cr, w - m, m, datetime.now().strftime("%H:%M  %a %-d %b").upper(), 10, p["dim"], 1.0, spacing=1.5, align="right")
    hline(cr, m, w - m, m + 24, p["faint"], 0.35)

    ncol = 3 if w >= 1400 else 2 if w >= 900 else 1
    cw = (w - 2 * m - (ncol - 1) * 48) / ncol
    cols_x = [m + i * (cw + 48) for i in range(ncol)]
    lh = 20

    def row(x, y, k, v, vcolor=None, ka=1.0):
        text(cr, x, y, k, 11, p["dim"], ka)
        text(cr, x + cw, y, v, 11, vcolor or p["ink"], 1.0, align="right")
        return y + lh

    # bottom band: the three vitals as sparklines, so the panel reads at a glance
    bh = 40
    by = h - m - bh
    band = [("cpu", f"{data.cpu.total * 100:.0f}%", data.cpu.hist, 1.0, level_color(data.cpu.total, p), None),
            ("memory", f"{fmt_bytes(data.mem.used)} / {fmt_bytes(data.mem.total)}", data.mem.hist, 1.0,
             level_color(data.mem.used / data.mem.total, p), None)]
    if data.thermal.temp:
        band.append(("thermal", f"{data.thermal.temp:.0f}°C", data.thermal.hist, 100.0,
                     level_color(data.thermal.temp / 100, p, 0.85, 0.7), None))
    if data.power.present and not data.power.on_ac:
        band.append(("power", f"{data.power.watts:.1f} W", data.power.hist, max(15.0, max(data.power.hist) * 1.1), p["accent"], None))
    bw = (w - 2 * m - (len(band) - 1) * 48) / len(band)
    for i, (label, val, hist, vmax, color, sub) in enumerate(band):
        block_spark(cr, m + i * (bw + 48), by - 32, bw, bh, label, val, hist, vmax, color, p, sub)

    # -- column 1: system
    x, y = cols_x[0], m + 56
    y = heading(cr, x, y, "system", p, cw)
    y = row(x, y, "host", data.host)
    y = row(x, y, "kernel", data.kernel)
    y = row(x, y, "uptime", data.uptime)
    y = row(x, y, "load", f"{data.load[0]:.2f}  {data.load[1]:.2f}  {data.load[2]:.2f}")
    y = row(x, y, "processes", data.nprocs)
    y = row(x, y, "cpu", f"{data.cpu.total * 100:.0f}%", level_color(data.cpu.total, p))
    y = row(x, y, "memory", f"{fmt_bytes(data.mem.used)} / {fmt_bytes(data.mem.total)}")
    y = row(x, y, "root", f"{fmt_bytes(data.disk.root_used)} / {fmt_bytes(data.disk.root_total)}",
            level_color(data.disk.root_used / max(1, data.disk.root_total), p, 0.92, 0.8))
    y = row(x, y, "disk io", f"r {fmt_bytes(data.disk.read_bps, True)}  w {fmt_bytes(data.disk.write_bps, True)}")
    if data.thermal.temp:
        y = row(x, y, "thermal", f"{data.thermal.temp:.0f}°C" + (f"  {data.thermal.fan_rpm} rpm" if data.thermal.fan_rpm else ""))
    if data.power.present:
        y = row(x, y, "battery", f"{data.power.level}%  {data.power.status.lower()}" + (
            f"  {data.power.watts:.1f} W" if not data.power.on_ac else ""))
        if data.power.health:
            y = row(x, y, "battery health", f"{data.power.health * 100:.0f}%" + (f"  {data.power.cycles} cycles" if data.power.cycles else ""))
    y += 12
    n_failed = len(data.failed)
    y = row(x, y, "failed units", str(n_failed) if n_failed else "none", p["bad"] if n_failed else p["ok"])
    for u in data.failed[:6]:
        text(cr, x + 12, y, u, 11, p["bad"], 0.9)
        y += lh
    upd = data.updates
    y = row(x, y, "pending updates", "—" if upd is None else (str(upd) if upd else "up to date"),
            p["warn"] if upd else p["ok"])
    if data.containers is not None:
        y = row(x, y, "containers", str(len(data.containers)) if data.containers else "none")
        for c in data.containers[:6]:
            text(cr, x + 12, y, c, 11, p["ink"], 0.8)
            y += lh
    y += 12
    y = heading(cr, x, y, "memory · top", p, cw)
    for rss, name in data.top:
        y = row(x, y, name, fmt_bytes(rss))

    # -- column 2: network + ports
    x, y = cols_x[1 % ncol], (m + 56 if ncol > 1 else y + 24)
    y = heading(cr, x, y, "network", p, cw)
    net = data.net
    y = row(x, y, "throughput", f"▾{fmt_bytes(net.rx, True)}   ▴{fmt_bytes(net.tx, True)}")
    if net.wifi:
        y = row(x, y, "wifi", f"{net.ssid or net.wifi[0]}  {net.wifi[2]:.0f} dBm")
        hbar(cr, x, y + 4, cw, 2, net.wifi[1], p["accent"], p["faint"])
        y += 12
    y = row(x, y, "vpn", "up" if net.vpn else "down", p["ok"] if net.vpn else p["dim"])
    for name, ip, kind in net.ifaces[:6]:
        y = row(x, y, name, ip)
    y = row(x, y, "ssh sessions", str(data.ssh), p["warn"] if data.ssh else None)
    gy = y + 8
    spark(cr, x, gy, cw, 36, net.rx_hist, max(200 * 1024, max(net.rx_hist) * 1.2), p["accent"])
    spark(cr, x, gy, cw, 36, net.tx_hist, max(200 * 1024, max(net.rx_hist) * 1.2), p["dim"], fill=0.0, line=1.0)
    hline(cr, x, x + cw, gy + 36, p["faint"], 0.35)
    y = gy + 36 + 28
    y = heading(cr, x, y, f"listening · {len(data.ports)}", p, cw)
    ports = data.ports[:24]
    pc = 3
    pw_ = cw / pc
    for i, (proto, port) in enumerate(ports):
        r_, c_ = divmod(i, pc)
        text(cr, x + c_ * pw_, y + r_ * lh, f"{port}", 11, p["ink"], 0.9)
        text(cr, x + c_ * pw_ + 50, y + r_ * lh, proto, 10, p["dim"])
    y += math.ceil(len(ports) / pc) * lh + 12

    # -- column 3: git + calendar
    x, y = cols_x[2 % ncol], (m + 56 if ncol > 2 else y + 24)
    y = heading(cr, x, y, "repositories", p, cw)
    if not data.git:
        text(cr, x, y, "none configured", 11, p["faint"])
        y += lh
    for name, branch, dirty, ahead, behind in data.git:
        state = []
        if dirty:
            state.append(f"{dirty} changed")
        if ahead:
            state.append(f"↑{ahead}")
        if behind:
            state.append(f"↓{behind}")
        color = p["warn"] if (dirty or ahead) else p["ok"]
        text(cr, x, y, name, 11, p["ink"])
        text(cr, x + cw * 0.42, y, branch, 11, p["dim"])
        text(cr, x + cw, y, "  ".join(state) or "clean", 11, color, align="right")
        y += lh
    y += 24
    y = heading(cr, x, y, "calendar", p, cw)
    if not data.calendar:
        text(cr, x, y, "nothing scheduled", 11, p["faint"])
        y += lh
    for line in data.calendar[:8]:
        text(cr, x, y, line[:int(cw / 6.8)], 11, p["ink"], 0.9)
        y += lh


def panel_log(cr, w, h, data, p, t, field):
    col(cr, p["bg"])
    cr.paint()
    field.draw(cr, p, data, data.scale, 0.5)

    m = 56
    text(cr, m, m, "WORKSPACES", 11, p["ink"], 0.9, "medium", spacing=3)
    text(cr, w - m, m, datetime.now().strftime("%H:%M"), 10, p["dim"], 1.0, align="right")
    hline(cr, m, w - m, m + 24, p["faint"], 0.35)
    y = m + 44
    lh = 18
    for out in data.tree:
        text(cr, m, y, out["name"], 10, p["dim"], 1.0, "medium", spacing=1.5)
        text(cr, w - m, y, out.get("mode", ""), 9, p["faint"], 1.0, align="right")
        y += lh + 2
        for ws in out["workspaces"]:
            active = ws["visible"]
            focused = ws["focused"]
            # workspace chip
            col(cr, p["accent"] if active else p["faint"], 0.9 if active else 0.5)
            cr.rectangle(m + 6, y + 3, 3, 10)
            cr.fill()
            text(cr, m + 18, y, ws["name"], 10, p["ink"] if active else p["dim"], 1.0,
                 "medium" if focused else "normal")
            names = ws["windows"]
            if names:
                s = " · ".join(names)
                text(cr, m + 18 + 28, y, s[:int((w - 2 * m - 60) / 6.2)], 10, p["dim"] if active else p["faint"], 0.9)
            y += lh
        y += 8
    y += 12
    text(cr, m, y, "JOURNAL", 11, p["ink"], 0.9, "medium", spacing=3)
    text(cr, w - m, y, "warnings and above", 9, p["faint"], 1.0, align="right")
    hline(cr, m, w - m, y + 24, p["faint"], 0.35)
    y += 40
    # newest at the top, fade older lines toward the bottom
    avail = int((h - m - y) / lh)
    lines = list(data.journal)[-avail:][::-1]
    for i, (prio, ts, unit, msg) in enumerate(lines):
        fade = max(0.25, 1.0 - i / max(1, avail) * 0.9)
        pcol = p["bad"] if prio <= 3 else p["warn"] if prio == 4 else p["dim"]
        text(cr, m, y, ts, 10, p["faint"], fade)
        text(cr, m + 48, y, unit[:16], 10, pcol, fade)
        text(cr, m + 48 + 116, y, msg[:int((w - 2 * m - 170) / 6.2)], 10, p["ink"], fade * 0.85)
        y += lh


PANELS = {"ambient": panel_ambient, "portrait": panel_portrait, "ops": panel_ops, "log": panel_log}
