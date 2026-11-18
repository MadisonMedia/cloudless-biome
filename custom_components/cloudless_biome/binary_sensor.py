"""A problem sensor per device: unreachable, or a command that does not take."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BiomeConfigEntry
from .biome import Biome
from .entity import BiomeDeviceEntity
from .model import Device


async def async_setup_entry(
    hass: HomeAssistant, entry: BiomeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up a problem sensor per device."""
    biome = entry.runtime_data
    for device in biome.devices:
        async_add_entities([DeviceProblemSensor(biome, device)], config_subentry_id=device.id)


class DeviceProblemSensor(BiomeDeviceEntity, BinarySensorEntity):
    """On when the device cannot be reached or does not follow."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, biome: Biome, device: Device) -> None:
        """Initialize."""
        super().__init__(biome, device, "device_problem")

    @property
    def is_on(self) -> bool:
        """Return whether there is a problem."""
        return self.device.id in self.biome.problems

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """What the problem is: missing, unavailable or failed."""
        return {"entity": self.device.entity_id, "problem": self.biome.problems.get(self.device.id)}
