"""Save profiles, devices and biome settings from the Biome page, with one reload at the end."""

from __future__ import annotations

import json
from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
import voluptuous as vol

from .astro import EVENT_DATE, EVENTS
from .const import (
    CONF_COPY_FROM,
    CONF_DAY_END,
    CONF_DAY_MODE,
    CONF_DAY_START,
    CONF_ENTITY_ID,
    CONF_KIND,
    CONF_MANUAL,
    CONF_MANUAL_MINUTES,
    CONF_MAX_ON,
    CONF_ORDER,
    CONF_PROFILES,
    CONF_START_DATE,
    CONF_START_EVENT,
    CONF_START_OFFSET,
    CONF_TRANSITION,
    DAY_FIXED,
    DAY_MODES,
    DEFAULT_MAX_ON,
    DOMAIN,
    KINDS,
    MANUAL_MODES,
    OFFSET_LIMIT,
    OPT_MAX_ON,
    OPT_NATURAL,
    OPT_PRICE,
    OPT_SENSORS,
    RAMP_LIMIT,
    REFS,
    SUBENTRY_DEVICE,
    SUBENTRY_PROFILE,
    TRANSITION_LIMIT,
)
from .model import (
    clock_of,
    device_from,
    device_order,
    minutes_of,
    month_day,
    setting_data,
    setting_from,
)

DATA_SAVING = f"{DOMAIN}_saving"


def _clock(value: Any) -> str:
    try:
        return clock_of(minutes_of(str(value)))
    except (ValueError, IndexError) as err:
        raise vol.Invalid(f"not a time: {value}") from err


def _month_day(value: Any) -> str | None:
    if value in (None, ""):
        return None
    parsed = month_day(str(value))
    if parsed is None:
        raise vol.Invalid(f"not a date: {value}")
    return f"{parsed[0]:02d}-{parsed[1]:02d}"


def _edge(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("ref") not in REFS:
        raise vol.Invalid("an edge needs a ref: start, end or clock")
    raw = value.get("value", 0)
    if value["ref"] == "clock":
        minutes = minutes_of(raw) if isinstance(raw, str) else int(raw) % 1440
        return {"ref": "clock", "value": minutes}
    offset = int(raw)
    if not -OFFSET_LIMIT <= offset <= OFFSET_LIMIT:
        raise vol.Invalid(f"offset out of range: {offset}")
    return {"ref": value["ref"], "value": offset}


NAME = vol.All(str, vol.Strip, vol.Length(min=1, max=60))
POSITIVE = vol.All(vol.Coerce(int), vol.Range(min=0))

PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required("id"): str,
        vol.Required("name"): NAME,
        vol.Required(CONF_DAY_START): _clock,
        vol.Required(CONF_DAY_END): _clock,
        vol.Optional(CONF_START_DATE, default=None): _month_day,
        vol.Optional(CONF_START_EVENT, default=EVENT_DATE): vol.In(EVENTS),
        vol.Optional(CONF_START_OFFSET, default=0): vol.All(vol.Coerce(int), vol.Range(min=-180, max=180)),
        vol.Optional(CONF_TRANSITION, default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=TRANSITION_LIMIT)),
        vol.Optional(CONF_DAY_MODE, default=DAY_FIXED): vol.In(DAY_MODES),
        vol.Optional(CONF_COPY_FROM, default=None): vol.Any(None, str),
    },
    extra=vol.REMOVE_EXTRA,
)

SPAN_SCHEMA = vol.Schema(
    {
        vol.Required("on"): _edge,
        vol.Required("off"): _edge,
        vol.Optional("every", default=None): vol.Any(None, vol.All(vol.Coerce(int), vol.Range(min=1, max=1440))),
        vol.Optional("pulse", default=None): vol.Any(None, vol.All(vol.Coerce(int), vol.Range(min=1, max=86400))),
    },
    extra=vol.REMOVE_EXTRA,
)


def _setting(value: Any) -> dict[str, Any]:
    """Validate a device setting and store it in the current form, also when it comes in an older one."""
    if not isinstance(value, dict):
        raise vol.Invalid("a setting must be an object")
    if "spans" in value:
        value = {**value, "spans": [SPAN_SCHEMA(s) for s in value["spans"] or []]}
    brightness = value.get("brightness")
    if brightness not in (None, "") and not 1 <= int(brightness) <= 100:
        raise vol.Invalid(f"brightness out of range: {brightness}")
    if not 0 <= int(value.get("ramp") or 0) <= RAMP_LIMIT:
        raise vol.Invalid("ramp out of range")
    return setting_data(setting_from(value))


DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required("id"): str,
        vol.Required("name"): NAME,
        vol.Required(CONF_ENTITY_ID): vol.All(str, vol.Match(r"^(switch|light)\.[a-z0-9_]+$")),
        vol.Optional(CONF_KIND, default="other"): vol.In(KINDS),
        vol.Optional(CONF_MANUAL, default="next"): vol.In(MANUAL_MODES),
        vol.Optional(CONF_MANUAL_MINUTES, default=60): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
        vol.Optional(CONF_MAX_ON, default=None): vol.Any(None, POSITIVE),
        vol.Optional(CONF_PROFILES, default=dict): {str: _setting},
    },
    extra=vol.REMOVE_EXTRA,
)

SETTINGS_SCHEMA = vol.Schema(
    {
        vol.Optional(OPT_MAX_ON, default=dict): {vol.In(KINDS): POSITIVE},
        vol.Optional(OPT_NATURAL, default=dict): vol.Schema(
            {
                vol.Optional("latitude"): vol.Any(None, vol.All(vol.Coerce(float), vol.Range(min=-90, max=90))),
                vol.Optional("longitude"): vol.Any(None, vol.All(vol.Coerce(float), vol.Range(min=-180, max=180))),
                vol.Optional("min_length"): vol.All(vol.Coerce(int), vol.Range(min=0, max=1439)),
                vol.Optional("max_length"): vol.All(vol.Coerce(int), vol.Range(min=0, max=1439)),
                vol.Optional("center"): vol.Any(None, _clock),
                vol.Optional("factor"): vol.All(vol.Coerce(float), vol.Range(min=0, max=1.5)),
                vol.Optional("invert"): bool,
            },
            extra=vol.REMOVE_EXTRA,
        ),
        vol.Optional(OPT_SENSORS, default=list): [vol.Match(r"^[a-z_]+\.[a-z0-9_]+$")],
        vol.Optional(OPT_PRICE, default=None): vol.Any(None, vol.All(vol.Coerce(float), vol.Range(min=0))),
    },
    extra=vol.REMOVE_EXTRA,
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required("profiles"): vol.All([PROFILE_SCHEMA], vol.Length(min=1)),
        vol.Required("devices"): [DEVICE_SCHEMA],
        vol.Optional("settings"): SETTINGS_SCHEMA,
    },
    extra=vol.REMOVE_EXTRA,
)


def fingerprint(entry: ConfigEntry) -> str:
    """Return what the biome's settings look like, to skip reloads that change nothing."""
    items = sorted((s.subentry_id, s.subentry_type, s.title, dict(s.data)) for s in entry.subentries.values())
    return json.dumps([entry.title, dict(entry.options), items], sort_keys=True, default=str)


def config_of(entry: ConfigEntry) -> dict[str, Any]:
    """Return profiles, devices and biome settings as the page edits them, in the current form."""
    profiles = []
    devices = []
    subs = list(entry.subentries.values())
    order = {
        s.subentry_id: device_order(device_from(s.subentry_id, s.title, s.data))
        for s in subs
        if s.subentry_type == SUBENTRY_DEVICE and s.data.get(CONF_ENTITY_ID)
    }
    subs.sort(key=lambda s: order.get(s.subentry_id, (0, 0, "")))
    for sub in subs:
        data = dict(sub.data)
        if sub.subentry_type == SUBENTRY_PROFILE:
            profiles.append(
                {
                    "id": sub.subentry_id,
                    "name": sub.title,
                    CONF_DAY_START: data.get(CONF_DAY_START, "08:00"),
                    CONF_DAY_END: data.get(CONF_DAY_END, "20:00"),
                    CONF_START_DATE: data.get(CONF_START_DATE),
                    CONF_START_EVENT: data.get(CONF_START_EVENT) or EVENT_DATE,
                    CONF_START_OFFSET: data.get(CONF_START_OFFSET, 0),
                    CONF_TRANSITION: data.get(CONF_TRANSITION, 0),
                    CONF_DAY_MODE: data.get(CONF_DAY_MODE) or DAY_FIXED,
                    CONF_COPY_FROM: data.get(CONF_COPY_FROM),
                }
            )
        elif sub.subentry_type == SUBENTRY_DEVICE:
            devices.append(
                {
                    "id": sub.subentry_id,
                    "name": sub.title,
                    CONF_ENTITY_ID: data.get(CONF_ENTITY_ID),
                    CONF_KIND: data.get(CONF_KIND, "other"),
                    CONF_MANUAL: data.get(CONF_MANUAL, "next"),
                    CONF_MANUAL_MINUTES: data.get(CONF_MANUAL_MINUTES, 60),
                    CONF_MAX_ON: data.get(CONF_MAX_ON),
                    CONF_PROFILES: {
                        pid: setting_data(setting_from(s)) for pid, s in (data.get(CONF_PROFILES) or {}).items()
                    },
                }
            )
    options = dict(entry.options or {})
    settings = {
        OPT_MAX_ON: options.get(OPT_MAX_ON, dict(DEFAULT_MAX_ON)),
        OPT_NATURAL: options.get(OPT_NATURAL) or {},
        OPT_SENSORS: options.get(OPT_SENSORS) or [],
        OPT_PRICE: options.get(OPT_PRICE),
    }
    return {"profiles": profiles, "devices": devices, "settings": settings}


