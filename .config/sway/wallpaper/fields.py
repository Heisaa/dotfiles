"""Ambient background fields. Each has draw(cr, p, data, scale, intensity) and is
constructed with (w, h). Pick one with config.FIELD."""

import math
import random

import cairo

from draw import col, text, level_color

# ---------------------------------------------------------------- shared

def _sines(seed, n, fmin, fmax):
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        a = rnd.uniform(0, math.tau)
        f = rnd.uniform(fmin, fmax)
        out.append((math.cos(a) * f, math.sin(a) * f, rnd.uniform(0, math.tau), rnd.uniform(0.6, 1.4)))
    return out


class Flat:
    """No field at all: the panel background stays untouched."""

    def __init__(self, w, h, **_):
        self.w, self.h = w, h

    def draw(self, cr, p, data, scale=1.0, intensity=1.0):
        pass


# ---------------------------------------------------------------- hex

class Hex:
    """Pointy-top hex lattice (cached outlines) with a ripple whose speed follows
    CPU load and sparkles whose count follows it."""

    def __init__(self, w, h, r=16, density=1.0, **_):
        self.w, self.h, self.r = w, h, r
        self.dx, self.dy = math.sqrt(3) * r, 1.5 * r
        rnd = random.Random(7)
        cx, cy, diag = w * 0.5, h * 0.5, math.hypot(w, h) * 0.5
        self.cells = []
        for j in range(int(h / self.dy) + 2):
            for i in range(int(w / self.dx) + 2):
                x = i * self.dx + (self.dx / 2 if j % 2 else 0)
                y = j * self.dy
                if rnd.random() <= density:
                    self.cells.append((x, y, math.hypot(x - cx, y - cy) / diag))
        self.cache = {}

    def _hex(self, cr, x, y, r):
        for k in range(6):
            a = math.pi / 6 + k * math.pi / 3
            (cr.move_to if k == 0 else cr.line_to)(x + r * math.cos(a), y + r * math.sin(a))
        cr.close_path()

    def _outlines(self, scale, p):
        key = (scale, id(p))
        if key not in self.cache:
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(self.w * scale) + 1, int(self.h * scale) + 1)
            surf.set_device_scale(scale, scale)
            cr = cairo.Context(surf)
            cr.set_line_width(1.0)
            g = p["grid"]
            for x, y, d in self.cells:
                a = g[3] * max(0.0, 1.0 - d * 0.9)
                if a > 0.004:
                    cr.set_source_rgba(g[0], g[1], g[2], a)
                    self._hex(cr, x, y, self.r - 1.5)
                    cr.stroke()
            self.cache = {key: surf}
        return self.cache[key]

    def draw(self, cr, p, data, scale=1.0, intensity=1.0):
        cr.set_source_surface(self._outlines(scale, p), 0, 0)
        cr.paint()
        c = p["crest"]
        r = self.r - 2.5
        for x, y, d in self.cells:
            b = math.sin((math.hypot(x, self.h - y) / 420.0 - data.phase) * math.tau)
            if b > 0.65:
                a = ((b - 0.65) / 0.35) ** 2 * 0.065 * max(0.0, 1.0 - d * 0.6) * intensity
                if a > 0.004:
                    cr.set_source_rgba(c[0], c[1], c[2], a)
                    self._hex(cr, x, y, r)
                    cr.fill()
        n = int(data.cpu.total * intensity * 0.05 * len(self.cells))
        rnd = random.Random(int(data.phase * 7.0))
        for _ in range(n):
            x, y, d = self.cells[rnd.randrange(len(self.cells))]
            cr.set_source_rgba(c[0], c[1], c[2], 0.08 + 0.25 * rnd.random() * (1 - d))
            self._hex(cr, x, y, r * 0.55)
            cr.fill()


# ---------------------------------------------------------------- contours

