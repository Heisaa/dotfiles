"""Cheap data collectors for the wallpaper. Everything reads /proc and /sys
directly; anything that needs a subprocess is rate limited by `every`."""

import glob
import re
import json
import os
import shutil
import socket
import subprocess
import time
from collections import deque

HIST = 600  # samples kept per sparkline (10 min at 1 Hz)
WHOLE_DISK = re.compile(r"^(sd[a-z]+|vd[a-z]+|nvme\d+n\d+|mmcblk\d+)$")


def read(path, default=""):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def run(cmd, timeout=5):
    """Run a command and return stdout, "" on any failure."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              shell=isinstance(cmd, str)).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


class Cadenced:
    """Wraps an expensive collector so it only refreshes every N seconds."""

    def __init__(self, fn, every, initial=None):
        self.fn, self.every, self.value, self.at = fn, every, initial, 0.0

    def get(self, force=False):
        now = time.monotonic()
        if force or now - self.at >= self.every:
            try:
                self.value = self.fn()
            except Exception:  # noqa: BLE001 - a broken collector must not kill the wallpaper
                pass
            self.at = now
        return self.value


# ---------------------------------------------------------------- CPU / RAM

class Cpu:
    def __init__(self):
        self.prev = None
        self.total = 0.0
        self.cores = []
        self.hist = deque([0.0] * HIST, maxlen=HIST)
        self.hist_a = deque([0.0] * HIST, maxlen=HIST)  # first half of the cores
        self.hist_b = deque([0.0] * HIST, maxlen=HIST)  # second half
        self.freq_mhz = 0
        self.sample()

    def sample(self):
        rows = []
        for line in read("/proc/stat").splitlines():
            if not line.startswith("cpu"):
                break
            f = list(map(int, line.split()[1:]))
            idle = f[3] + f[4]
            rows.append((sum(f), idle))
        if self.prev and len(self.prev) == len(rows):
            usage = []
            for (t, i), (pt, pi) in zip(rows, self.prev):
                dt = t - pt
                usage.append(0.0 if dt <= 0 else 1.0 - (i - pi) / dt)
            self.total, self.cores = usage[0], usage[1:]
            self.hist.append(self.total)
            half = max(1, len(self.cores) // 2)
            a, b = self.cores[:half], self.cores[half:]
            self.hist_a.append(sum(a) / len(a) if a else 0.0)
            self.hist_b.append(sum(b) / len(b) if b else 0.0)
        self.prev = rows
        khz = read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", "0")
        self.freq_mhz = int(khz) // 1000 if khz.isdigit() else 0


class Mem:
    def __init__(self):
        self.total = self.used = self.swap_total = self.swap_used = 0
        self.hist = deque([0.0] * HIST, maxlen=HIST)

    def sample(self):
        kv = {}
        for line in read("/proc/meminfo").splitlines():
            k, _, v = line.partition(":")
            kv[k] = int(v.split()[0]) * 1024
        self.total = kv.get("MemTotal", 1)
        self.used = self.total - kv.get("MemAvailable", 0)
        self.swap_total = kv.get("SwapTotal", 0)
        self.swap_used = self.swap_total - kv.get("SwapFree", 0)
        self.hist.append(self.used / self.total)


def loadavg():
    p = read("/proc/loadavg", "0 0 0 0/0").split()
    return [float(x) for x in p[:3]], p[3] if len(p) > 3 else "0/0"


# ---------------------------------------------------------------- Network

class Net:
    def __init__(self):
        self.prev = None
        self.rx = self.tx = 0.0  # bytes/s
        self.rx_hist = deque([0.0] * HIST, maxlen=HIST)
        self.tx_hist = deque([0.0] * HIST, maxlen=HIST)
        self.ifaces = []  # (name, ip, kind)
        self.wifi = None  # (iface, quality 0..1, dbm)
        self.vpn = False
        self._slow = Cadenced(self._slow_fn, 20)
        self.ssid = ""
        self.bitrate = ""

    def sample(self):
        rx = tx = 0
        for stats in glob.glob("/sys/class/net/*/statistics"):
            name = stats.split("/")[4]
            if name == "lo":
                continue
            rx += int(read(stats + "/rx_bytes", "0") or 0)
            tx += int(read(stats + "/tx_bytes", "0") or 0)
        now = time.monotonic()
        if self.prev:
            dt = max(now - self.prev[0], 1e-3)
            self.rx = max(0.0, (rx - self.prev[1]) / dt)
            self.tx = max(0.0, (tx - self.prev[2]) / dt)
            self.rx_hist.append(self.rx)
            self.tx_hist.append(self.tx)
        self.prev = (now, rx, tx)
        # /proc/net/wireless is cheap; read it every tick
        self.wifi = None
        for line in read("/proc/net/wireless").splitlines()[2:]:
            p = line.replace(":", " ").split()
            if len(p) >= 4:
                q = float(p[2])
                dbm = float(p[3])
                self.wifi = (p[0], max(0.0, min(1.0, (dbm + 90) / 60)) if dbm < 0 else min(1.0, q / 70), dbm)
        self._slow.get()

    def _slow_fn(self):
        ifaces = []
        for line in run(["ip", "-j", "-4", "addr"]) and json.loads(run(["ip", "-j", "-4", "addr"])) or []:
            name = line.get("ifname", "")
            if name == "lo" or line.get("operstate") not in ("UP", "UNKNOWN"):
                continue
            ips = [a["local"] for a in line.get("addr_info", []) if a.get("family") == "inet"]
            if not ips:
                continue
            kind = "vpn" if name.startswith(("tun", "wg", "tailscale", "proton")) else (
                "wifi" if name.startswith(("wl",)) else "eth")
            ifaces.append((name, ips[0], kind))
        self.ifaces = ifaces
        self.vpn = any(k == "vpn" for _, _, k in ifaces)
        self.ssid = ""
        if self.wifi and shutil.which("iw"):
            for line in run(["iw", "dev", self.wifi[0], "link"]).splitlines():
                line = line.strip()
                if line.startswith("SSID:"):
                    self.ssid = line.split(":", 1)[1].strip()
                elif line.startswith("tx bitrate:"):
                    self.bitrate = line.split(":", 1)[1].split("MBit")[0].strip() + " Mb/s"
        return True


# ---------------------------------------------------------------- Power / thermal

class Power:
    def __init__(self):
        self.dir = next(iter(glob.glob("/sys/class/power_supply/BAT*")), None)
        self.present = self.dir is not None
        self.on_ac = True
        self.status = ""
        self.level = 100
        self.watts = 0.0
        self.hours_left = None
        self.hist = deque([0.0] * HIST, maxlen=HIST)
        self.cycles = read((self.dir or "") + "/cycle_count", "")
        self.health = None
        full, design = read((self.dir or "") + "/charge_full"), read((self.dir or "") + "/charge_full_design")
        if not full:
            full, design = read((self.dir or "") + "/energy_full"), read((self.dir or "") + "/energy_full_design")
        if full.isdigit() and design.isdigit() and int(design):
            self.health = int(full) / int(design)

    def sample(self):
        if not self.present:
            return
        d = self.dir
        self.status = read(d + "/status", "Unknown")
        self.level = int(read(d + "/capacity", "100") or 100)
        self.on_ac = self.status not in ("Discharging",)
        pw = read(d + "/power_now")
        if pw.isdigit():
            uw = int(pw)
        else:
            ua, uv = read(d + "/current_now", "0"), read(d + "/voltage_now", "0")
            uw = int(ua or 0) * int(uv or 0) / 1e6
        self.watts = uw / 1e6
        self.hist.append(self.watts if not self.on_ac else 0.0)
        self.hours_left = None
        if uw > 0:
            if self.status == "Discharging":
                rem = read(d + "/energy_now") or read(d + "/charge_now")
                rate = read(d + "/power_now") or read(d + "/current_now")
                if rem.isdigit() and rate.isdigit() and int(rate):
                    self.hours_left = int(rem) / int(rate)
            elif self.status == "Charging":
                full = read(d + "/energy_full") or read(d + "/charge_full")
                rem = read(d + "/energy_now") or read(d + "/charge_now")
                rate = read(d + "/power_now") or read(d + "/current_now")
                if full.isdigit() and rem.isdigit() and rate.isdigit() and int(rate):
                    self.hours_left = (int(full) - int(rem)) / int(rate)


class Thermal:
    def __init__(self):
        self.zones = []
        for z in glob.glob("/sys/class/thermal/thermal_zone*"):
            self.zones.append((read(z + "/type", "?"), z + "/temp"))
        self.fans = glob.glob("/sys/class/hwmon/hwmon*/fan*_input")
        self.temp = 0.0
        self.fan_rpm = None
        self.hist = deque([0.0] * HIST, maxlen=HIST)

    def sample(self):
        temps = []
        for kind, path in self.zones:
            t = read(path, "")
            if t.lstrip("-").isdigit():
                temps.append((kind, int(t) / 1000))
        pref = [t for k, t in temps if "pkg" in k or "cpu" in k.lower() or "acpitz" in k]
        self.temp = max(pref) if pref else (max(t for _, t in temps) if temps else 0.0)
        self.hist.append(self.temp)
        rpms = [int(read(f, "0") or 0) for f in self.fans]
        self.fan_rpm = max(rpms) if rpms else None


# ---------------------------------------------------------------- Disk

class Disk:
    def __init__(self):
        self.prev = None
        self.read_bps = self.write_bps = 0.0
        self.root_used = self.root_total = 0
        self.home_used = self.home_total = 0

    def sample(self):
        rd = wr = 0
        for line in read("/proc/diskstats").splitlines():
            p = line.split()
            if len(p) < 10 or not WHOLE_DISK.match(p[2]):
                continue
            rd += int(p[5]) * 512
            wr += int(p[9]) * 512
        now = time.monotonic()
        if self.prev:
            dt = max(now - self.prev[0], 1e-3)
            self.read_bps = max(0.0, (rd - self.prev[1]) / dt)
            self.write_bps = max(0.0, (wr - self.prev[2]) / dt)
        self.prev = (now, rd, wr)
        for attr, path in (("root", "/"), ("home", os.path.expanduser("~"))):
            try:
                st = os.statvfs(path)
                setattr(self, attr + "_total", st.f_blocks * st.f_frsize)
                setattr(self, attr + "_used", (st.f_blocks - st.f_bavail) * st.f_frsize)
            except OSError:
                pass


# ---------------------------------------------------------------- Ops (slow, subprocess based)

def failed_units():
    out = run(["systemctl", "--failed", "--no-legend", "--plain"])
    return [l.split()[0] for l in out.splitlines() if l.strip()]


def pending_updates():
    """Count of pending package updates; None if no known package manager."""
    if shutil.which("checkupdates"):
        return len([l for l in run(["checkupdates"], timeout=60).splitlines() if l.strip()])
    if shutil.which("apt"):
        out = run(["apt", "list", "--upgradable"], timeout=60)
        return max(0, len([l for l in out.splitlines() if "/" in l]))
    if shutil.which("dnf"):
        return len([l for l in run(["dnf", "-q", "check-update"], timeout=60).splitlines() if l.strip()])
    return None


def listening_ports():
    ports = set()
    for line in run(["ss", "-tulnH"]).splitlines():
        p = line.split()
        if len(p) >= 5:
            proto, addr = p[0], p[4]
            port = addr.rsplit(":", 1)[-1]
            if port.isdigit():
                ports.add((proto, int(port)))
    return sorted(ports, key=lambda x: (x[1], x[0]))


def ssh_sessions():
    out = run(["ss", "-tnH", "state", "established", "( sport = :22 )"])
    return len([l for l in out.splitlines() if l.strip()])


def git_status(paths):
    rows = []
    for p in paths:
        p = os.path.expanduser(p)
        if not os.path.isdir(os.path.join(p, ".git")) and not os.path.isfile(os.path.join(p, ".git")):
            continue
        dirty = len([l for l in run(["git", "-C", p, "status", "--porcelain"]).splitlines() if l.strip()])
        ahead = run(["git", "-C", p, "rev-list", "--count", "@{u}..HEAD"]).strip()
        behind = run(["git", "-C", p, "rev-list", "--count", "HEAD..@{u}"]).strip()
        branch = run(["git", "-C", p, "rev-parse", "--abbrev-ref", "HEAD"]).strip()
        rows.append((os.path.basename(p.rstrip("/")), branch, dirty,
                     int(ahead) if ahead.isdigit() else 0, int(behind) if behind.isdigit() else 0))
    return rows


def calendar(cmd):
    if not cmd:
        return []
    return [l.rstrip() for l in run(cmd, timeout=20).splitlines() if l.strip()][:8]


def uptime():
    s = float(read("/proc/uptime", "0 0").split()[0])
    d, r = divmod(int(s), 86400)
    h, r = divmod(r, 3600)
    m = r // 60
    return f"{d}d {h:02d}:{m:02d}" if d else f"{h:02d}:{m:02d}"


def top_procs(n=5):
    """Top processes by CPU time delta is expensive; use RSS-sorted snapshot of /proc instead."""
    rows = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/statm") as f:
                rss = int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
            with open(f"/proc/{pid}/comm") as f:
                name = f.read().strip()
        except OSError:
            continue
        rows.append((rss, name))
    rows.sort(reverse=True)
    return rows[:n]


def kernel():
    return os.uname().release


def hostname():
    return socket.gethostname()


def containers():
    if not shutil.which("docker"):
        return None
    out = run(["docker", "ps", "--format", "{{.Names}}"], timeout=5)
    return [l for l in out.splitlines() if l.strip()]


class Procs:
    """Per-process CPU share and RSS, for the starfield. ~300 pids x 2 small
    files per tick; only sampled when a field that needs it is visible."""

    PAGE = os.sysconf("SC_PAGE_SIZE")
    CLK = os.sysconf("SC_CLK_TCK")

    def __init__(self):
        self.prev = {}
        self.at = None
        self.rows = []  # (pid, comm, rss_bytes, cpu_fraction_of_one_core)
        self.top = []
        self.threads = 0

    def sample(self):
        now = time.monotonic()
        dt = (now - self.at) if self.at else None
        cur, rows, threads = {}, [], 0
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                with open(f"/proc/{pid}/stat") as f:
                    st = f.read()
                with open(f"/proc/{pid}/statm") as f:
                    rss = int(f.read().split()[1]) * self.PAGE
            except (OSError, ValueError):
                continue
            if rss == 0:
                continue  # kernel thread
            rp = st.rindex(")")
            comm = st[st.index("(") + 1:rp]
            f = st[rp + 2:].split()
            ticks = int(f[11]) + int(f[12])
            threads += int(f[17])
            cur[pid] = ticks
            cpu = 0.0
            if dt and pid in self.prev:
                cpu = max(0.0, (ticks - self.prev[pid]) / self.CLK / dt)
            rows.append((int(pid), comm, rss, cpu))
        self.prev, self.at, self.rows, self.threads = cur, now, rows, threads
        self.top = sorted(rows, key=lambda r: r[3], reverse=True)[:8]


class Kernel:
    """Kernel counters: context switches, interrupts, forks per second, plus
    file descriptors, sockets and entropy. All from /proc, all cheap."""

    def __init__(self):
        self.prev = None
        self.ctxt = self.intr = self.forks = 0.0
        self.running = self.blocked = 0
        self.fds = self.fds_max = 0
        self.tcp = self.udp = 0
        self.entropy = 0
        self.ctxt_hist = deque([0.0] * HIST, maxlen=HIST)

    def sample(self):
        kv = {}
        for line in read("/proc/stat").splitlines():
            p = line.split()
            if p and p[0] in ("ctxt", "intr", "processes", "procs_running", "procs_blocked"):
                kv[p[0]] = int(p[1])
        now = time.monotonic()
        if self.prev:
            dt = max(now - self.prev[0], 1e-3)
            self.ctxt = (kv.get("ctxt", 0) - self.prev[1]) / dt
            self.intr = (kv.get("intr", 0) - self.prev[2]) / dt
            self.forks = (kv.get("processes", 0) - self.prev[3]) / dt
            self.ctxt_hist.append(self.ctxt)
        self.prev = (now, kv.get("ctxt", 0), kv.get("intr", 0), kv.get("processes", 0))
        self.running, self.blocked = kv.get("procs_running", 0), kv.get("procs_blocked", 0)
        fn = read("/proc/sys/fs/file-nr", "0 0 0").split()
        self.fds, self.fds_max = int(fn[0]), int(fn[2]) if len(fn) > 2 else 0
        self.entropy = int(read("/proc/sys/kernel/random/entropy_avail", "0") or 0)
        for line in read("/proc/net/sockstat").splitlines():
            p = line.split()
            if p and p[0] == "TCP:":
                self.tcp = int(p[2])
            elif p and p[0] == "UDP:":
                self.udp = int(p[2])


def dmi():
    """(vendor, model, chassis) from /sys/class/dmi/id."""
    chassis = {"3": "Desktop", "8": "Portable", "9": "Laptop", "10": "Notebook", "11": "Handheld",
               "13": "All in one", "14": "Sub Notebook", "30": "Tablet", "31": "Convertible", "32": "Detachable"}
    d = "/sys/class/dmi/id/"
    return (read(d + "sys_vendor", "") or "?", read(d + "product_name", "") or read(d + "product_family", "") or "?",
            chassis.get(read(d + "chassis_type", ""), "Machine"))


def cpu_model():
    for line in read("/proc/cpuinfo").splitlines():
        if line.startswith("model name"):
            m = line.split(":", 1)[1].strip()
            return m.replace("(R)", "").replace("(TM)", "").replace("CPU ", "").split("@")[0].strip()
    return os.uname().machine


def cpu_freq_range():
    """(min, max) of the current core frequencies in GHz."""
    vals = []
    for f in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq"):
        v = read(f, "")
        if v.isdigit():
            vals.append(int(v) / 1e6)
    return (min(vals), max(vals)) if vals else (0.0, 0.0)


def ping(host="1.1.1.1"):
    """Round-trip ms to host, or None."""
    out = run(["ping", "-c", "1", "-W", "1", "-n", host], timeout=3)
    for tok in out.split():
        if tok.startswith("time="):
            try:
                return float(tok[5:])
            except ValueError:
                return None
    return None
