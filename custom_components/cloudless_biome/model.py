"""Profiles, devices and biome-wide settings, read from the config entry and its subentries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry

from .astro import EVENT_DATE, EVENTS
from .const import (
    CONF_ACTIVE,
    CONF_BRIGHTNESS,
    CONF_COPY_FROM,
    CONF_DAY_END,
    CONF_DAY_MODE,
    CONF_DAY_START,
    CONF_ENTITY_ID,
    CONF_KIND,
    CONF_MANUAL,
    CONF_MANUAL_MINUTES,
    CONF_MAX_ON,
    CONF_MODE,
    CONF_OFF_OFFSET,
    CONF_OFF_TIME,
    CONF_ON_OFFSET,
    CONF_ON_TIME,
    CONF_ORDER,
    CONF_PROFILES,
    CONF_RAMP,
    CONF_SPANS,
    CONF_START_DATE,
    CONF_START_EVENT,
    CONF_START_OFFSET,
    CONF_TRANSITION,
    DAY_FIXED,
    DAY_MODES,
    DEFAULT_MAX_ON,
    KINDS,
    LEGACY_FIXED,
    MANUAL_MODES,
    MANUAL_NEXT,
    MODE_ALWAYS,
    MODE_WINDOWS,
    OPT_MAX_ON,
    OPT_NATURAL,
    OPT_PRICE,
    OPT_SENSORS,
    REFS,
    SUBENTRY_DEVICE,
    SUBENTRY_PROFILE,
)


def minutes_of(clock: str) -> int:
    """Return the minutes since midnight of HH:MM or HH:MM:SS."""
    parts = str(clock).split(":")
    return (int(parts[0]) * 60 + int(parts[1])) % 1440


def clock_of(minutes: float) -> str:
    """Return HH:MM for minutes since midnight."""
    minutes = round(minutes) % 1440
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def month_day(value: str | None) -> tuple[int, int] | None:
    """Return (month, day) of MM-DD or YYYY-MM-DD, or None."""
    if not value:
        return None
    parts = str(value).split("-")[-2:]
    try:
        month, day = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return None
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return month, day


@dataclass(frozen=True)
class Natural:
    """A biome day that follows the sun at a latitude, kept within limits and centred on a time of day."""

    latitude: float | None = None  # None: where Home Assistant is
    longitude: float | None = None
    min_length: int = 600  # minutes
    max_length: int = 840
    center: int | None = None  # minutes after midnight; None: solar noon at the place
    factor: float = 1.0  # 1 = as nature, 0 = always 12 hours
    invert: bool = False  # move the seasons by half a year, for animals from the other hemisphere


@dataclass(frozen=True)
class Settings:
    """Settings that apply to the whole biome."""

    max_on: Mapping[str, int] = field(default_factory=lambda: dict(DEFAULT_MAX_ON))
    natural: Natural = field(default_factory=Natural)
    sensors: tuple[str, ...] = ()
    price: float | None = None


@dataclass(frozen=True)
class Profile:
    """A season: the times of the biome day and which devices run."""

    id: str
    name: str
    day_start: int
    day_end: int
    start: tuple[int, int] | None = None  # month and day, for EVENT_DATE
    copy_from: str | None = None
    transition: int = 0  # days from the start over which the biome day moves to this profile's times
    event: str = EVENT_DATE
    offset: int = 0  # days before (negative) or after the event
    day_mode: str = DAY_FIXED

    @property
    def day_length(self) -> int:
        """Minutes from the start to the end of the biome day."""
        return (self.day_end - self.day_start) % 1440

    @property
    def dated(self) -> bool:
        """Whether the profile starts by itself on a day of the year."""
        return self.event != EVENT_DATE or self.start is not None


@dataclass(frozen=True)
class Edge:
    """One end of a time window: minutes from the biome day's start or end, or a clock time."""

    ref: str
    value: int


@dataclass(frozen=True)
class Span:
    """A time window. With `every`, the device runs only for `pulse` seconds every `every` minutes in it."""

    on: Edge
    off: Edge
    every: int | None = None
    pulse: int | None = None