# marching squares: for each case, the pairs of edges (0 top, 1 right, 2 bottom, 3 left) to join
_MS = {1: [(3, 2)], 2: [(2, 1)], 3: [(3, 1)], 4: [(0, 1)], 5: [(3, 0), (2, 1)], 6: [(0, 2)], 7: [(3, 0)],
       8: [(0, 3)], 9: [(0, 2)], 10: [(0, 1), (3, 2)], 11: [(0, 1)], 12: [(3, 1)], 13: [(2, 1)], 14: [(3, 2)]}


class Contours:
    """Iso-lines of a slowly drifting smooth field, like a terrain map. CPU load
    raises the relief so lines crowd together; memory use sets the line count."""

    def __init__(self, w, h, cell=22, **_):
        self.w, self.h, self.cell = w, h, cell
        self.nx, self.ny = int(w / cell) + 2, int(h / cell) + 2
        self.waves = _sines(3, 5, 1 / 900.0, 1 / 320.0)

    def field(self, t, amp):
        waves = self.waves
        c = self.cell
        rows = []
        for j in range(self.ny):
            y = j * c
            row = []
            for i in range(self.nx):
                x = i * c
                v = 0.0
                for fx, fy, ph, sp in waves:
                    v += math.sin((x * fx + y * fy) * math.tau + ph + t * sp)
                row.append(v * amp)
            rows.append(row)
        return rows

    def draw(self, cr, p, data, scale=1.0, intensity=1.0):
        t = data.phase * 4.0  # phase already scales with cpu; slow drift
        amp = 1.0 + 0.8 * data.cpu.total
        g = self.field(t, amp)
        nlev = 7 + int(9 * (data.mem.used / max(1, data.mem.total)))
        levels = [(-4.5 + 9.0 * k / nlev) for k in range(nlev + 1)]
        c = self.cell
        col_ = p["crest"]
        cr.set_line_width(1.0)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        # accumulate segments per level so each gets one stroke with its own alpha
        for k, L in enumerate(levels):
            a = (0.05 + 0.14 * abs(math.sin(k * 1.7))) * intensity  # vary weight a little per line
            cr.set_source_rgba(col_[0], col_[1], col_[2], a)
            for j in range(self.ny - 1):
                r0, r1 = g[j], g[j + 1]
                y0 = j * c
                for i in range(self.nx - 1):
                    tl, tr, br, bl = r0[i], r0[i + 1], r1[i + 1], r1[i]
                    lo = min(tl, tr, br, bl)
                    hi = max(tl, tr, br, bl)
                    if L < lo or L >= hi:
                        continue
                    idx = (8 if tl >= L else 0) | (4 if tr >= L else 0) | (2 if br >= L else 0) | (1 if bl >= L else 0)
                    segs = _MS.get(idx)
                    if not segs:
                        continue
                    x0 = i * c

                    def pt(e):
                        if e == 0:
                            f = (L - tl) / (tr - tl) if tr != tl else 0.5
                            return x0 + f * c, y0
                        if e == 1:
                            f = (L - tr) / (br - tr) if br != tr else 0.5
                            return x0 + c, y0 + f * c
                        if e == 2:
                            f = (L - bl) / (br - bl) if br != bl else 0.5
                            return x0 + f * c, y0 + c
                        f = (L - tl) / (bl - tl) if bl != tl else 0.5
                        return x0, y0 + f * c

                    for e1, e2 in segs:
                        cr.move_to(*pt(e1))
                        cr.line_to(*pt(e2))
            cr.stroke()


# ---------------------------------------------------------------- starfield

