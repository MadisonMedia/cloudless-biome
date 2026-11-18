"""A running biome: compares what the plan wants with what the devices do, and switches."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from datetime import datetime, time, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import CALLBACK_TYPE, Context, Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CHECK_INTERVAL_MINUTES,
    DOMAIN,
    LOG_SIZE,
    MANUAL_DURATION,
    MANUAL_NEVER,
    MAX_ATTEMPTS,
    PULSE_LOG_SIZE,
    SAVE_DELAY,
    STORAGE_VERSION,
)
from .edit import config_of, fingerprint
from .model import Device, Profile, clock_of, devices_of, profiles_of, settings_of, span_data
from .schedule import Plan

_LOGGER = logging.getLogger(__name__)

SWITCHABLE = (STATE_ON, STATE_OFF)
BRIGHTNESS_TOLERANCE = 3
# Time a device gets to report its new state before Biome sends the same command again. Switching off
# is retried sooner: a pump or fogger that keeps running does harm.
SETTLE_ON = timedelta(seconds=30)
SETTLE_OFF = timedelta(seconds=5)
RETRY_ON = timedelta(minutes=1)
RETRY_OFF = timedelta(seconds=5)


def _local(moment: datetime) -> str:
    """Return a moment as local time, the way people read it in the log and on the page."""
    return dt_util.as_local(moment).isoformat(timespec="seconds")


class Biome:
    """One biome with its profiles and devices."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, device_id: str | None = None) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self.device_id = device_id
        self.profiles: list[Profile] = profiles_of(entry)
        self.devices: list[Device] = devices_of(entry)
        self.settings = settings_of(entry)
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.paused = False
        self.dry_run = True
        self.manual: dict[str, Any] | None = None
        self.notes = ""
        self.overrides: dict[str, dict[str, Any]] = {}
        self.log_items: deque[dict[str, Any]] = deque(maxlen=LOG_SIZE)
        self.pulse_items: deque[dict[str, Any]] = deque(maxlen=PULSE_LOG_SIZE)
        self.problems: dict[str, str] = {}
        self._attempts: dict[str, int] = {}
        self._would: dict[str, str] = {}
        self._sent: dict[str, tuple[datetime, str]] = {}
        self._cutoff: dict[str, datetime] = {}
        # The on-phase (its last_changed) a device was already cut off in, so one phase is cut only once.
        self._cut_phase: dict[str, datetime] = {}
        self._plan: tuple[Any, Plan] | None = None
        self._ours: deque[str] = deque(maxlen=100)
        self._locks: dict[str, asyncio.Lock] = {}
        self._listeners: list[CALLBACK_TYPE] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._timer: CALLBACK_TYPE | None = None
        self._stop_listeners: list[CALLBACK_TYPE] = []
        self.fingerprint = fingerprint(entry)

    @property
    def title(self) -> str:
        """Return the biome's name."""
        return self.entry.title

    def device(self, device_id: str) -> Device | None:
        """Return a device by its id."""
        return next((d for d in self.devices if d.id == device_id), None)

    @property
    def plan(self) -> Plan:
        """Return the plan as it stands. It is kept while nothing it depends on changes."""
        tz = dt_util.get_default_time_zone()
        key = (repr(self.manual), str(tz), self.hass.config.latitude, self.hass.config.longitude)
        if self._plan is None or self._plan[0] != key:
            plan = Plan(
                self.profiles,
                self.manual,
                tz,
                self.hass.config.latitude or 0.0,
                self.settings.natural,
                self.hass.config.longitude or 0.0,
            )
            self._plan = (key, plan)
        return self._plan[1]

    # -- start and stop ---------------------------------------------------------------------------------

    async def async_start(self) -> None:
        """Load the stored state, follow the devices and check them every minute."""
        stored = await self._store.async_load() or {}
        self.paused = bool(stored.get("paused", False))
        self.dry_run = bool(stored.get("dry_run", True))
        self.manual = stored.get("manual")
        self.notes = str(stored.get("notes") or "")
        ids = {d.id for d in self.devices}
        self.overrides = {k: v for k, v in (stored.get("overrides") or {}).items() if k in ids}
        self.log_items.extend(stored.get("log") or [])
        self.pulse_items.extend(stored.get("pulses") or [])
        self._would = {k: v for k, v in (stored.get("would") or {}).items() if k in ids}
        # A device cut off for running too long stays off for the rest of its window, also across a reload.
        now = dt_util.utcnow()
        for key, value in (stored.get("cutoff") or {}).items():
            try:
                until = datetime.fromisoformat(value)
            except (TypeError, ValueError):
                continue
            if key in ids and until > now:
                self._cutoff[key] = until
        if self.devices:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, sorted({d.entity_id for d in self.devices}), self._state_changed
                )
            )
        self._unsubs.append(async_track_time_interval(self.hass, self._tick, timedelta(minutes=CHECK_INTERVAL_MINUTES)))
        self.hass.async_create_task(self.async_check_all(), eager_start=False)

    @callback
    def async_on_stop(self, listener: CALLBACK_TYPE) -> Callable[[], None]:
        """Call `listener` when the biome stops, for example to reload with new settings."""
        self._stop_listeners.append(listener)

        def remove() -> None:
            if listener in self._stop_listeners:
                self._stop_listeners.remove(listener)

        return remove

    async def async_stop(self) -> None:
        """Stop following and store the state."""
        for listener in list(self._stop_listeners):
            listener()
        self._stop_listeners.clear()
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._timer is not None:
            self._timer()
            self._timer = None
        await self._store.async_save(self._stored())

    def _stored(self) -> dict[str, Any]:
        return {
            "paused": self.paused,
            "dry_run": self.dry_run,
            "manual": self.manual,
            "notes": self.notes,
            "overrides": self.overrides,
            "would": self._would,
            "cutoff": {k: v.isoformat() for k, v in self._cutoff.items()},
            "log": list(self.log_items),
            "pulses": list(self.pulse_items),
        }

    def _save(self) -> None:
        self._store.async_delay_save(self._stored, SAVE_DELAY)

    # -- listeners --------------------------------------------------------------------------------------

    @callback
    def async_add_listener(self, listener: CALLBACK_TYPE) -> Callable[[], None]:
        """Call `listener` after every change."""
        self._listeners.append(listener)

        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    def log(self, kind: str, device: Device | None = None, routine: bool = False, **extra: Any) -> None:
        """Remember what happened, newest last."""
        item: dict[str, Any] = {"at": dt_util.now().isoformat(timespec="seconds"), "kind": kind}
        if device is not None:
            item["device"] = device.id
            item["name"] = device.name
        item.update(extra)
        (self.pulse_items if routine else self.log_items).append(item)
        self._save()

    # -- controls ---------------------------------------------------------------------------------------

    async def async_set_paused(self, paused: bool) -> None:
        """Pause the biome: devices stay as they are. Resuming checks them at once."""
        if paused == self.paused:
            return
        self.paused = paused
        self.log("paused" if paused else "running")
        self._notify()
        if not paused:
            await self.async_check_all()

    async def async_set_dry_run(self, dry_run: bool) -> None:
        """In a dry run Biome only shows and logs what it would switch."""
        if dry_run == self.dry_run:
            return
        self.dry_run = dry_run
        self._would.clear()
        # Cut-offs of the dry run were only simulated; the real run starts afresh.
        self._cutoff.clear()
        self._cut_phase.clear()
        self.log("dry_run_on" if dry_run else "dry_run_off")
        self._notify()
        if not dry_run:
            await self.async_check_all()

    async def async_set_profile(self, profile_id: str | None) -> None:
        """Choose a profile by hand. With dated profiles, the choice lasts until the next season starts."""
        today = dt_util.now().date()
        if profile_id is None or profile_id not in {p.id for p in self.profiles}:
            self.manual = None
        elif self.plan.automatic:
            if (auto := self.plan.auto_profile(today)) is not None and auto.id == profile_id:
                self.manual = None
            else:
                until = self.plan.next_season_change(today)
                self.manual = {"profile": profile_id, "until": until.isoformat() if until else None}
        else:
            self.manual = {"profile": profile_id, "until": None}
        profile = self.plan.profile(today)
        self.log("profile", profile=profile.name if profile else None, manual=self.manual is not None)
        self._notify()
        await self.async_check_all()

    @callback
    def async_set_notes(self, text: str) -> None:
        """Keep free notes on the biome, for example what the animals need."""
        self.notes = text
        self._save()
        self._notify()

    async def async_resume(self, device_id: str | None = None) -> None:
        """Drop manual overrides, of one device or all, and follow the plan again."""
        targets = [device_id] if device_id else list(self.overrides)
        for key in targets:
            if self.overrides.pop(key, None) is not None:
                self.log("resumed", self.device(key))
        self._notify()
        await self.async_check_all()

    # -- checking ---------------------------------------------------------------------------------------

    @callback
    def _tick(self, _now: datetime) -> None:
        self.hass.async_create_task(self.async_check_all(), eager_start=False)

    async def async_check_all(self) -> None:
        """Check every device."""
        if self.manual and not self.plan.manual_applies(dt_util.now().date()):
            self.manual = None
            self.log("profile_auto")
        await asyncio.gather(*(self.async_check(d) for d in self.devices))
        self._schedule()
        self._notify()

    @callback
    def _schedule(self) -> None:
        """Wake up at the next moment something changes: a switching point, a dimming step,
        the end of a manual switch, or midnight for the next profile."""
        if self._timer is not None:
            self._timer()
            self._timer = None
        if not self._unsubs:
            return
        now = dt_util.now()
        plan = self.plan
        tomorrow = now.astimezone(plan.tz).date() + timedelta(days=1)
        moments = [datetime.combine(tomorrow, time(0), plan.tz)]
        # The day phase changes at the biome day's edges, even when no device switches there.
        today = tomorrow - timedelta(days=1)
        for start, end in plan.day_windows(today - timedelta(days=1), tomorrow):
            moments += [start, end]
        for device in self.devices:
            if (moment := plan.next_moment(device, now)) is not None:
                moments.append(moment)
            until = (self.overrides.get(device.id) or {}).get("until")
            if until:
                moments.append(datetime.fromisoformat(until))
            # A command that has not taken yet is tried again soon, not only at the next check.
            if self._attempts.get(device.id, 0) > 0 and device.id in self._sent:
                sent, target = self._sent[device.id]
                if target == STATE_OFF:
                    # Switching off keeps being tried: soon at first, then every two minutes.
                    retry = RETRY_OFF if self._attempts[device.id] <= MAX_ATTEMPTS else timedelta(minutes=2)
                    moments.append(sent + retry)
                elif self._attempts[device.id] <= MAX_ATTEMPTS:
                    moments.append(sent + RETRY_ON)
            # A device that may only stay on for a while is checked when its time is up.
            limit = device.limit(self.settings)
            state = self.hass.states.get(device.entity_id)
            if (
                limit
                and state is not None
                and state.state == STATE_ON
                and self._cut_phase.get(device.id) != state.last_changed
            ):
                moments.append(state.last_changed + timedelta(seconds=limit))
            if (cutoff := self._cutoff.get(device.id)) is not None:
                moments.append(cutoff)
        # Compare instants, never wall clocks: around the change of clocks they would mislead.
        future = [m for m in moments if m.timestamp() > now.timestamp()]
        moment = min(future, key=lambda m: m.timestamp()) if future else now + timedelta(minutes=1)
        self._timer = async_track_point_in_time(self.hass, self._wake, moment)

    @callback
    def _wake(self, _now: datetime) -> None:
        self._timer = None
        self.hass.async_create_task(self.async_check_all(), eager_start=False)

    def _override(self, device: Device, now: datetime) -> dict[str, Any] | None:
        """Return the device's manual override, dropping it when it has run out."""
        item = self.overrides.get(device.id)
        if item is None:
            return None
        until = item.get("until")
        if until is not None and now >= datetime.fromisoformat(until):
            self.overrides.pop(device.id, None)
            self.log("override_ended", device)
            return None
        return item

    def desired(self, device: Device, now: datetime) -> tuple[bool, int | None]:
        """Return whether the device should be on, and at which brightness."""
        cutoff = self._cutoff.get(device.id)
        if cutoff is not None and now < cutoff:
            return False, None
        override = self._override(device, now)
        if override is not None:
            return override["state"] == STATE_ON, None
        plan = self.plan
        return plan.is_on(device, now), plan.brightness(device, now)

    async def async_check(self, device: Device) -> None:
        """Bring one device to what it should be."""
        lock = self._locks.setdefault(device.id, asyncio.Lock())
        if lock.locked():
            return
        async with lock:
            await self._check(device)

    async def _check(self, device: Device) -> None:
        # In UTC: around the change of clocks, local times of the same zone compare by the wall clock.
        now = dt_util.utcnow()
        state = self.hass.states.get(device.entity_id)
        if state is None or state.state not in SWITCHABLE:
            self.problems[device.id] = "missing" if state is None else "unavailable"
            return
        self._limit(device, state, now)
        if not self.profiles:
            # Without a profile there is no plan. Switching everything off would be the worst guess.
            # Only a device that is on too long is switched off.
            if device.id in self._cutoff and state.state == STATE_ON and not self.dry_run:
                await self._switch(device, False, None, first=False)
            return
        on, brightness = self.desired(device, now)
        if self.problems.get(device.id) in ("missing", "unavailable"):
            self.problems.pop(device.id, None)
        is_on = state.state == STATE_ON
        # Brightness is set when switching on and during the dimming ramps; otherwise Biome leaves it alone.
        level = brightness if on and device.domain == "light" and device.id not in self.overrides else None
        dimming = level is not None and is_on and self.plan.ramping(device, now) and self._brightness_off(state, level)
        if is_on == on and not dimming:
            self._attempts.pop(device.id, None)
            self._would.pop(device.id, None)
            if self.problems.get(device.id) == "failed":
                self.problems.pop(device.id, None)
            return
        # Paused, Biome switches nothing, except a device that has been on longer than it may.
        if self.paused and not (is_on and not on and device.id in self._cutoff):
            return
        target = STATE_ON if on else STATE_OFF
        if self.dry_run:
            if is_on != on and self._would.get(device.id) != target:
                self._would[device.id] = target
                self.log("would_switch", device, routine=self._pulsed(device), state=target)
                self._save()
            return
        sent = self._sent.get(device.id)
        settle = SETTLE_OFF if target == STATE_OFF else SETTLE_ON
        if sent is not None and sent[1] == target and now - sent[0] < settle and not dimming:
            return
        attempts = self._attempts.get(device.id, 0) + 1
        self._attempts[device.id] = attempts
        if attempts > MAX_ATTEMPTS:
            if self.problems.get(device.id) != "failed":
                self.problems[device.id] = "failed"
                self.log("failed", device, state=target)
            # Switching on is tried again only now and then; switching off every time, it is the safe side.
            if target == STATE_ON and attempts % 5:
                return
        self._sent[device.id] = (now, target)
        await self._switch(device, on, level, first=attempts == 1 and not dimming)

    def _last_pulses(self) -> dict[str, list[dict[str, Any]]]:
        """Return the last two interval switches of each device."""
        out: dict[str, list[dict[str, Any]]] = {}
        for item in reversed(self.pulse_items):
            key = item.get("device")
            if key and len(out.setdefault(key, [])) < 2:
                out[key].insert(0, item)
        return out

    def full_log(self) -> list[dict[str, Any]]:
        """Return the whole log, interval switches included, oldest first."""

        def instant(item: dict[str, Any]) -> float:
            try:
                return datetime.fromisoformat(item["at"]).timestamp()
            except (KeyError, TypeError, ValueError):
                return 0.0

        return sorted([*self.log_items, *({**i, "routine": True} for i in self.pulse_items)], key=instant)

    def _pulsed(self, device: Device) -> bool:
        """Whether the device runs in intervals now. Its many routine switches stay out of the log."""
        plan = self.plan
        profile = plan.profile(dt_util.now().date())
        if profile is None:
            return False
        setting = device.setting(profile, plan.by_id)
        return not setting.always and any(s.every and s.pulse for s in setting.spans)

    def _limit(self, device: Device, state: State, now: datetime) -> None:
        """Switch a device off that has been on longer than it may, once per time it went on.

        It stays off until the plan's window ends; without such an end (around the clock, or on while the plan
        has it off) until midnight or not at all. A device that does not follow is not cut again and again:
        the retries of switching off take care of it.
        """
        cutoff = self._cutoff.get(device.id)
        if cutoff is not None and now >= cutoff:
            self._cutoff.pop(device.id, None)
            if self.problems.get(device.id) == "max_on":
                self.problems.pop(device.id, None)
        limit = device.limit(self.settings)
        if not limit or state.state != STATE_ON or self._cut_phase.get(device.id) == state.last_changed:
            return
        if now - state.last_changed < timedelta(seconds=limit):
            return
        self._cut_phase[device.id] = state.last_changed
        plan = self.plan
        if plan.is_on(device, now):
            change = plan.next_change(device, now)
            local = now.astimezone(plan.tz)
            midnight = datetime.combine(local.date() + timedelta(days=1), time(0), plan.tz)
            self._cutoff[device.id] = change[0] if change else midnight
        else:
            # The plan has it off anyway; switching off is enough.
            self._cutoff[device.id] = now + timedelta(seconds=limit)
        self._save()
        if self.dry_run:
            return  # the dry run logs that it would switch off
        # Not even a manual switch lifts the limit.
        self.overrides.pop(device.id, None)
        self.problems[device.id] = "max_on"
        self.log("max_on", device, routine=self._pulsed(device), seconds=limit)

    @staticmethod
    def _brightness_off(state: State, brightness: int) -> bool:
        current = state.attributes.get("brightness")
        if current is None:
            return False
        return abs(round(current / 2.55) - brightness) > BRIGHTNESS_TOLERANCE

    async def _switch(self, device: Device, on: bool, brightness: int | None, first: bool) -> None:
        context = Context()
        self._ours.append(context.id)
        data: dict[str, Any] = {ATTR_ENTITY_ID: device.entity_id}
        if on and brightness is not None:
            data["brightness_pct"] = brightness
        if first:
            self.log(
                "switched",
                device,
                routine=self._pulsed(device),
                state=STATE_ON if on else STATE_OFF,
                brightness=brightness,
            )
        try:
            await self.hass.services.async_call(
                device.domain, "turn_on" if on else "turn_off", data, blocking=True, context=context
            )
        except (HomeAssistantError, ValueError) as err:
            _LOGGER.warning("%s: could not switch %s: %s", self.title, device.entity_id, err)

    # -- state changes ----------------------------------------------------------------------------------

    @callback
    def _state_changed(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        new: State | None = event.data["new_state"]
        old: State | None = event.data["old_state"]
        for device in [d for d in self.devices if d.entity_id == entity_id]:
            self._handle_change(device, old, new)
        # A device that just went on may have to go off after its longest time.
        self._schedule()
        self._notify()

    def _handle_change(self, device: Device, old: State | None, new: State | None) -> None:
        if new is None or new.state not in SWITCHABLE:
            self.problems[device.id] = "missing" if new is None else "unavailable"
            return
        ours = new.context.id in self._ours or (new.context.parent_id in self._ours)
        old_state = old.state if old is not None else None
        if ours or old_state == new.state:
            if ours:
                self._attempts.pop(device.id, None)
            return
        if old_state not in SWITCHABLE:
            # Back from unavailable or unknown: whatever it does now, the plan applies.
            self.problems.pop(device.id, None)
            self.hass.async_create_task(self.async_check(device), eager_start=False)
            return
        self._manual_change(device, new)

    def _manual_change(self, device: Device, new: State) -> None:
        """Someone switched the device: by hand, in an app, by voice or by an automation."""
        now = dt_util.utcnow()
        plan = self.plan
        planned = STATE_ON if plan.is_on(device, now) else STATE_OFF
        if self.paused:
            return
        if device.manual == MANUAL_NEVER:
            if not self.dry_run:
                self.log("corrected", device, state=planned)
            self.hass.async_create_task(self.async_check(device), eager_start=False)
            return
        if new.state == planned:
            if self.overrides.pop(device.id, None) is not None:
                self.log("resumed", device)
            return
        if device.manual == MANUAL_DURATION:
            until: datetime | None = now + timedelta(minutes=device.manual_minutes)
        else:
            change = plan.next_change(device, now)
            # Without a switching point ahead (around the clock, or off in the profile), a manual switch
            # lasts for the manual duration, never for good: a heat mat switched off for cleaning comes back.
            until = change[0] if change else now + timedelta(minutes=device.manual_minutes)
        self.overrides[device.id] = {
            "state": new.state,
            "since": now.isoformat(timespec="seconds"),
            "until": _local(until) if until else None,
        }
        self.log("manual", device, state=new.state, until=_local(until) if until else None)

    # -- for the entities and the page ------------------------------------------------------------------

    def status(self, device: Device, now: datetime | None = None) -> dict[str, Any]:
        """Return what the device should do and why."""
        now = now or dt_util.now()
        plan = self.plan
        today = now.astimezone(plan.tz).date()
        profile = plan.profile(today)
        override = self.overrides.get(device.id)
        planned = plan.is_on(device, now)
        active = profile is not None and device.setting(profile, plan.by_id).active
        if override is not None:
            on, reason = override["state"] == STATE_ON, "manual"
        else:
            on, reason = planned, "plan" if active else "inactive"
        change = plan.next_change(device, now)
        state = self.hass.states.get(device.entity_id)
        return {
            "on": on,
            "planned": planned,
            "reason": reason,
            "paused": self.paused,
            "override": override,
            "next_change": _local(change[0]) if change else None,
            "next_state": (STATE_ON if change[1] else STATE_OFF) if change else None,
            "actual": state.state if state else None,
            "brightness": plan.brightness(device, now),
            "problem": self.problems.get(device.id),
            "would": self._would.get(device.id),
        }

    def next_switch(self, now: datetime | None = None) -> tuple[datetime, Device, bool] | None:
        """Return the next switching point of all devices by the plan."""
        now = now or dt_util.now()
        plan = self.plan
        best: tuple[datetime, Device, bool] | None = None
        for device in self.devices:
            change = plan.next_change(device, now)
            if change and (best is None or change[0] < best[0]):
                best = (change[0], device, change[1])
        return best

    def snapshot(self) -> dict[str, Any]:
        """Return everything the page and the card show."""
        now = dt_util.now()
        plan = self.plan
        today = now.astimezone(plan.tz).date()
        start = plan_start = datetime.combine(today, datetime.min.time(), plan.tz)
        end = plan_start + timedelta(days=1)
        profile = plan.profile(today)

        def clip(a: datetime, b: datetime) -> list[str] | None:
            a, b = max(a, start), min(b, end)
            return [_local(a), _local(b)] if a < b else None

        def windows(device: Device) -> list[dict[str, Any]]:
            out = []
            for w in plan.windows(device, today - timedelta(days=1), today):
                if (span := clip(w.start, w.end)) is not None:
                    out.append(
                        {
                            "span": span,
                            "start": _local(w.start),
                            "end": _local(w.end),
                            "brightness": w.setting.brightness,
                            "ramp": w.setting.ramp,
                        }
                    )
            return out

        devices = []
        for device in self.devices:
            setting = device.setting(profile, plan.by_id) if profile else None
            devices.append(
                {
                    "id": device.id,
                    "name": device.name,
                    "kind": device.kind,
                    "entity_id": device.entity_id,
                    "manual": device.manual,
                    "manual_minutes": device.manual_minutes,
                    "max_on": device.limit(self.settings),
                    "setting": None
                    if setting is None
                    else {
                        "active": setting.active,
                        "always": setting.always,
                        "spans": [span_data(x) for x in setting.spans],
                        "brightness": setting.brightness,
                        "ramp": setting.ramp,
                    },
                    "windows": windows(device),
                    **self.status(device, now),
                }
            )
        nxt = self.next_switch(now)
        effective = plan.effective(today)
        change = plan.transition(today)
        return {
            "entry_id": self.entry.entry_id,
            "device_id": self.device_id,
            "title": self.title,
            "now": now.isoformat(),
            "range": [start.isoformat(), end.isoformat()],
            "time_zone": str(plan.tz),
            "paused": self.paused,
            "dry_run": self.dry_run,
            "day": plan.is_day(now),
            "day_windows": [s for a, b in plan.day_windows(today - timedelta(days=1), today) if (s := clip(a, b))],
            "profile": {
                "id": profile.id if profile else None,
                "name": profile.name if profile else None,
                "manual": plan.manual_applies(today),
                "until": self.manual.get("until") if self.manual and plan.manual_applies(today) else None,
                "automatic": plan.automatic,
                "day_start": clock_of(effective.day_start) if effective else None,
                "day_end": clock_of(effective.day_end) if effective else None,
                "transition": {
                    "from": change.previous.name,
                    "day": change.day,
                    "days": change.days,
                }
                if change
                else None,
            },
            "profiles": [
                {
                    "id": p.id,
                    "name": p.name,
                    "day_start": clock_of(p.day_start),
                    "day_end": clock_of(p.day_end),
                    "start": f"{p.start[0]:02d}-{p.start[1]:02d}" if p.start else None,
                    "transition": p.transition,
                    "event": p.event,
                    "offset": p.offset,
                    "day_mode": p.day_mode,
                    "last_start": (d.isoformat() if (d := plan.last_start(p, today)) and p.dated else None),
                    "next_start": (d.isoformat() if (d := plan.next_start(p, today)) and p.dated else None),
                    "today": [clock_of(t[0]), clock_of(t[0] + t[1])] if (t := plan.day_times(p, today)) else None,
                }
                for p in self.profiles
            ],
            "latitude": self.hass.config.latitude,
            "longitude": self.hass.config.longitude,
            "devices": devices,
            "config": config_of(self.entry),
            "notes": self.notes,
            "next": {"at": _local(nxt[0]), "device": nxt[1].id, "name": nxt[1].name, "state": nxt[2]} if nxt else None,
            "log": list(self.log_items)[-80:],
            "pulse_log": self._last_pulses(),
        }
