"""Sunrise, sunset and solar elevation (NOAA approximation, good to a minute or two)."""

import math
from datetime import datetime, timedelta, timezone


def _julian_day(dt_utc):
    return dt_utc.timestamp() / 86400.0 + 2440587.5


def _solar(jd):
    t = (jd - 2451545.0) / 36525.0
    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    mr = math.radians(m)
    c = (math.sin(mr) * (1.914602 - t * (0.004817 + 0.000014 * t)) +
         math.sin(2 * mr) * (0.019993 - 0.000101 * t) + math.sin(3 * mr) * 0.000289)
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    eps0 = 23 + (26 + ((21.448 - t * (46.815 + t * (0.00059 - t * 0.001813)))) / 60) / 60
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))
    decl = math.degrees(math.asin(math.sin(math.radians(eps)) * math.sin(math.radians(app_long))))
    y = math.tan(math.radians(eps / 2)) ** 2
    l0r, mr = math.radians(l0), math.radians(m)
    eqt = 4 * math.degrees(y * math.sin(2 * l0r) - 2 * e * math.sin(mr) + 4 * e * y * math.sin(mr) * math.cos(2 * l0r)
                           - 0.5 * y * y * math.sin(4 * l0r) - 1.25 * e * e * math.sin(2 * mr))
    return decl, eqt  # degrees, minutes


def elevation(lat, lon, when=None):
    """Solar elevation in degrees at `when` (aware datetime, default now)."""
    when = when or datetime.now(timezone.utc)
    jd = _julian_day(when.astimezone(timezone.utc))
    decl, eqt = _solar(jd)
    minutes = when.astimezone(timezone.utc).hour * 60 + when.astimezone(timezone.utc).minute + when.second / 60
    tst = (minutes + eqt + 4 * lon) % 1440
    ha = tst / 4 - 180
    latr, dr = math.radians(lat), math.radians(decl)
    cosz = math.sin(latr) * math.sin(dr) + math.cos(latr) * math.cos(dr) * math.cos(math.radians(ha))
    return 90 - math.degrees(math.acos(max(-1, min(1, cosz))))


def sun_times(lat, lon, day=None):
    """(sunrise, sunset) as aware local datetimes for `day` (local date), or (None, None)
    for polar day/night."""
    local_tz = datetime.now().astimezone().tzinfo
    day = day or datetime.now(local_tz).date()
    noon_utc = datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc) - timedelta(hours=lon / 15)
    decl, eqt = _solar(_julian_day(noon_utc))
    latr, dr = math.radians(lat), math.radians(decl)
    cos_ha = (math.cos(math.radians(90.833)) / (math.cos(latr) * math.cos(dr)) - math.tan(latr) * math.tan(dr))
    if cos_ha > 1 or cos_ha < -1:
        return None, None
    ha = math.degrees(math.acos(cos_ha))
    midnight = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    rise = midnight + timedelta(minutes=720 - 4 * (lon + ha) - eqt)
    sett = midnight + timedelta(minutes=720 - 4 * (lon - ha) - eqt)
    return rise.astimezone(local_tz), sett.astimezone(local_tz)


def subsolar(when=None):
    """(latitude, longitude) in degrees of the point where the sun is at zenith."""
    when = (when or datetime.now(timezone.utc)).astimezone(timezone.utc)
    decl, eqt = _solar(_julian_day(when))
    minutes = when.hour * 60 + when.minute + when.second / 60
    lon = 180 - (minutes + eqt) / 4  # hour angle at Greenwich, negated
    return decl, (lon + 180) % 360 - 180