class Stars:
    """One point per process: size from memory, brightness from CPU share.
    Positions are a stable hash of the pid, so a process keeps its place."""

    def __init__(self, w, h, **_):
        self.w, self.h = w, h

    def _pos(self, pid, comm):
        rnd = random.Random(f"{pid}:{comm}")
        return rnd.uniform(0.04, 0.96) * self.w, rnd.uniform(0.08, 0.80) * self.h

    def draw(self, cr, p, data, scale=1.0, intensity=1.0):
        rows = data.procs.rows
        if not rows:
            return
        c = p["crest"]
        labels = []
        for pid, comm, rss, cpu in rows:
            x, y = self._pos(pid, comm)
            r = 1.2 + max(0.0, min(3.5, math.log2(max(rss, 1) / (16 * 2 ** 20)) * 0.9))
            a = (0.22 + min(1.0, cpu) * 0.75) * intensity
            cr.set_source_rgba(c[0], c[1], c[2], a)
            cr.arc(x, y, r, 0, math.tau)
            cr.fill()
            if cpu > 0.04:
                # glow
                cr.set_source_rgba(c[0], c[1], c[2], 0.10 * min(1.0, cpu) * intensity)
                cr.arc(x, y, r + 6 + 8 * min(1.0, cpu), 0, math.tau)
                cr.fill()
                labels.append((cpu, x, y, comm, r))
        labels.sort(reverse=True)
        for cpu, x, y, comm, r in labels[:6]:
            text(cr, x + r + 6, y, f"{comm}  {cpu * 100:.0f}%", 9, p["dim"], 0.8 * intensity, valign="middle")


# ---------------------------------------------------------------- traces

class Traces:
    """Long thin traces of the vitals across the full width, seismograph style.
    History scrolls one sample per tick, so the motion is continuous."""

    def __init__(self, w, h, **_):
        self.w, self.h = w, h

    def _trace(self, cr, hist, vmax, base, amp, color, a, label, p, w):
        vals = list(hist)
        n = len(vals)
        if n < 2:
            return
        sx = w / (n - 1)
        col(cr, color, a)
        cr.set_line_width(1.0)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        for i, v in enumerate(vals):
            y = base - min(1.0, v / vmax) * amp
            (cr.move_to if i == 0 else cr.line_to)(i * sx, y)
        cr.stroke()
        col(cr, color, a * 0.3)
        cr.move_to(0, base + 0.5)
        cr.line_to(w, base + 0.5)
        cr.stroke()
        text(cr, 10, base + 4, label, 9, color, a, "medium", spacing=2)

    def draw(self, cr, p, data, scale=1.0, intensity=1.0):
        w, h = self.w, self.h
        amp = h * 0.10
        rows = [(data.cpu.hist, 1.0, p["accent"], 0.55, "cpu")]
        if data.power.present:
            rows.append((data.power.hist, max(15.0, max(data.power.hist) * 1.1), p["ok"], 0.45, "watts"))
        rows.append((data.net.rx_hist, max(200 * 1024, max(data.net.rx_hist) * 1.2), p["dim"], 0.5, "net"))
        if data.thermal.temp:
            rows.append((data.thermal.hist, 100.0, p["warn"], 0.35, "temp"))
        top, bottom = h * 0.22, h * 0.80
        for k, (hist, vmax, color, a, label) in enumerate(rows):
            base = top + (bottom - top) * (k + 1) / len(rows)
            self._trace(cr, hist, vmax, base, amp, color, a * intensity, label, p, w)


# ---------------------------------------------------------------- radar

