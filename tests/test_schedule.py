"""The plan: profiles by date and event, the biome day, time windows, pulses, ramps and the change of clocks."""

from __future__ import annotations

from datetime import date, timedelta

from custom_components.cloudless_biome.astro import _dst_dates, natural_day_length, season_date, solar_noon
from custom_components.cloudless_biome.model import Device, Edge, Natural, Profile, Setting, Span
from custom_components.cloudless_biome.schedule import Plan

from .conftest import TZ, local

WINTER = Profile("winter", "Winter", 9 * 60, 19 * 60, (11, 1))
SUMMER = Profile("summer", "Sommer", 8 * 60, 20 * 60, (4, 1))
PROFILES = [SUMMER, WINTER]


def day(on: int = 0, off: int = 0) -> Span:
    """A window with the biome day, shifted by offsets."""
    return Span(Edge("start", on), Edge("end", off))


def clock(on: str, off: str, every: int | None = None, pulse: int | None = None) -> Span:
    def minutes(value: str) -> int:
        h, m = value.split(":")
        return int(h) * 60 + int(m)

    return Span(Edge("clock", minutes(on)), Edge("clock", minutes(off)), every, pulse)


def lamp(**settings: Setting) -> Device:
    return Device("d", "Lampe", "switch.lamp", settings=settings)


def test_profile_by_date_across_new_year() -> None:
    plan = Plan(PROFILES, None, TZ)
    assert plan.auto_profile(date(2026, 11, 17)) is WINTER
    assert plan.auto_profile(date(2027, 1, 10)) is WINTER
    assert plan.auto_profile(date(2026, 4, 1)) is SUMMER
    assert plan.auto_profile(date(2026, 3, 31)) is WINTER
    assert plan.next_season_change(date(2026, 11, 17)) == date(2027, 4, 1)


def test_manual_profile_until_next_season() -> None:
    plan = Plan(PROFILES, {"profile": "summer", "until": "2027-04-01"}, TZ)
    assert plan.profile(date(2026, 12, 1)) is SUMMER
    assert plan.profile(date(2027, 4, 1)) is SUMMER
    plan = Plan(PROFILES, {"profile": "summer", "until": "2026-12-01"}, TZ)
    assert plan.profile(date(2026, 12, 1)) is WINTER


def test_without_dates_the_first_profile_applies() -> None:
    a = Profile("a", "A", 480, 1200)
    b = Profile("b", "B", 600, 1100)
    assert Plan([a, b], None, TZ).profile(date(2026, 6, 1)) is a
    assert Plan([a, b], {"profile": "b", "until": None}, TZ).profile(date(2026, 6, 1)) is b


def test_events_clock_change_and_seasons() -> None:
    assert _dst_dates(2027, TZ) == (date(2027, 3, 28), date(2027, 10, 31))
    assert season_date("spring", 2027, TZ, 52.5) == date(2027, 3, 20)
    assert season_date("summer", 2027, TZ, 52.5) == date(2027, 6, 21)
    assert season_date("winter", 2026, TZ, 52.5) == date(2026, 12, 21)
    assert season_date("spring", 2027, TZ, -33.9) == date(2027, 9, 23)  # south of the equator
    winter = Profile("w", "Winter", 540, 1140, None, event="dst_end", offset=-7)
    summer = Profile("s", "Sommer", 480, 1200, None, event="dst_start")
    plan = Plan([summer, winter], None, TZ)
    assert plan.auto_profile(date(2027, 10, 23)) is summer
    assert plan.auto_profile(date(2027, 10, 24)) is winter
    assert plan.auto_profile(date(2028, 2, 1)) is winter
    assert plan.next_season_change(date(2027, 11, 1)) == date(2028, 3, 26)


def test_offsets_and_inactive() -> None:
    device = lamp(winter=Setting(spans=(day(15, -15),)), summer=Setting(active=False))
    plan = Plan(PROFILES, None, TZ)
    assert not plan.is_on(device, local(2026, 11, 17, 9, 14))
    assert plan.is_on(device, local(2026, 11, 17, 9, 15))
    assert plan.is_on(device, local(2026, 11, 17, 18, 44))
    assert not plan.is_on(device, local(2026, 11, 17, 18, 45))
    assert plan.next_change(device, local(2026, 11, 17, 12)) == (local(2026, 11, 17, 18, 45), False)
    assert plan.next_change(device, local(2026, 11, 17, 20)) == (local(2026, 11, 18, 9, 15), True)
    assert not plan.is_on(device, local(2026, 6, 1, 12))
    assert plan.next_change(device, local(2026, 6, 1, 12)) is None


