"""Shared base of a biome's entities."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .biome import Biome
from .const import DOMAIN, KIND_ICONS, PANEL_URL
from .model import Device


def device_info(biome: Biome) -> DeviceInfo:
    """Return the device that stands for a biome."""
    return DeviceInfo(
        identifiers={(DOMAIN, biome.entry.entry_id)},
        name=biome.title,
        manufacturer="Cloudless",
        model="Biome",
        entry_type=DeviceEntryType.SERVICE,
        configuration_url=f"homeassistant://{PANEL_URL}",
    )


class BiomeEntity(Entity):
    """An entity that follows its biome."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, biome: Biome, key: str) -> None:
        """Initialize."""
        self.biome = biome
        self._attr_unique_id = f"{biome.entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = device_info(biome)

    async def async_added_to_hass(self) -> None:
        """Follow the biome."""
        self.async_on_remove(self.biome.async_add_listener(self._biome_changed))

    def _biome_changed(self) -> None:
        if self.hass is not None and self.entity_id and self._state_differs():
            self.async_write_ha_state()

    def _state_differs(self) -> bool:
        """Write the state only when something visible changed."""
        fingerprint = (
            self.state,
            sorted((self.extra_state_attributes or {}).items(), key=str),
            self.icon,
            getattr(self, "options", None),
        )
        if fingerprint == getattr(self, "_last_fingerprint", None):
            return False
        self._last_fingerprint = fingerprint
        return True


class BiomeDeviceEntity(BiomeEntity):
    """An entity for one of the biome's devices."""

    def __init__(self, biome: Biome, device: Device, key: str) -> None:
        """Initialize."""
        super().__init__(biome, f"{device.id}_{key}")
        self.device = device
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{biome.entry.entry_id}_{device.id}")},
            name=device.name,
            manufacturer="Cloudless",
            model="Biome",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=f"homeassistant://{PANEL_URL}",
        )

    @property
    def kind_icon(self) -> str:
        """Return the icon of the device's kind."""
        return KIND_ICONS.get(self.device.kind, KIND_ICONS["other"])

    def status(self) -> dict[str, Any]:
        """Return the device's status."""
        return self.biome.status(self.device)
