"""Pause and dry run of a biome."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BiomeConfigEntry
from .biome import Biome
from .entity import BiomeEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: BiomeConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up the switches."""
    biome = entry.runtime_data
    async_add_entities([PausedSwitch(biome), DryRunSwitch(biome)])


class PausedSwitch(BiomeEntity, SwitchEntity):
    """On: Biome switches nothing, devices stay as they are."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, biome: Biome) -> None:
        """Initialize."""
        super().__init__(biome, "paused")

    @property
    def is_on(self) -> bool:
        """Return whether the biome is paused."""
        return self.biome.paused

    @property
    def icon(self) -> str:
        """Return an icon."""
        return "mdi:pause-circle" if self.biome.paused else "mdi:play-circle-outline"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Pause."""
        await self.biome.async_set_paused(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Resume."""
        await self.biome.async_set_paused(False)


class DryRunSwitch(BiomeEntity, SwitchEntity):
    """On: Biome only shows and logs what it would switch."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, biome: Biome) -> None:
        """Initialize."""
        super().__init__(biome, "dry_run")

    @property
    def is_on(self) -> bool:
        """Return whether the biome runs dry."""
        return self.biome.dry_run

    @property
    def icon(self) -> str:
        """Return an icon."""
        return "mdi:test-tube" if self.biome.dry_run else "mdi:test-tube-off"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start a dry run."""
        await self.biome.async_set_dry_run(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Let Biome switch."""
        await self.biome.async_set_dry_run(False)