def test_several_windows_and_anchors() -> None:
    """Morning and evening light: 30 minutes from the day's start, and the last hour before its end."""
    spans = (Span(Edge("start", 0), Edge("start", 30)), Span(Edge("end", -60), Edge("end", 0)))
    device = lamp(winter=Setting(spans=spans))
    plan = Plan(PROFILES, None, TZ)
    assert plan.is_on(device, local(2026, 11, 17, 9, 10))
    assert not plan.is_on(device, local(2026, 11, 17, 12))
    assert plan.is_on(device, local(2026, 11, 17, 18, 30))
    assert plan.next_change(device, local(2026, 11, 17, 12)) == (local(2026, 11, 17, 18), True)
    night = lamp(winter=Setting(spans=(Span(Edge("clock", 22 * 60), Edge("start", 0)),)))
    assert plan.is_on(night, local(2026, 11, 18, 3))
    assert not plan.is_on(night, local(2026, 11, 18, 9))


def test_pulses() -> None:
    """08:00-20:00 every 15 minutes for 60 seconds; 10:00-18:00 every hour for 20 minutes."""
    fogger = lamp(winter=Setting(spans=(clock("08:00", "20:00", 15, 60),)))
    fan = lamp(winter=Setting(spans=(clock("10:00", "18:00", 60, 20 * 60),)))
    plan = Plan(PROFILES, None, TZ)
    start = local(2026, 11, 17, 8, 15)
    assert plan.is_on(fogger, start + timedelta(seconds=59))
    assert not plan.is_on(fogger, start + timedelta(seconds=60))
    assert plan.next_change(fogger, start + timedelta(seconds=10)) == (start + timedelta(seconds=60), False)
    assert plan.next_change(fogger, start + timedelta(seconds=70)) == (local(2026, 11, 17, 8, 30), True)
    assert not plan.is_on(fogger, local(2026, 11, 17, 20) + timedelta(seconds=30))
    assert plan.is_on(fan, local(2026, 11, 17, 11, 19))
    assert not plan.is_on(fan, local(2026, 11, 17, 11, 20))
    assert not plan.is_on(fan, local(2026, 11, 17, 18, 5))


def test_day_across_midnight() -> None:
    night = Profile("n", "Nacht", 20 * 60, 6 * 60)
    device = lamp(n=Setting())
    plan = Plan([night], None, TZ)
    assert plan.is_on(device, local(2026, 11, 17, 23))
    assert plan.is_on(device, local(2026, 11, 18, 5, 59))
    assert not plan.is_on(device, local(2026, 11, 18, 6))
    assert plan.is_day(local(2026, 11, 18, 2))


def test_new_profile_copies_settings() -> None:
    spring = Profile("spring", "Frühling", 8 * 60, 19 * 60, None, copy_from="winter")
    device = lamp(winter=Setting(spans=(day(30, 0),)))
    assert device.setting(spring, {p.id: p for p in [*PROFILES, spring]}).spans[0].on.value == 30


def test_ramp() -> None:
    device = lamp(winter=Setting(brightness=80, ramp=30))
    plan = Plan(PROFILES, None, TZ)
    assert plan.brightness(device, local(2026, 11, 17, 9, 15)) == 40
    assert plan.brightness(device, local(2026, 11, 17, 12)) == 80
    assert plan.brightness(device, local(2026, 11, 17, 18, 45)) == 40
    assert plan.ramping(device, local(2026, 11, 17, 9, 15))
    assert not plan.ramping(device, local(2026, 11, 17, 12))


def test_switch_to_winter_time_keeps_wall_clock() -> None:
    device = lamp(summer=Setting())
    plan = Plan(PROFILES, None, TZ)
    assert plan.next_change(device, local(2026, 10, 25, 12)) == (local(2026, 10, 25, 20), False)
    assert plan.is_on(device, local(2026, 10, 25, 8))


def test_soft_change_of_season() -> None:
    """Summer starts on 1 Apr with 14 days of transition: 15 steps from 09:00-19:00 to 08:00-20:00."""
    summer = Profile("summer", "Sommer", 8 * 60, 20 * 60, (4, 1), transition=14)
    plan = Plan([summer, WINTER], None, TZ)
    assert plan.effective(date(2026, 3, 31)) is WINTER
    first = plan.effective(date(2026, 4, 1))
    assert (first.id, first.day_start, first.day_end) == ("summer", 536, 1144)
    change = plan.transition(date(2026, 4, 1))
    assert (change.previous.id, change.day, change.days) == ("winter", 1, 14)
    middle = plan.effective(date(2026, 4, 8))
    assert (middle.day_start, middle.day_end) == (508, 1172)
    assert plan.effective(date(2026, 4, 15)) is summer
    device = lamp(summer=Setting(), winter=Setting())
    assert plan.is_on(device, local(2026, 4, 1, 8, 56))
    assert not plan.is_on(device, local(2026, 4, 1, 8, 55))
    manual = Plan([summer, WINTER], {"profile": "summer", "until": None}, TZ)
    assert manual.effective(date(2026, 4, 1)) is summer


