"""Websocket API: list, subscribe and control."""

from __future__ import annotations

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant

from .conftest import local


async def test_subscribe_and_control(
    hass: HomeAssistant, hass_ws_client, freezer: FrozenDateTimeFactory, setup_biome
) -> None:
    # Log in before moving the clock, or the access token is not valid yet.
    client = await hass_ws_client(hass)
    freezer.move_to(local(2026, 11, 17, 12))
    for name in ("lamp1", "lamp2", "heat"):
        hass.states.async_set(f"switch.{name}", "on")
    biome = await setup_biome()

    await client.send_json_auto_id({"type": "cloudless_biome/biomes"})
    msg = await client.receive_json()
    assert msg["result"] == [{"entry_id": biome.entry.entry_id, "title": "Terrarium"}]

    await client.send_json_auto_id({"type": "cloudless_biome/subscribe", "entry_id": biome.entry.entry_id})
    assert (await client.receive_json())["success"]
    snap = (await client.receive_json())["event"]
    assert snap["dry_run"] is True
    assert snap["profile"]["name"] == "Winter"
    assert [d["name"] for d in snap["devices"]] == ["Lampe 1", "Lampe 2", "Heizung"]
    lamp2 = snap["devices"][1]
    assert lamp2["windows"][0]["start"].startswith("2026-11-17T09:15")
    assert lamp2["windows"][0]["end"].startswith("2026-11-17T18:45")

    await client.send_json_auto_id(
        {"type": "cloudless_biome/control", "entry_id": biome.entry.entry_id, "action": "pause", "value": True}
    )
    msgs = [await client.receive_json() for _ in range(2)]
    assert any(m.get("type") == "result" and m["success"] for m in msgs)
    assert biome.paused

    await client.send_json_auto_id({"type": "cloudless_biome/subscribe", "entry_id": "nope"})
    msg = await client.receive_json()
    assert msg["error"]["code"] == "not_found"


async def test_save_from_the_page(
    hass: HomeAssistant, hass_ws_client, freezer: FrozenDateTimeFactory, setup_biome
) -> None:
    from unittest.mock import patch

    client = await hass_ws_client(hass)
    freezer.move_to(local(2026, 11, 17, 12))
    for name in ("lamp1", "lamp2", "heat", "fogger"):
        hass.states.async_set(f"switch.{name}", "on")
    biome = await setup_biome()
    entry = biome.entry
    await client.send_json_auto_id({"type": "cloudless_biome/subscribe", "entry_id": entry.entry_id})
    await client.receive_json()
    config = (await client.receive_json())["event"]["config"]
    assert {p["name"] for p in config["profiles"]} == {"Winter", "Sommer"}

    # Rename lamp 1 and move it, drop the heater, add a fogger and a spring profile that copies winter.
    config["profiles"].append(
        {"id": "new1", "name": "Frühling", "day_start": "08:30", "day_end": "19:30", "copy_from": "winter"}
    )
    lamp1 = next(d for d in config["devices"] if d["id"] == "lamp1")
    lamp1["name"] = "Hauptlicht"
    lamp1["profiles"]["winter"]["spans"][0]["on"]["value"] = 30
    lamp1["profiles"]["new1"] = {"active": True, "on_offset": 5, "off_offset": 0}  # the older form still works
    config["devices"] = [d for d in config["devices"] if d["id"] != "heat"]
    config["devices"].append(
        {
            "id": "new2",
            "name": "Nebel",
            "entity_id": "switch.fogger",
            "kind": "rain",
            "max_on": 45,
            "profiles": {
                "winter": {
                    "spans": [
                        {
                            "on": {"ref": "clock", "value": "08:00"},
                            "off": {"ref": "clock", "value": "20:00"},
                            "every": 15,
                            "pulse": 30,
                        }
                    ]
                }
            },
        }
    )
    # The page sets the order: the fogger first.
    config["devices"].insert(0, config["devices"].pop())

    reloads = []
    real_reload = hass.config_entries.async_reload

    async def counting_reload(entry_id: str) -> bool:
        reloads.append(entry_id)
        return await real_reload(entry_id)

    with patch.object(hass.config_entries, "async_reload", counting_reload):
        await client.send_json_auto_id({"type": "cloudless_biome/save", "entry_id": entry.entry_id, "config": config})
        replies = [await client.receive_json() for _ in range(2)]
        await hass.async_block_till_done()
    assert any(r.get("event") == {"reload": True} for r in replies)
    assert any(r.get("type") == "result" and r["success"] for r in replies)
    assert reloads == [entry.entry_id]

    biome = entry.runtime_data
    names = {d.name for d in biome.devices}
    assert names == {"Hauptlicht", "Lampe 2", "Nebel"}
    spring = next(p for p in biome.profiles if p.name == "Frühling")
    assert spring.copy_from == "winter"
    main = next(d for d in biome.devices if d.name == "Hauptlicht")
    assert main.settings["winter"].spans[0].on.value == 30
    assert main.settings[spring.id].spans[0].on.value == 5
    fogger = next(d for d in biome.devices if d.name == "Nebel")
    assert fogger.kind == "rain"
    span = fogger.settings["winter"].spans[0]
    assert (span.on.ref, span.on.value, span.every, span.pulse) == ("clock", 480, 15, 30)
    assert fogger.limit(biome.settings) == 45
    assert [d.name for d in biome.devices] == ["Nebel", "Hauptlicht", "Lampe 2"]

    await client.send_json_auto_id(
        {"type": "cloudless_biome/notes", "entry_id": entry.entry_id, "text": "Bartagame: 35 °C"}
    )
    msg = await client.receive_json()
    while msg.get("type") != "result":
        msg = await client.receive_json()
    assert msg["success"]
    assert entry.runtime_data.notes == "Bartagame: 35 °C"

    # Invalid: the same entity twice.
    config = {
        "profiles": [{"id": "winter", "name": "W", "day_start": "09:00", "day_end": "19:00"}],
        "devices": [
            {"id": "a", "name": "A", "entity_id": "switch.lamp1"},
            {"id": "b", "name": "B", "entity_id": "switch.lamp1"},
        ],
    }
    await client.send_json_auto_id({"type": "cloudless_biome/save", "entry_id": entry.entry_id, "config": config})
    msg = await client.receive_json()
    while msg.get("type") != "result":
        msg = await client.receive_json()
    assert msg["error"]["code"] == "invalid"


async def test_full_log(hass: HomeAssistant, hass_ws_client, freezer: FrozenDateTimeFactory, setup_biome) -> None:
    client = await hass_ws_client(hass)
    freezer.move_to(local(2026, 11, 17, 12))
    biome = await setup_biome()
    biome.log("paused")
    biome.log("switched", biome.device("lamp1"), routine=True, state="on")
    await client.send_json_auto_id({"type": "cloudless_biome/log", "entry_id": biome.entry.entry_id})
    msg = await client.receive_json()
    kinds = [(i["kind"], i.get("routine", False)) for i in msg["result"]]
    assert ("paused", False) in kinds
    assert ("switched", True) in kinds
