"""The biome's next switching point and day phase, and each device's status."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import BiomeConfigEntry
from .biome import Biome
from .entity import BiomeDeviceEntity, BiomeEntity
from .model import Device

STATUS_OPTIONS = ("on", "off", "manual_on", "manual_off", "inactive")


async def async_setup_entry(
    hass: HomeAssistant, entry: BiomeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up the sensors."""
    biome = entry.runtime_data
    async_add_entities([NextSwitchSensor(biome), PhaseSensor(biome)])
    for device in biome.devices:
        async_add_entities([DeviceStatusSensor(biome, device)], config_subentry_id=device.id)


class NextSwitchSensor(BiomeEntity, SensorEntity):
    """When the plan switches a device next."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-outline"

    def __init__(self, biome: Biome) -> None:
        """Initialize."""
        super().__init__(biome, "next_switch")

    @property
    def native_value(self) -> datetime | None:
        """Return the next switching point."""
        nxt = self.biome.next_switch()
        return nxt[0] if nxt else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Which device switches, and to what."""
        nxt = self.biome.next_switch()
        if nxt is None:
            return {}
        return {"device": nxt[1].name, "entity": nxt[1].entity_id, "to": "on" if nxt[2] else "off"}


class PhaseSensor(BiomeEntity, SensorEntity):
    """Day or night in the biome."""

    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(self, biome: Biome) -> None:
        """Initialize."""
        super().__init__(biome, "phase")
        self._attr_options = ["day", "night"]

    @property
    def native_value(self) -> str:
        """Return day or night."""
        return "day" if self.biome.plan.is_day(dt_util.now()) else "night"

    @property
    def icon(self) -> str:
        """Return a sun or a moon."""
        return "mdi:white-balance-sunny" if self.native_value == "day" else "mdi:weather-night"


class DeviceStatusSensor(BiomeDeviceEntity, SensorEntity):
    """What the device should do, and why."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_name = None

    def __init__(self, biome: Biome, device: Device) -> None:
        """Initialize."""
        super().__init__(biome, device, "device_status")
        self._attr_options = list(STATUS_OPTIONS)

    @property
    def native_value(self) -> str:
        """Return the status."""
        status = self.status()
        if status["reason"] == "inactive":
            return "inactive"
        state = "on" if status["on"] else "off"
        return f"manual_{state}" if status["reason"] == "manual" else state

    @property
    def icon(self) -> str:
        """Return the icon of the device's kind."""
        return self.kind_icon

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The device, the next switching point and a manual override."""
        status = self.status()
        override = status["override"] or {}
        return {
            "entity": self.device.entity_id,
            "next_change": status["next_change"],
            "next_state": status["next_state"],
            "manual_until": override.get("until"),
            "brightness": status["brightness"],
        }
