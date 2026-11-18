"""Fixtures for Cloudless Biome: a terrarium in Berlin with fake switches."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cloudless_biome.const import DOMAIN, SUBENTRY_DEVICE, SUBENTRY_PROFILE

pytest_plugins = "pytest_homeassistant_custom_component"

TZ = ZoneInfo("Europe/Berlin")


@pytest.fixture(autouse=True)
def _enable(enable_custom_integrations: None) -> None:
    """Allow the custom integration to load."""


@pytest.fixture(autouse=True)
def _no_frontend(hass: HomeAssistant):
    """The page is not needed in the tests."""
    for component in ("frontend", "panel_custom"):
        hass.config.components.add(component)
    with patch("custom_components.cloudless_biome.async_register_frontend", return_value=None):
        yield


def local(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=TZ)


def profile(pid: str, title: str, start: str, end: str, date: str | None = None) -> ConfigSubentryData:
    return ConfigSubentryData(
        subentry_id=pid,
        subentry_type=SUBENTRY_PROFILE,
        title=title,
        data={"day_start": start, "day_end": end, "start_date": date},
        unique_id=None,
    )


def device(did: str, title: str, entity_id: str, profiles: dict[str, Any], **extra: Any) -> ConfigSubentryData:
    return ConfigSubentryData(
        subentry_id=did,
        subentry_type=SUBENTRY_DEVICE,
        title=title,
        data={
            "entity_id": entity_id,
            "kind": "light",
            "manual": "next",
            "manual_minutes": 60,
            "profiles": profiles,
            **extra,
        },
        unique_id=None,
    )


def terrarium_subentries() -> list[ConfigSubentryData]:
    """Winter from 1 Nov 09:00-19:00, summer from 1 Apr 08:00-20:00; three devices."""
    return [
        profile("winter", "Winter", "09:00", "19:00", "11-01"),
        profile("summer", "Sommer", "08:00", "20:00", "04-01"),
        device(
            "lamp1",
            "Lampe 1",
            "switch.lamp1",
            {"winter": {"active": True, "on_offset": 0, "off_offset": 0}, "summer": {"active": True}},
        ),
        device(
            "lamp2",
            "Lampe 2",
            "switch.lamp2",
            {
                "winter": {"active": True, "on_offset": 15, "off_offset": -15},
                "summer": {"active": True, "on_offset": 15, "off_offset": -15},
            },
        ),
        device(
            "heat",
            "Heizung",
            "switch.heat",
            {"winter": {"active": True, "on_offset": -30, "off_offset": 0}, "summer": {"active": False}},
            kind="heat",
        ),
    ]


@pytest.fixture
async def setup_biome(hass: HomeAssistant):
    """Return a helper that sets up a biome and returns it."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    await async_setup_component(hass, "homeassistant", {})
    await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "websocket_api", {})

    async def _setup(subentries: list[ConfigSubentryData] | None = None, title: str = "Terrarium"):
        entry = MockConfigEntry(
            domain=DOMAIN,
            title=title,
            data={},
            subentries_data=terrarium_subentries() if subentries is None else subentries,
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry.runtime_data

    return _setup