class Radar:
    """A sweep that completes one turn per minute. Cores are ticks on the rim,
    network activity leaves blips that fade over a few sweeps."""

    def __init__(self, w, h, **_):
        self.w, self.h = w, h
        self.blips = []  # (angle, radius, born_phase)

    def draw(self, cr, p, data, scale=1.0, intensity=1.0):
        import time as _t
        w, h = self.w, self.h
        cx, cy = w * 0.5, h * 0.46
        R = min(w, h) * 0.30
        c, faint = p["crest"], p["faint"]
        sec = _t.time() % 60
        ang = sec / 60 * math.tau - math.pi / 2
        cr.set_line_width(1.0)
        for f in (0.25, 0.5, 0.75, 1.0):
            col(cr, faint, (0.5 if f == 1.0 else 0.28) * intensity)
            cr.arc(cx, cy, R * f, 0, math.tau)
            cr.stroke()
        col(cr, faint, 0.25 * intensity)
        for k in range(12):
            a = k * math.tau / 12
            cr.move_to(cx + R * 0.05 * math.cos(a), cy + R * 0.05 * math.sin(a))
            cr.line_to(cx + R * math.cos(a), cy + R * math.sin(a))
        cr.stroke()
        # cores as rim ticks
        cores = data.cpu.cores or [data.cpu.total]
        for k, u in enumerate(cores):
            a = k * math.tau / len(cores) - math.pi / 2
            col(cr, level_color(u, p), (0.25 + 0.75 * u) * intensity)
            cr.set_line_width(2.0)
            cr.move_to(cx + (R + 8) * math.cos(a), cy + (R + 8) * math.sin(a))
            cr.line_to(cx + (R + 8 + 18 * u + 2) * math.cos(a), cy + (R + 8 + 18 * u + 2) * math.sin(a))
            cr.stroke()
        # sweep trail: 12 fading wedges behind the hand
        for k in range(14):
            a0 = ang - (k + 1) * 0.045
            cr.move_to(cx, cy)
            cr.arc(cx, cy, R, a0, a0 + 0.05)
            cr.close_path()
            col(cr, c, 0.09 * (1 - k / 14) * intensity)
            cr.fill()
        col(cr, c, 0.9 * intensity)
        cr.set_line_width(1.2)
        cr.move_to(cx, cy)
        cr.line_to(cx + R * math.cos(ang), cy + R * math.sin(ang))
        cr.stroke()
        # blips from network activity
        rate = data.net.rx + data.net.tx
        n_new = min(6, int(rate / (150 * 1024)))
        rnd = random.Random(int(sec * 10))
        for _ in range(n_new):
            self.blips.append((ang, R * rnd.uniform(0.15, 0.95), data.phase))
        self.blips = [b for b in self.blips if len(self.blips) < 80][-80:]
        for i, (a, r, born) in enumerate(self.blips):
            age = (len(self.blips) - i) / 80
            col(cr, c, 0.7 * (1 - age) * intensity)
            cr.arc(cx + r * math.cos(a), cy + r * math.sin(a), 2.0, 0, math.tau)
            cr.fill()
        text(cr, cx, cy + R + 44, f"{data.cpu.total * 100:.0f}%", 10, p["dim"], intensity, align="center")


# ---------------------------------------------------------------- flow

class Flow:
    """Streamlines of a slowly rotating vector field. Line weight follows CPU."""

    def __init__(self, w, h, **_):
        self.w, self.h = w, h
        self.waves = _sines(11, 3, 1 / 700.0, 1 / 300.0)
        rnd = random.Random(5)
        self.seeds = [(rnd.uniform(0, w), rnd.uniform(0, h * 0.85)) for _ in range(260)]

    def draw(self, cr, p, data, scale=1.0, intensity=1.0):
        t = data.phase * 3.0
        c = p["crest"]
        waves = self.waves
        step = 7.0
        cr.set_line_width(0.8 + 1.2 * data.cpu.total)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        col(cr, c, 0.13 * intensity)
        for sx, sy in self.seeds:
            x, y = sx, sy
            cr.move_to(x, y)
            for _ in range(30):
                v = 0.0
                for fx, fy, ph, sp in waves:
                    v += math.sin((x * fx + y * fy) * math.tau + ph + t * sp)
                a = v * 1.2
                x += step * math.cos(a)
                y += step * math.sin(a)
                if x < 0 or x > self.w or y < 0 or y > self.h:
                    break
                cr.line_to(x, y)
            cr.stroke()


FIELDS = {"flat": Flat, "blank": Flat, "hex": Hex, "contours": Contours, "stars": Stars, "traces": Traces,
          "radar": Radar, "flow": Flow}
NEEDS_PROCS = {"stars"}


def make(name, w, h, **kw):
    return FIELDS.get(name, Contours)(w, h, **kw)
