"""The plan: which profile applies on a day, the biome day, and when each device is on. No Home Assistant state here."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from typing import Any

from .astro import event_date, natural_day_length, solar_noon
from .const import DAY_NATURAL
from .model import Device, Edge, Natural, Profile, Setting, Span

DAY = 1440


def at(day: date, minutes: float, tz: tzinfo) -> datetime:
    """Return the moment, in UTC, of the wall-clock time `minutes` after midnight of `day`.

    In UTC, because Python compares two times of the same zone by their wall clock and ignores `fold`:
    in the hour that repeats when summer time ends, 02:10 of the second pass would count as before 02:30
    of the first. Minutes may be negative or exceed a day.
    """
    whole = int(minutes // 1)
    base = day + timedelta(days=whole // DAY)
    rest = whole % DAY
    result = datetime.combine(base, time(rest // 60, rest % 60), tz)
    return (result + timedelta(seconds=round((minutes - whole) * 60))).astimezone(UTC)


@dataclass(frozen=True)
class Transition:
    """The biome day moves from one profile's times to the next over some days."""

    previous: Profile
    day: int  # 1 on the start day
    days: int
    fraction: float


@dataclass(frozen=True)
class Window:
    """A device is on from start to end."""

    start: datetime
    end: datetime
    setting: Setting
    span: Span | None = None
    pulse: bool = False