def test_soft_change_across_midnight_and_new_year() -> None:
    late = Profile("late", "Spät", 23 * 60, 5 * 60, (1, 1), transition=2)
    early = Profile("early", "Früh", 1 * 60, 7 * 60, (7, 1))
    plan = Plan([late, early], None, TZ)
    step = plan.effective(date(2027, 1, 1))
    assert (step.day_start, step.day_end) == (60 - 40, (60 - 40 + 360) % 1440)


def test_always_and_clock_times_ignore_the_biome_day() -> None:
    summer = Profile("summer", "Sommer", 8 * 60, 20 * 60, (4, 1), transition=14)
    plan = Plan([summer, WINTER], None, TZ)
    mat = lamp(winter=Setting(always=True), summer=Setting(always=True))
    fogger = lamp(winter=Setting(spans=(clock("07:00", "07:05"),)), summer=Setting(active=False))
    assert plan.is_on(mat, local(2026, 11, 17, 3))
    assert plan.is_on(mat, local(2026, 11, 17, 23, 59))
    assert plan.next_change(mat, local(2026, 11, 17, 12)) is None
    assert plan.is_on(mat, local(2026, 4, 3, 2))
    assert plan.is_on(fogger, local(2026, 11, 17, 7, 2))
    assert not plan.is_on(fogger, local(2026, 11, 17, 7, 5))
    assert plan.next_change(fogger, local(2026, 11, 17, 12)) == (local(2026, 11, 18, 7), True)
    overnight = lamp(winter=Setting(spans=(clock("22:00", "02:00"),)))
    assert plan.is_on(overnight, local(2026, 11, 18, 1))


def test_natural_day_far_away() -> None:
    """A day as in central Australia, centred on 13:00 and kept between 10 and 14 hours."""
    assert 420 < natural_day_length(date(2026, 12, 21), 52.5) < 480  # Berlin in winter: about 7.6 h
    natural = Profile("n", "Natürlich", 0, 0, day_mode="natural")
    plan = Plan([natural], None, TZ, natural=Natural(latitude=-24, min_length=600, max_length=840, center=780))
    december = plan.effective(date(2026, 12, 21))
    june = plan.effective(date(2026, 6, 21))
    assert december.day_length > june.day_length
    assert abs((december.day_start + december.day_length / 2) - 780) <= 1
    assert 600 <= june.day_length <= 840
    inverted = Plan([natural], None, TZ, natural=Natural(latitude=-24, center=780, invert=True))
    assert inverted.effective(date(2026, 6, 21)).day_length > inverted.effective(date(2026, 12, 21)).day_length


def test_natural_day_here_with_the_real_sun() -> None:
    """Berlin: the day sits around the sun's highest point and is stretched to at least 10 hours in winter."""
    assert 12 * 60 - 5 < solar_noon(date(2026, 12, 21), 13.4, TZ) < 12 * 60 + 15
    assert 13 * 60 + 5 < solar_noon(date(2026, 6, 21), 13.4, TZ) < 13 * 60 + 20  # summer time
    natural = Profile("n", "Natürlich", 0, 0, day_mode="natural")
    plan = Plan([natural], None, TZ, 52.5, Natural(min_length=600, max_length=840), 13.4)
    winter = plan.effective(date(2026, 12, 21))
    summer = plan.effective(date(2026, 6, 21))
    assert winter.day_length == 600
    assert 7 * 60 - 5 < winter.day_start < 7 * 60 + 15
    assert summer.day_length == 840
    assert 6 * 60 + 5 < summer.day_start < 6 * 60 + 20
    spring = plan.effective(date(2026, 4, 1))
    assert 600 < spring.day_length < 840  # in between, as nature has it


def test_the_repeated_hour_when_summer_time_ends() -> None:
    """25 Oct 2026: 02:00-03:00 comes twice. A window that ends at 02:30 stays off in the second pass."""
    from datetime import UTC, datetime

    night = lamp(winter=Setting(spans=(clock("01:00", "02:30"),)))
    pulses = lamp(winter=Setting(spans=(clock("00:00", "06:00", 30, 60),)))
    plan = Plan([WINTER], None, TZ)
    first = datetime(2026, 10, 25, 0, 10, tzinfo=UTC)  # 02:10 summer time
    second = datetime(2026, 10, 25, 1, 10, tzinfo=UTC)  # 02:10 winter time, after 02:30 summer time
    assert plan.is_on(night, first)
    assert not plan.is_on(night, second)
    for now in (first, second, datetime(2026, 10, 25, 0, 40, tzinfo=UTC)):
        change = plan.next_change(pulses, now)
        assert change is not None and change[0] > now
        moment = plan.next_moment(pulses, now)
        assert moment is not None and moment.timestamp() > now.timestamp()
