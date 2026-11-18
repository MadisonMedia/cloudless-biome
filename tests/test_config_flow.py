"""Config flow: a biome with its first profile; profiles and devices as subentries."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from custom_components.cloudless_biome.const import DOMAIN, SUBENTRY_DEVICE, SUBENTRY_PROFILE


async def _create(hass: HomeAssistant):
    await async_setup_component(hass, "http", {})
    await async_setup_component(hass, "websocket_api", {})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "Terrarium", "profile_name": "Winter", "day_start": "09:00", "day_end": "09:00"},
    )
    assert result["errors"] == {"base": "same_times"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": " Terrarium ", "profile_name": "Winter", "day_start": "09:00:00", "day_end": "19:00:00"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return hass.config_entries.async_entries(DOMAIN)[0]


async def test_create_setup_unload(hass: HomeAssistant) -> None:
    entry = await _create(hass)
    assert entry.title == "Terrarium"
    (profile,) = entry.subentries.values()
    assert profile.subentry_type == SUBENTRY_PROFILE
    assert dict(profile.data) == {"day_start": "09:00", "day_end": "19:00", "start_date": None, "transition": 0}
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert entry.runtime_data.dry_run
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED


async def test_add_profile_and_device(hass: HomeAssistant) -> None:
    entry = await _create(hass)
    winter = next(iter(entry.subentries))
    hass.states.async_set("switch.lamp1", "off", {"friendly_name": "Lampe 1"})

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_PROFILE), context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "profile_name": "Sommer",
            "day_start": "08:00:00",
            "day_end": "20:00:00",
            "start_date": "2026-04-01",
            "transition": 14,
            "copy_from": winter,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    summer = next(s for s in entry.subentries.values() if s.title == "Sommer")
    assert summer.data["start_date"] == "04-01"
    assert summer.data["transition"] == 14
    assert summer.data["copy_from"] == winter

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_DEVICE), context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"entity_id": "switch.lamp1", "kind": "light", "manual": "next", "manual_minutes": 60}
    )
    assert result["step_id"] == "profile"
    assert "brightness" not in str(result["data_schema"].schema)
    # Profiles with a start date come first: Sommer (1 Apr), then Winter (1 Nov).
    assert result["description_placeholders"]["profile"] == "Sommer"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"active": True, "on_offset": 15, "off_offset": -15}
    )
    assert result["description_placeholders"]["profile"] == "Winter"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"active": False, "on_offset": 0, "off_offset": 0}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    lamp = next(s for s in entry.subentries.values() if s.subentry_type == SUBENTRY_DEVICE)
    assert lamp.title == "Lampe 1"
    assert lamp.data["profiles"][summer.subentry_id]["spans"][0]["on"] == {"ref": "start", "value": 15}
    assert lamp.data["profiles"][winter]["active"] is False
    assert entry.runtime_data.device(lamp.subentry_id) is not None

    # The same entity cannot be added twice.
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_DEVICE), context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"entity_id": "switch.lamp1", "kind": "light", "manual": "next"}
    )
    assert result["errors"] == {"entity_id": "already_used"}

    # After pairing again the entity has a new id: change it in place.
    hass.states.async_set("switch.lamp1_2", "off")
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_DEVICE),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": lamp.subentry_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"entity_id": "switch.lamp1_2", "name": "Lampe 1", "kind": "light", "manual": "next"}
    )
    for values in (
        {"active": True, "on_offset": 15, "off_offset": -15},
        {"active": False, "on_offset": 0, "off_offset": 0},
    ):
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], values)
    assert result["type"] is FlowResultType.ABORT
    await hass.async_block_till_done()
    lamp = entry.subentries[lamp.subentry_id]
    assert lamp.data["entity_id"] == "switch.lamp1_2"
    assert lamp.data["profiles"][summer.subentry_id]["spans"][0]["on"] == {"ref": "start", "value": 15}