class Plan:
    """The plan of a biome for its profiles and an optional manual choice of profile."""

    def __init__(
        self,
        profiles: list[Profile],
        manual: Mapping[str, Any] | None,
        tz: tzinfo,
        latitude: float = 50.0,
        natural: Natural | None = None,
        longitude: float = 10.0,
    ) -> None:
        """Initialize."""
        self.profiles = profiles
        self.by_id = {p.id: p for p in profiles}
        self.manual = manual
        self.tz = tz
        self.latitude = latitude
        self.longitude = longitude
        self.natural = natural or Natural()
        self._starts: dict[tuple[str, int], date | None] = {}

    # -- which profile ----------------------------------------------------------------------------------

    @property
    def automatic(self) -> bool:
        """Whether profiles change by themselves during the year."""
        return any(p.dated for p in self.profiles)

    def start_in(self, profile: Profile, year: int) -> date | None:
        """Return the day the profile starts in `year`, with its offset in days."""
        key = (profile.id, year)
        if key not in self._starts:
            day = event_date(profile.event, year, self.tz, self.latitude, profile.start)
            self._starts[key] = day + timedelta(days=profile.offset) if day else None
        return self._starts[key]

    def last_start(self, profile: Profile, day: date) -> date | None:
        """Return the last start of the profile on or before `day`."""
        years = (day.year + 1, day.year, day.year - 1)
        found = [d for y in years if (d := self.start_in(profile, y)) and d <= day]
        return max(found) if found else None

    def next_start(self, profile: Profile, day: date) -> date | None:
        """Return the next start of the profile after `day`."""
        years = (day.year - 1, day.year, day.year + 1, day.year + 2)
        found = [d for y in years if (d := self.start_in(profile, y)) and d > day]
        return min(found) if found else None

    def auto_profile(self, day: date) -> Profile | None:
        """Return the dated profile that started last before or on `day`."""
        best: tuple[date, Profile] | None = None
        for profile in self.profiles:
            if profile.dated and (start := self.last_start(profile, day)) and (best is None or start > best[0]):
                best = (start, profile)
        return best[1] if best else None

    def next_season_change(self, day: date) -> date | None:
        """Return the next day after `day` on which a profile starts."""
        found = [d for p in self.profiles if p.dated and (d := self.next_start(p, day))]
        return min(found) if found else None

    def manual_applies(self, day: date) -> bool:
        """Whether the manual choice of profile applies on `day`."""
        if not self.manual or self.manual.get("profile") not in self.by_id:
            return False
        until = self.manual.get("until")
        return until is None or day < date.fromisoformat(until)

    def profile(self, day: date) -> Profile | None:
        """Return the profile that applies on `day`."""
        if not self.profiles:
            return None
        if self.manual_applies(day) and self.manual:
            return self.by_id[self.manual["profile"]]
        return self.auto_profile(day) or self.profiles[0]

    # -- the biome day ----------------------------------------------------------------------------------

    def day_times(self, profile: Profile, day: date) -> tuple[float, float]:
        """Return the start and length in minutes of the profile's biome day on `day`."""
        if profile.day_mode != DAY_NATURAL:
            return profile.day_start, profile.day_length
        n = self.natural
        latitude = self.latitude if n.latitude is None else n.latitude
        longitude = self.longitude if n.longitude is None else n.longitude
        sun_day = day + timedelta(days=182) if n.invert else day
        length = 720 + (natural_day_length(sun_day, latitude) - 720) * n.factor
        length = max(n.min_length, min(n.max_length, length))
        length = max(0.0, min(DAY - 1, length))
        # The middle of the day: a set time, or the sun's highest point at the place, in local time.
        center = n.center if n.center is not None else solar_noon(day, longitude, self.tz)
        return center - length / 2, length

    def transition(self, day: date) -> Transition | None:
        """Return the soft change of season under way on `day`, if any. A profile chosen by hand applies at once."""
        profile = self.profile(day)
        if profile is None or profile.transition <= 0 or not profile.dated or self.manual_applies(day):
            return None
        start = self.last_start(profile, day)
        if start is None or (day - start).days >= profile.transition:
            return None
        previous = self.auto_profile(start - timedelta(days=1))
        if previous is None or previous.id == profile.id:
            return None
        step = (day - start).days + 1
        return Transition(previous, step, profile.transition, step / (profile.transition + 1))

    def effective(self, day: date) -> Profile | None:
        """Return the profile of `day` with the times its biome day has on that day."""
        profile = self.profile(day)
        if profile is None:
            return None
        start, length = self.day_times(profile, day)
        if (change := self.transition(day)) is not None:
            p_start, p_length = self.day_times(change.previous, day)
            delta = ((start - p_start + 720) % DAY) - 720
            start = p_start + delta * change.fraction
            length = p_length + (length - p_length) * change.fraction
        start = round(start) % DAY
        end = (start + round(length)) % DAY
        if start == profile.day_start and end == profile.day_end:
            return profile
        return replace(profile, day_start=start, day_end=end)

    def day_window(self, day: date) -> tuple[datetime, datetime] | None:
        """Return the biome day that starts on `day`."""
        profile = self.effective(day)
        if profile is None or profile.day_length == 0:
            return None
        return at(day, profile.day_start, self.tz), at(day, profile.day_start + profile.day_length, self.tz)

    def day_windows(self, first: date, last: date) -> list[tuple[datetime, datetime]]:
        """Return the biome days that start between `first` and `last`."""
        out = []
        day = first
        while day <= last:
            if (item := self.day_window(day)) is not None:
                out.append(item)
            day += timedelta(days=1)
        return out

    def is_day(self, now: datetime) -> bool:
        """Whether it is day in the biome."""
        today = now.astimezone(self.tz).date()
        now = now.astimezone(UTC)
        return any(a <= now < b for a, b in self.day_windows(today - timedelta(days=1), today))

    # -- devices ----------------------------------------------------------------------------------------

    @staticmethod
    def span_minutes(span: Span, profile: Profile) -> tuple[int, int] | None:
        """Return a window's start and end in minutes from midnight; the end may reach into the next day."""

        def edge(e: Edge) -> int:
            if e.ref == "clock":
                return e.value
            if e.ref == "start":
                return profile.day_start + e.value
            return profile.day_start + profile.day_length + e.value

        clock_on, clock_off = span.on.ref == "clock", span.off.ref == "clock"
        if not (clock_on and clock_off) and profile.day_length == 0:
            return None
        on, off = edge(span.on), edge(span.off)
        if clock_on and not clock_off and on > off:
            on -= DAY  # a clock time before midnight, the day's end after it
        if off <= on:
            if not (clock_on or clock_off):
                return None
            off += DAY
        if off - on > DAY:
            return None
        return on, off

    def window(self, device: Device, day: date) -> list[Window]:
        """Return when the device is on during the biome day that starts on `day`."""
        profile = self.effective(day)
        if profile is None:
            return []
        setting = device.setting(profile, self.by_id)
        if not setting.active:
            return []
        if setting.always:
            return [Window(at(day, 0, self.tz), at(day, DAY, self.tz), setting)]
        out = []
        for span in setting.spans:
            minutes = self.span_minutes(span, profile)
            if minutes is None:
                continue
            on, off = minutes
            if span.every and span.pulse:
                t: float = on
                while t < off:
                    end = min(t + span.pulse / 60, off)
                    out.append(Window(at(day, t, self.tz), at(day, end, self.tz), setting, span, pulse=True))
                    t += span.every
            else:
                out.append(Window(at(day, on, self.tz), at(day, off, self.tz), setting, span))
        return out

    def windows(self, device: Device, first: date, last: date) -> list[Window]:
        """Return the device's windows of the biome days that start between `first` and `last`."""
        out: list[Window] = []
        day = first
        while day <= last:
            out += self.window(device, day)
            day += timedelta(days=1)
        return out

    def _around(self, device: Device, now: datetime) -> list[Window]:
        today = now.astimezone(self.tz).date()
        now = now.astimezone(UTC)
        return self.windows(device, today - timedelta(days=1), today + timedelta(days=2))

    @staticmethod
    def _on(windows: list[Window], moment: datetime) -> bool:
        return any(w.start <= moment < w.end for w in windows)

    def is_on(self, device: Device, now: datetime) -> bool:
        """Whether the plan has the device on."""
        return self._on(self._around(device, now), now.astimezone(UTC))

    def brightness(self, device: Device, now: datetime) -> int | None:
        """Return the brightness in percent the plan wants, with the dimming ramps, or None."""
        now = now.astimezone(UTC)
        for w in self._around(device, now):
            if not (w.start <= now < w.end) or w.setting.brightness is None:
                continue
            target = w.setting.brightness
            if w.setting.ramp <= 0 or w.pulse or w.setting.always:
                return target
            ramp = timedelta(minutes=w.setting.ramp)
            factor = min(1.0, (now - w.start) / ramp, (w.end - now) / ramp)
            return max(1, round(target * factor))
        return None

    def ramping(self, device: Device, now: datetime) -> bool:
        """Whether the device is dimming up or down right now."""
        now = now.astimezone(UTC)
        for w in self._around(device, now):
            if w.setting.brightness is None or w.setting.ramp <= 0 or w.pulse or w.setting.always:
                continue
            if not (w.start <= now < w.end):
                continue
            ramp = timedelta(minutes=w.setting.ramp)
            return now - w.start < ramp or w.end - now < ramp
        return False

    def next_moment(self, device: Device, now: datetime) -> datetime | None:
        """Return when something changes for the device next: switching, or brightness while dimming."""
        now = now.astimezone(UTC)
        if self.ramping(device, now):
            return now + timedelta(minutes=1)
        times = []
        for w in self._around(device, now):
            times += [w.start, w.end]
            if w.setting.brightness is not None and w.setting.ramp > 0 and not w.pulse:
                times.append(w.end - timedelta(minutes=w.setting.ramp))
        future = [t for t in times if t > now]
        return min(future) if future else None

    def next_change(self, device: Device, now: datetime) -> tuple[datetime, bool] | None:
        """Return when the plan switches the device next, and to what."""
        now = now.astimezone(UTC)
        windows = self._around(device, now)
        current = self._on(windows, now)
        # Beyond the days looked at, an end is only the edge of what was computed.
        horizon = at(now.astimezone(self.tz).date() + timedelta(days=3), 0, self.tz)
        times = sorted({t for w in windows for t in (w.start, w.end) if now < t < horizon})
        for moment in times:
            if self._on(windows, moment) != current:
                return moment, not current
        return None