DAY_SPAN = Span(Edge("start", 0), Edge("end", 0))


@dataclass(frozen=True)
class Setting:
    """How a device runs in one profile."""

    active: bool = True
    always: bool = False
    spans: tuple[Span, ...] = (DAY_SPAN,)
    brightness: int | None = None
    ramp: int = 0


@dataclass(frozen=True)
class Device:
    """A switch or light that follows the biome day."""

    id: str
    name: str
    entity_id: str
    kind: str = "other"
    manual: str = MANUAL_NEXT
    manual_minutes: int = 60
    settings: Mapping[str, Setting] = field(default_factory=dict)
    order: int = 0
    max_on: int | None = None  # seconds; None: the biome's default for the kind; 0: no limit

    @property
    def domain(self) -> str:
        """Return the domain of the entity."""
        return self.entity_id.split(".", 1)[0]

    def setting(self, profile: Profile, profiles: Mapping[str, Profile]) -> Setting:
        """Return the setting for a profile, following copy_from when the profile is new to the device."""
        seen: set[str] = set()
        current: Profile | None = profile
        while current is not None and current.id not in seen:
            if current.id in self.settings:
                return self.settings[current.id]
            seen.add(current.id)
            current = profiles.get(current.copy_from) if current.copy_from else None
        return next(iter(self.settings.values()), Setting())

    def limit(self, settings: Settings) -> int:
        """Return the longest time in seconds the device may stay on, or 0 for no limit."""
        if self.max_on is not None:
            return max(0, self.max_on)
        return max(0, int(settings.max_on.get(self.kind, 0) or 0))


def device_order(device: Device) -> tuple[int, int, str]:
    """Sort key of devices: the order from the page, then kind and name."""
    return (device.order, KINDS.index(device.kind), device.name.casefold())


def profile_from(subentry_id: str, title: str, data: Mapping[str, Any]) -> Profile:
    """Build a profile from subentry data."""
    event = data.get(CONF_START_EVENT) or EVENT_DATE
    day_mode = data.get(CONF_DAY_MODE) or DAY_FIXED
    return Profile(
        id=subentry_id,
        name=title,
        day_start=minutes_of(data.get(CONF_DAY_START, "08:00")),
        day_end=minutes_of(data.get(CONF_DAY_END, "20:00")),
        start=month_day(data.get(CONF_START_DATE)),
        copy_from=data.get(CONF_COPY_FROM) or None,
        transition=max(0, int(data.get(CONF_TRANSITION) or 0)),
        event=event if event in EVENTS else EVENT_DATE,
        offset=int(data.get(CONF_START_OFFSET) or 0),
        day_mode=day_mode if day_mode in DAY_MODES else DAY_FIXED,
    )


def _edge(data: Any, default: Edge) -> Edge:
    if not isinstance(data, Mapping) or data.get("ref") not in REFS:
        return default
    value = data.get("value", 0)
    if data["ref"] == "clock" and isinstance(value, str):
        value = minutes_of(value)
    return Edge(data["ref"], int(value or 0))


def span_from(data: Mapping[str, Any]) -> Span:
    """Build a time window from stored data."""
    every = data.get("every")
    pulse = data.get("pulse")
    return Span(
        on=_edge(data.get("on"), Edge("start", 0)),
        off=_edge(data.get("off"), Edge("end", 0)),
        every=int(every) if every else None,
        pulse=int(pulse) if pulse and every else None,
    )


def span_data(span: Span) -> dict[str, Any]:
    """Return a time window as stored data."""
    return {
        "on": {"ref": span.on.ref, "value": span.on.value},
        "off": {"ref": span.off.ref, "value": span.off.value},
        "every": span.every,
        "pulse": span.pulse,
    }


def setting_data(setting: Setting) -> dict[str, Any]:
    """Return a device setting as stored data."""
    return {
        CONF_ACTIVE: setting.active,
        CONF_MODE: MODE_ALWAYS if setting.always else MODE_WINDOWS,
        CONF_SPANS: [span_data(s) for s in setting.spans],
        CONF_BRIGHTNESS: setting.brightness,
        CONF_RAMP: setting.ramp,
    }