async def async_save_config(hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any]) -> None:
    """Replace the biome's profiles, devices and settings. New items carry ids that are not subentry ids yet."""
    config = CONFIG_SCHEMA(config)
    entities = [d[CONF_ENTITY_ID] for d in config["devices"]]
    if len(entities) != len(set(entities)):
        raise vol.Invalid("a device appears twice")
    for item in config["profiles"]:
        if item[CONF_DAY_MODE] == DAY_FIXED and item[CONF_DAY_START] == item[CONF_DAY_END]:
            raise vol.Invalid(f"{item['name']}: the day cannot start and end at the same time")
    manager = hass.config_entries
    saving: set[str] = hass.data.setdefault(DATA_SAVING, set())
    saving.add(entry.entry_id)
    try:
        if "settings" in config:
            manager.async_update_entry(entry, options={**entry.options, **config["settings"]})
        ids: dict[str, str] = {}
        keep: set[str] = set()
        # Profiles first, so devices can refer to new profiles by their new ids.
        for item in config["profiles"]:
            dated = item[CONF_START_EVENT] != EVENT_DATE or item[CONF_START_DATE]
            data = {
                CONF_DAY_START: item[CONF_DAY_START],
                CONF_DAY_END: item[CONF_DAY_END],
                CONF_START_DATE: item[CONF_START_DATE],
                CONF_START_EVENT: item[CONF_START_EVENT],
                CONF_START_OFFSET: item[CONF_START_OFFSET] if dated else 0,
                CONF_TRANSITION: item[CONF_TRANSITION] if dated else 0,
                CONF_DAY_MODE: item[CONF_DAY_MODE],
                CONF_COPY_FROM: item[CONF_COPY_FROM],
            }
            ids[item["id"]] = _put(manager, entry, SUBENTRY_PROFILE, item["id"], item["name"], data)
        for item in config["profiles"]:
            sub_id = ids[item["id"]]
            keep.add(sub_id)
            copy_from = ids.get(item[CONF_COPY_FROM] or "")
            sub = entry.subentries[sub_id]
            if sub.data.get(CONF_COPY_FROM) != copy_from:
                manager.async_update_subentry(entry, sub, data={**sub.data, CONF_COPY_FROM: copy_from})
        for index, item in enumerate(config["devices"]):
            data = {
                CONF_ORDER: index,
                CONF_ENTITY_ID: item[CONF_ENTITY_ID],
                CONF_KIND: item[CONF_KIND],
                CONF_MANUAL: item[CONF_MANUAL],
                CONF_MANUAL_MINUTES: item[CONF_MANUAL_MINUTES],
                CONF_MAX_ON: item[CONF_MAX_ON],
                CONF_PROFILES: {ids[k]: v for k, v in item[CONF_PROFILES].items() if k in ids},
            }
            keep.add(_put(manager, entry, SUBENTRY_DEVICE, item["id"], item["name"], data))
        for sub_id in [k for k in entry.subentries if k not in keep]:
            manager.async_remove_subentry(entry, sub_id)
    finally:
        saving.discard(entry.entry_id)
        # Also after an error halfway: the biome runs with what was stored.
        await manager.async_reload(entry.entry_id)


def _put(manager: Any, entry: ConfigEntry, kind: str, item_id: str, title: str, data: dict[str, Any]) -> str:
    """Update the subentry with this id, or add a new one. Return its id."""
    sub = entry.subentries.get(item_id)
    if sub is not None and sub.subentry_type == kind:
        if sub.title != title or dict(sub.data) != data:
            manager.async_update_subentry(entry, sub, title=title, data=data)
        return sub.subentry_id
    new = ConfigSubentry(data=MappingProxyType(data), subentry_type=kind, title=title, unique_id=None)
    manager.async_add_subentry(entry, new)
    return new.subentry_id
