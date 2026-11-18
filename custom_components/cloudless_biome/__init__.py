"""Cloudless Biome: time control for terrariums, greenhouses and other biomes."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .biome import Biome
from .const import DOMAIN, PANEL_URL, STORAGE_VERSION
from .edit import DATA_SAVING, fingerprint
from .frontend import async_register_frontend
from .websocket_api import async_register_websocket_commands

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SELECT, Platform.SENSOR, Platform.SWITCH]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type BiomeConfigEntry = ConfigEntry[Biome]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the websocket API and the Biome page."""
    async_register_websocket_commands(hass)
    await async_register_frontend(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BiomeConfigEntry) -> bool:
    """Set up a biome."""
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Cloudless",
        model="Biome",
        entry_type=dr.DeviceEntryType.SERVICE,
        configuration_url=f"homeassistant://{PANEL_URL}",
    )
    biome = Biome(hass, entry, device.id)
    entry.runtime_data = biome
    await biome.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BiomeConfigEntry) -> bool:
    """Unload a biome."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete what a biome stored."""
    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()


async def _async_entry_updated(hass: HomeAssistant, entry: BiomeConfigEntry) -> None:
    """Profiles or devices changed: start over with the new settings. Overrides and the log are kept.

    The Biome page saves many subentries at once and reloads once at the end, so it is skipped here.
    """
    if entry.entry_id in hass.data.get(DATA_SAVING, ()):
        return
    biome = getattr(entry, "runtime_data", None)
    if biome is not None and biome.fingerprint == fingerprint(entry):
        return
    await hass.config_entries.async_reload(entry.entry_id)
