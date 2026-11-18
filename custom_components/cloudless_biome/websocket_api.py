"""Websocket API for the Biome page and, later, the card."""

from __future__ import annotations

import json
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
import voluptuous as vol

from .biome import Biome
from .const import DOMAIN, NOTES_LIMIT
from .edit import async_save_config


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register all commands."""
    for command in (ws_biomes, ws_subscribe, ws_control, ws_save, ws_notes, ws_log):
        websocket_api.async_register_command(hass, command)


def _biomes(hass: HomeAssistant) -> list[Biome]:
    biomes = [e.runtime_data for e in hass.config_entries.async_loaded_entries(DOMAIN)]
    return sorted(biomes, key=lambda b: b.title.casefold())


def _biome(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> Biome | None:
    biome = next((b for b in _biomes(hass) if b.entry.entry_id == msg["entry_id"]), None)
    if biome is None:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Biome not found")
    return biome


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/biomes"})
@callback
def ws_biomes(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """List the biomes."""
    connection.send_result(msg["id"], [{"entry_id": b.entry.entry_id, "title": b.title} for b in _biomes(hass)])


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe", vol.Required("entry_id"): str})
@callback
def ws_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Send the biome's state now and after every change."""
    biome = _biome(hass, connection, msg)
    if biome is None:
        return
    last = [""]

    @callback
    def send() -> None:
        snapshot = biome.snapshot()
        fingerprint = json.dumps({k: v for k, v in snapshot.items() if k != "now"}, sort_keys=True, default=str)
        if fingerprint == last[0]:
            return
        last[0] = fingerprint
        connection.send_message(websocket_api.event_message(msg["id"], snapshot))

    @callback
    def stopped() -> None:
        # The biome reloads, for example with new settings: the page subscribes again.
        connection.send_message(websocket_api.event_message(msg["id"], {"reload": True}))

    remove_listener = biome.async_add_listener(send)
    remove_stop = biome.async_on_stop(stopped)

    @callback
    def unsubscribe() -> None:
        remove_listener()
        remove_stop()

    connection.subscriptions[msg["id"]] = unsubscribe
    connection.send_result(msg["id"])
    send()


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/control",
        vol.Required("entry_id"): str,
        vol.Required("action"): vol.In(("pause", "dry_run", "profile", "resume")),
        vol.Optional("value"): vol.Any(bool, str, None),
        vol.Optional("device"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_control(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Pause, dry run, choose a profile, or go back to the plan."""
    biome = _biome(hass, connection, msg)
    if biome is None:
        return
    action, value = msg["action"], msg.get("value")
    if action == "pause":
        await biome.async_set_paused(bool(value))
    elif action == "dry_run":
        await biome.async_set_dry_run(bool(value))
    elif action == "profile":
        await biome.async_set_profile(value if isinstance(value, str) else None)
    else:
        await biome.async_resume(msg.get("device"))
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/save",
        vol.Required("entry_id"): str,
        vol.Required("config"): dict,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_save(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Save profiles and devices from the page. The biome reloads once."""
    biome = _biome(hass, connection, msg)
    if biome is None:
        return
    try:
        await async_save_config(hass, biome.entry, msg["config"])
    except vol.Invalid as err:
        connection.send_error(msg["id"], "invalid", str(err))
        return
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/notes",
        vol.Required("entry_id"): str,
        vol.Required("text"): vol.All(str, vol.Length(max=NOTES_LIMIT)),
    }
)
@websocket_api.require_admin
@callback
def ws_notes(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Store the biome's notes."""
    biome = _biome(hass, connection, msg)
    if biome is None:
        return
    biome.async_set_notes(msg["text"])
    connection.send_result(msg["id"])


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/log", vol.Required("entry_id"): str})
@callback
def ws_log(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Return the whole log, interval switches included."""
    biome = _biome(hass, connection, msg)
    if biome is None:
        return
    connection.send_result(msg["id"], biome.full_log())
