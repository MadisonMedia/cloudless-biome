"""Dates of the year a profile can start on, and the length of a natural day. No Home Assistant state in here."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, tzinfo
from functools import lru_cache
import math

EVENT_DATE = "date"
EVENT_DST_START = "dst_start"
EVENT_DST_END = "dst_end"
EVENT_SPRING = "spring"
EVENT_SUMMER = "summer"
EVENT_AUTUMN = "autumn"
EVENT_WINTER = "winter"
EVENTS = (EVENT_DATE, EVENT_DST_START, EVENT_DST_END, EVENT_SPRING, EVENT_SUMMER, EVENT_AUTUMN, EVENT_WINTER)

# Mean equinoxes and solstices (Meeus, Astronomical Algorithms, table 27.b), as Julian ephemeris days.
# Without the periodic terms they are off by well under a day, which is all a season needs.
_SEASON_TERMS = {
    "march": (2451623.80984, 365242.37404, 0.05169, -0.00411, -0.00057),
    "june": (2451716.56767, 365241.62603, 0.00325, 0.00888, -0.00030),
    "september": (2451810.21715, 365242.01767, -0.11575, 0.00337, 0.00078),
    "december": (2451900.05952, 365242.74049, -0.06223, -0.00823, 0.00032),
}
_NORTH = {EVENT_SPRING: "march", EVENT_SUMMER: "june", EVENT_AUTUMN: "september", EVENT_WINTER: "december"}
_SOUTH = {EVENT_SPRING: "september", EVENT_SUMMER: "december", EVENT_AUTUMN: "march", EVENT_WINTER: "june"}


def _jde_to_datetime(jde: float) -> datetime:
    return datetime(2000, 1, 1, 12, tzinfo=UTC) + timedelta(days=jde - 2451545.0)


def season_date(event: str, year: int, tz: tzinfo, latitude: float) -> date:
    """Return the local date of an astronomical season's start. South of the equator the names swap."""
    which = (_SOUTH if latitude < 0 else _NORTH)[event]
    a, b, c, d, e = _SEASON_TERMS[which]
    y = (year - 2000) / 1000
    jde = a + b * y + c * y**2 + d * y**3 + e * y**4
    return _jde_to_datetime(jde).astimezone(tz).date()


@lru_cache(maxsize=64)
def _dst_dates(year: int, tz: tzinfo) -> tuple[date | None, date | None]:
    """Return the days daylight saving time starts and ends in `year`, or None where there is none."""
    start = end = None
    previous = datetime(year, 1, 1, 12, tzinfo=tz).dst() or timedelta(0)
    day = date(year, 1, 2)
    while day.year == year:
        current = datetime(day.year, day.month, day.day, 12, tzinfo=tz).dst() or timedelta(0)
        if current and not previous and start is None:
            start = day
        elif previous and not current and end is None:
            end = day
        previous = current
        day += timedelta(days=1)
    return start, end


def event_date(event: str, year: int, tz: tzinfo, latitude: float, month_day: tuple[int, int] | None) -> date | None:
    """Return the day in `year` on which an event falls, or None if it does not exist there."""
    if event == EVENT_DATE:
        if month_day is None:
            return None
        month, day = month_day
        try:
            return date(year, month, day)
        except ValueError:  # 29 Feb in a common year
            return date(year, month, 28)
    if event in (EVENT_DST_START, EVENT_DST_END):
        start, end = _dst_dates(year, tz)
        return start if event == EVENT_DST_START else end
    if event in _NORTH:
        return season_date(event, year, tz, latitude)
    return None


def natural_day_length(day: date, latitude: float) -> float:
    """Return the minutes from sunrise to sunset at a latitude, with the usual allowance for refraction."""
    n = day.timetuple().tm_yday
    declination = math.radians(23.44) * math.sin(2 * math.pi * (284 + n) / 365)
    phi = math.radians(max(-89.9, min(89.9, latitude)))
    cos_omega = (math.sin(math.radians(-0.833)) - math.sin(phi) * math.sin(declination)) / (
        math.cos(phi) * math.cos(declination)
    )
    if cos_omega <= -1:
        return 1440.0  # midnight sun
    if cos_omega >= 1:
        return 0.0  # polar night
    return 2 * math.degrees(math.acos(cos_omega)) / 15 * 60


def solar_noon(day: date, longitude: float, tz: tzinfo) -> float:
    """Return the local time of solar noon on `day` at a longitude, in minutes after midnight."""
    n = day.timetuple().tm_yday
    b = 2 * math.pi * (n - 81) / 364
    equation_of_time = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)  # minutes
    noon_utc = datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(
        minutes=720 - 4 * longitude - equation_of_time
    )
    local = noon_utc.astimezone(tz)
    return local.hour * 60 + local.minute + local.second / 60
