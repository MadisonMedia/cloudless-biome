"""Config flow: a biome with its first profile, then profiles and devices as subentries."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector
import voluptuous as vol

from .const import (
    CONF_ACTIVE,
    CONF_BRIGHTNESS,
    CONF_COPY_FROM,
    CONF_DAY_END,
    CONF_DAY_START,
    CONF_ENTITY_ID,
    CONF_KIND,
    CONF_MANUAL,
    CONF_MANUAL_MINUTES,
    CONF_OFF_OFFSET,
    CONF_ON_OFFSET,
    CONF_PROFILE_NAME,
    CONF_PROFILES,
    CONF_RAMP,
    CONF_START_DATE,
    CONF_START_EVENT,
    CONF_TRANSITION,
    DOMAIN,
    KINDS,
    MANUAL_MODES,
    MANUAL_NEXT,
    OFFSET_LIMIT,
    PANEL_URL,
    RAMP_LIMIT,
    SUBENTRY_DEVICE,
    SUBENTRY_PROFILE,
    TRANSITION_LIMIT,
)
from .model import (
    Edge,
    Span,
    clock_of,
    minutes_of,
    month_day,
    profiles_of,
    setting_data,
    setting_from,
    span_data,
)

TIME = selector.TimeSelector()
MINUTES = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=-OFFSET_LIMIT, max=OFFSET_LIMIT, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="min"
    )
)


def _clock(value: str) -> str:
    """Store times as HH:MM."""
    return clock_of(minutes_of(value))


def _profile_data(user_input: dict[str, Any]) -> dict[str, Any]:
    start = month_day(user_input.get(CONF_START_DATE))
    return {
        CONF_DAY_START: _clock(user_input[CONF_DAY_START]),
        CONF_DAY_END: _clock(user_input[CONF_DAY_END]),
        CONF_START_DATE: f"{start[0]:02d}-{start[1]:02d}" if start else None,
        CONF_TRANSITION: int(user_input.get(CONF_TRANSITION) or 0) if start else 0,
    }


def _same_times(user_input: dict[str, Any]) -> bool:
    return minutes_of(user_input[CONF_DAY_START]) == minutes_of(user_input[CONF_DAY_END])


def _plain(stored: dict[str, Any]) -> bool:
    """Whether a setting is one window with the biome day, the only kind the dialog can edit."""
    if not stored:
        return True
    setting = setting_from(stored)
    if setting.always or len(setting.spans) != 1:
        return False
    span = setting.spans[0]
    return span.on.ref == "start" and span.off.ref == "end" and not span.every


def _default_profile_name(language: str | None) -> str:
    return "Standard" if (language or "en").startswith("de") else "Default"


class BiomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create a biome with its first profile."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        """Profiles and devices are subentries."""
        return {SUBENTRY_PROFILE: ProfileFlow, SUBENTRY_DEVICE: DeviceFlow}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Name the biome and set its day."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if _same_times(user_input):
                errors["base"] = "same_times"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME].strip(),
                    data={},
                    subentries=[
                        ConfigSubentryData(
                            subentry_type=SUBENTRY_PROFILE,
                            title=user_input[CONF_PROFILE_NAME].strip(),
                            data=_profile_data(user_input),
                            unique_id=None,
                        )
                    ],
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_NAME): selector.TextSelector(),
                        vol.Required(CONF_PROFILE_NAME): selector.TextSelector(),
                        vol.Required(CONF_DAY_START): TIME,
                        vol.Required(CONF_DAY_END): TIME,
                        vol.Optional(CONF_START_DATE): selector.DateSelector(),
                    }
                ),
                user_input
                or {
                    CONF_NAME: "Terrarium",
                    CONF_PROFILE_NAME: _default_profile_name(self.hass.config.language),
                    CONF_DAY_START: "08:00:00",
                    CONF_DAY_END: "20:00:00",
                },
            ),
            errors=errors,
            description_placeholders={"panel": f"/{PANEL_URL}"},
        )


class ProfileFlow(ConfigSubentryFlow):
    """Add or change a profile: a season with its own biome day."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Add a profile."""
        return await self._form("user", user_input)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Change a profile."""
        return await self._form("reconfigure", user_input)

    async def _form(self, step_id: str, user_input: dict[str, Any] | None) -> SubentryFlowResult:
        entry = self._get_entry()
        reconfigure = self.source == SOURCE_RECONFIGURE
        errors: dict[str, str] = {}
        if user_input is not None:
            if _same_times(user_input):
                errors["base"] = "same_times"
            else:
                data = _profile_data(user_input)
                title = user_input[CONF_PROFILE_NAME].strip()
                if reconfigure:
                    subentry = self._get_reconfigure_subentry()
                    if (subentry.data.get(CONF_START_EVENT) or "date") != "date":
                        # The profile starts with an event set on the Biome page; the dialog leaves that alone.
                        data = {k: v for k, v in data.items() if k not in (CONF_START_DATE, CONF_TRANSITION)}
                    return self.async_update_and_abort(entry, subentry, title=title, data={**subentry.data, **data})
                data[CONF_COPY_FROM] = user_input.get(CONF_COPY_FROM) or None
                return self.async_create_entry(title=title, data=data)
        fields: dict[Any, Any] = {
            vol.Required(CONF_PROFILE_NAME): selector.TextSelector(),
            vol.Required(CONF_DAY_START): TIME,
            vol.Required(CONF_DAY_END): TIME,
            vol.Optional(CONF_START_DATE): selector.DateSelector(),
            vol.Optional(CONF_TRANSITION): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=TRANSITION_LIMIT, step=1, mode=selector.NumberSelectorMode.BOX)
            ),
        }
        profiles = profiles_of(entry)
        if not reconfigure and profiles:
            fields[vol.Optional(CONF_COPY_FROM)] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[selector.SelectOptionDict(value=p.id, label=p.name) for p in profiles],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        if user_input is not None:
            suggested = user_input
        elif reconfigure:
            subentry = self._get_reconfigure_subentry()
            start = subentry.data.get(CONF_START_DATE)
            suggested = {
                CONF_PROFILE_NAME: subentry.title,
                CONF_DAY_START: f"{subentry.data[CONF_DAY_START]}:00",
                CONF_DAY_END: f"{subentry.data[CONF_DAY_END]}:00",
                CONF_TRANSITION: subentry.data.get(CONF_TRANSITION, 0),
            }
            if start:
                suggested[CONF_START_DATE] = f"2026-{start}"
        else:
            first = profiles[0] if profiles else None
            suggested = {
                CONF_DAY_START: f"{clock_of(first.day_start)}:00" if first else "08:00:00",
                CONF_DAY_END: f"{clock_of(first.day_end)}:00" if first else "20:00:00",
                CONF_TRANSITION: 0,
            }
            if first:
                suggested[CONF_COPY_FROM] = first.id
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(vol.Schema(fields), suggested),
            errors=errors,
        )


class DeviceFlow(ConfigSubentryFlow):
    """Add or change a device, then set how it runs in each profile."""

    def __init__(self) -> None:
        """Initialize."""
        super().__init__()
        self._data: dict[str, Any] = {}
        self._title = ""
        self._index = 0

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Add a device."""
        return await self._device("user", user_input)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Change a device."""
        return await self._device("reconfigure", user_input)

    async def _device(self, step_id: str, user_input: dict[str, Any] | None) -> SubentryFlowResult:
        entry = self._get_entry()
        if not profiles_of(entry):
            return self.async_abort(reason="no_profiles")
        reconfigure = self.source == SOURCE_RECONFIGURE
        current = self._get_reconfigure_subentry() if reconfigure else None
        errors: dict[str, str] = {}
        if user_input is not None:
            entity_id = user_input[CONF_ENTITY_ID]
            used = {
                s.data.get(CONF_ENTITY_ID)
                for s in entry.subentries.values()
                if s.subentry_type == SUBENTRY_DEVICE and (current is None or s.subentry_id != current.subentry_id)
            }
            if entity_id in used:
                errors[CONF_ENTITY_ID] = "already_used"
            else:
                state = self.hass.states.get(entity_id)
                name = (user_input.get(CONF_NAME) or "").strip()
                if not name:
                    name = state.name if state else entity_id
                self._title = name
                self._data = {
                    **(dict(current.data) if current else {}),
                    CONF_ENTITY_ID: entity_id,
                    CONF_KIND: user_input[CONF_KIND],
                    CONF_MANUAL: user_input[CONF_MANUAL],
                    CONF_MANUAL_MINUTES: int(user_input.get(CONF_MANUAL_MINUTES) or 60),
                }
                self._data.setdefault(CONF_PROFILES, {})
                self._data[CONF_PROFILES] = dict(self._data[CONF_PROFILES])
                self._index = 0
                return await self.async_step_profile()
        if user_input is not None:
            suggested = user_input
        elif current is not None:
            suggested = {
                CONF_ENTITY_ID: current.data[CONF_ENTITY_ID],
                CONF_NAME: current.title,
                CONF_KIND: current.data.get(CONF_KIND, "other"),
                CONF_MANUAL: current.data.get(CONF_MANUAL, MANUAL_NEXT),
                CONF_MANUAL_MINUTES: current.data.get(CONF_MANUAL_MINUTES, 60),
            }
        else:
            suggested = {CONF_KIND: "light", CONF_MANUAL: MANUAL_NEXT, CONF_MANUAL_MINUTES: 60}
        schema = vol.Schema(
            {
                vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["switch", "light"])
                ),
                vol.Optional(CONF_NAME): selector.TextSelector(),
                vol.Required(CONF_KIND): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=list(KINDS), translation_key=CONF_KIND)
                ),
                vol.Required(CONF_MANUAL): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=list(MANUAL_MODES), translation_key=CONF_MANUAL)
                ),
                vol.Optional(CONF_MANUAL_MINUTES): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=1440, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="min"
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id=step_id, data_schema=self.add_suggested_values_to_schema(schema, suggested), errors=errors
        )

    async def async_step_profile(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Set how the device runs in one profile; one step per profile."""
        entry = self._get_entry()
        profiles = profiles_of(entry)
        light = self._data[CONF_ENTITY_ID].startswith("light.")
        if user_input is not None:
            profile = profiles[self._index]
            setting = {
                CONF_ACTIVE: bool(user_input.get(CONF_ACTIVE, True)),
                CONF_ON_OFFSET: int(user_input.get(CONF_ON_OFFSET) or 0),
                CONF_OFF_OFFSET: int(user_input.get(CONF_OFF_OFFSET) or 0),
            }
            if light:
                brightness = user_input.get(CONF_BRIGHTNESS)
                setting[CONF_BRIGHTNESS] = int(brightness) if brightness else None
                setting[CONF_RAMP] = int(user_input.get(CONF_RAMP) or 0)
            # The dialog edits one window with the biome day. Several windows, fixed times or intervals
            # from the Biome page stay as they are.
            prior = self._data[CONF_PROFILES].get(profile.id) or {}
            merged = {**prior, **setting}
            if _plain(prior):
                merged["spans"] = [
                    span_data(Span(Edge("start", setting[CONF_ON_OFFSET]), Edge("end", setting[CONF_OFF_OFFSET])))
                ]
            self._data[CONF_PROFILES][profile.id] = setting_data(setting_from(merged))
            self._index += 1
        if self._index >= len(profiles):
            return self._finish()
        profile = profiles[self._index]
        stored = self._data[CONF_PROFILES].get(profile.id)
        if stored is None and self._index > 0:
            stored = self._data[CONF_PROFILES].get(profiles[self._index - 1].id)
        stored = stored or {}
        fields: dict[Any, Any] = {
            vol.Required(CONF_ACTIVE): selector.BooleanSelector(),
            vol.Required(CONF_ON_OFFSET): MINUTES,
            vol.Required(CONF_OFF_OFFSET): MINUTES,
        }
        current = setting_from(stored)
        first = current.spans[0] if current.spans else None
        plain = _plain(stored) and first is not None
        suggested: dict[str, Any] = {
            CONF_ACTIVE: current.active,
            CONF_ON_OFFSET: first.on.value if plain and first else 0,
            CONF_OFF_OFFSET: first.off.value if plain and first else 0,
        }
        if light:
            fields[vol.Optional(CONF_BRIGHTNESS)] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=100, step=1, mode=selector.NumberSelectorMode.SLIDER, unit_of_measurement="%"
                )
            )
            fields[vol.Optional(CONF_RAMP)] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=RAMP_LIMIT, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="min"
                )
            )
            if stored.get(CONF_BRIGHTNESS):
                suggested[CONF_BRIGHTNESS] = stored[CONF_BRIGHTNESS]
            suggested[CONF_RAMP] = stored.get(CONF_RAMP, 0)
        return self.async_show_form(
            step_id="profile",
            data_schema=self.add_suggested_values_to_schema(vol.Schema(fields), suggested),
            description_placeholders={
                "device": self._title,
                "profile": profile.name,
                "day_start": clock_of(profile.day_start),
                "day_end": clock_of(profile.day_end),
                "step": f"{self._index + 1}/{len(profiles)}",
            },
            last_step=self._index == len(profiles) - 1,
        )

    def _finish(self) -> SubentryFlowResult:
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_and_abort(
                self._get_entry(), self._get_reconfigure_subentry(), title=self._title, data=self._data
            )
        return self.async_create_entry(title=self._title, data=self._data)
