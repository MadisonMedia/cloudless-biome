"""Back to the plan: drop manual overrides."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BiomeConfigEntry
from .biome import Biome
from .entity import BiomeDeviceEntity, BiomeEntity
from .model import Device


async def async_setup_entry(
    hass: HomeAssistant, entry: BiomeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up the buttons."""
    biome = entry.runtime_data
    async_add_entities([ResumeAllButton(biome)])
    for device in biome.devices:
        async_add_entities([ResumeButton(biome, device)], config_subentry_id=device.id)


class ResumeAllButton(BiomeEntity, ButtonEntity):
    """All devices follow the plan again."""

    _attr_icon = "mdi:calendar-refresh-outline"

    def __init__(self, biome: Biome) -> None:
        """Initialize."""
        super().__init__(biome, "resume_all")

    async def async_press(self) -> None:
        """Drop all overrides."""
        await self.biome.async_resume()


class ResumeButton(BiomeDeviceEntity, ButtonEntity):
    """The device follows the plan again."""

    _attr_icon = "mdi:calendar-refresh-outline"

    def __init__(self, biome: Biome, device: Device) -> None:
        """Initialize."""
        super().__init__(biome, device, "resume")

    async def async_press(self) -> None:
        """Drop the device's override."""
        await self.biome.async_resume(self.device.id)