def setting_from(data: Mapping[str, Any]) -> Setting:
    """Build a device setting from stored data, also from the time before time windows."""
    brightness = data.get(CONF_BRIGHTNESS)
    mode = data.get(CONF_MODE)
    if CONF_SPANS in data:
        spans = tuple(span_from(s) for s in data[CONF_SPANS] or () if isinstance(s, Mapping))
    elif mode == LEGACY_FIXED and data.get(CONF_ON_TIME) and data.get(CONF_OFF_TIME):
        spans = (Span(Edge("clock", minutes_of(data[CONF_ON_TIME])), Edge("clock", minutes_of(data[CONF_OFF_TIME]))),)
    else:
        spans = (Span(Edge("start", int(data.get(CONF_ON_OFFSET, 0))), Edge("end", int(data.get(CONF_OFF_OFFSET, 0)))),)
    return Setting(
        active=bool(data.get(CONF_ACTIVE, True)),
        always=mode == MODE_ALWAYS,
        spans=spans,
        brightness=int(brightness) if brightness not in (None, "") else None,
        ramp=int(data.get(CONF_RAMP, 0) or 0),
    )


def device_from(subentry_id: str, title: str, data: Mapping[str, Any]) -> Device:
    """Build a device from subentry data."""
    kind = data.get(CONF_KIND, "other")
    manual = data.get(CONF_MANUAL, MANUAL_NEXT)
    max_on = data.get(CONF_MAX_ON)
    return Device(
        id=subentry_id,
        name=title,
        entity_id=data[CONF_ENTITY_ID],
        kind=kind if kind in KINDS else "other",
        manual=manual if manual in MANUAL_MODES else MANUAL_NEXT,
        manual_minutes=max(1, int(data.get(CONF_MANUAL_MINUTES, 60))),
        settings={pid: setting_from(s) for pid, s in (data.get(CONF_PROFILES) or {}).items()},
        order=int(data.get(CONF_ORDER, 0) or 0),
        max_on=int(max_on) if max_on is not None else None,
    )


def settings_of(entry: ConfigEntry) -> Settings:
    """Return the biome-wide settings."""
    options = entry.options or {}
    natural = options.get(OPT_NATURAL) or {}
    price = options.get(OPT_PRICE)
    max_on = options.get(OPT_MAX_ON)
    return Settings(
        max_on=dict(DEFAULT_MAX_ON) if max_on is None else {k: int(v or 0) for k, v in max_on.items()},
        natural=Natural(
            latitude=float(natural["latitude"]) if natural.get("latitude") is not None else None,
            longitude=float(natural["longitude"]) if natural.get("longitude") is not None else None,
            min_length=int(natural.get("min_length", 600)),
            max_length=int(natural.get("max_length", 840)),
            center=minutes_of(natural["center"]) if natural.get("center") else None,
            factor=float(natural.get("factor", 1.0)),
            invert=bool(natural.get("invert", False)),
        ),
        sensors=tuple(options.get(OPT_SENSORS) or ()),
        price=float(price) if price not in (None, "") else None,
    )


def profiles_of(entry: ConfigEntry) -> list[Profile]:
    """Return the profiles of a biome: the dated ones roughly in calendar order, then the others as created."""
    rough = {"dst_start": (3, 28), "spring": (3, 20), "summer": (6, 21), "autumn": (9, 22), "dst_end": (10, 28)}
    rough["winter"] = (12, 21)
    items = [
        profile_from(s.subentry_id, s.title, s.data)
        for s in entry.subentries.values()
        if s.subentry_type == SUBENTRY_PROFILE
    ]
    return sorted(items, key=lambda p: (not p.dated, p.start or rough.get(p.event, (0, 0))))


def devices_of(entry: ConfigEntry) -> list[Device]:
    """Return the devices of a biome in the order set on the page; without one, by kind and name."""
    items = [
        device_from(s.subentry_id, s.title, s.data)
        for s in entry.subentries.values()
        if s.subentry_type == SUBENTRY_DEVICE and s.data.get(CONF_ENTITY_ID)
    ]
    return sorted(items, key=device_order)
