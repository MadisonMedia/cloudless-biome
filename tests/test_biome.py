"""The running biome: dry run, switching, manual overrides, unavailable devices, pause and profiles."""

from __future__ import annotations

from datetime import datetime, timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_time_changed, async_mock_service

from .conftest import local


async def _states(hass: HomeAssistant, **states: str) -> None:
    for name, state in states.items():
        hass.states.async_set(f"switch.{name}", state)
    await hass.async_block_till_done()


async def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: int = 1) -> None:
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_dry_run_switches_nothing(hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_biome) -> None:
    freezer.move_to(local(2026, 11, 17, 12))
    await _states(hass, lamp1="off", lamp2="on", heat="on")
    biome = await setup_biome()
    on = async_mock_service(hass, "switch", "turn_on")
    off = async_mock_service(hass, "switch", "turn_off")
    assert biome.dry_run
    await _tick(hass, freezer)
    assert not on and not off
    kinds = [(i["kind"], i.get("name"), i.get("state")) for i in biome.log_items]
    assert ("would_switch", "Lampe 1", "on") in kinds
    assert sum(1 for k in kinds if k[0] == "would_switch") == 1  # logged once, not every minute


async def test_live_restores_plan(hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_biome) -> None:
    freezer.move_to(local(2026, 11, 17, 12))
    await _states(hass, lamp1="off", lamp2="on", heat="on")
    biome = await setup_biome()
    on = async_mock_service(hass, "switch", "turn_on")
    off = async_mock_service(hass, "switch", "turn_off")
    await biome.async_set_dry_run(False)
    await hass.async_block_till_done()
    assert [c.data["entity_id"] for c in on] == ["switch.lamp1"]
    assert not off
    # Evening: lamp 2 goes off at 18:45, lamp 1 and the heater at 19:00.
    await _states(hass, lamp1="on")
    freezer.move_to(local(2026, 11, 17, 18, 44))
    await _tick(hass, freezer)
    assert [c.data["entity_id"] for c in off] == ["switch.lamp2"]


async def test_manual_switch_lasts_until_next_point(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_biome
) -> None:
    freezer.move_to(local(2026, 11, 17, 12))
    await _states(hass, lamp1="on", lamp2="on", heat="on")
    biome = await setup_biome()
    off = async_mock_service(hass, "switch", "turn_off")
    on = async_mock_service(hass, "switch", "turn_on")
    await biome.async_set_dry_run(False)
    hass.states.async_set("switch.lamp1", "off", context=Context(user_id="matt"))
    await _tick(hass, freezer, 5)
    assert not on
    status = biome.status(biome.device("lamp1"))
    assert status["reason"] == "manual"
    assert status["override"]["until"].startswith("2026-11-17T19:00")
    # The next switching point is 19:00 (off). After it, lamp 1 follows the plan again: off until 09:00.
    freezer.move_to(local(2026, 11, 18, 9, 0))
    await _tick(hass, freezer, 0)
    assert biome.status(biome.device("lamp1"))["reason"] == "plan"
    assert [c.data["entity_id"] for c in on] == ["switch.lamp1"]
    assert "switch.lamp1" not in [c.data["entity_id"] for c in off]


async def test_manual_never_restores_at_once(hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_biome) -> None:
    from .conftest import device, profile

    freezer.move_to(local(2026, 11, 17, 12))
    await _states(hass, lamp1="on")
    biome = await setup_biome(
        [
            profile("p", "Standard", "09:00", "19:00"),
            device("lamp1", "Lampe 1", "switch.lamp1", {"p": {"active": True}}, manual="never"),
        ]
    )
    on = async_mock_service(hass, "switch", "turn_on")
    async_mock_service(hass, "switch", "turn_off")
    await biome.async_set_dry_run(False)
    hass.states.async_set("switch.lamp1", "off", context=Context(user_id="matt"))
    await hass.async_block_till_done()
    assert [c.data["entity_id"] for c in on] == ["switch.lamp1"]


async def test_back_from_unavailable_is_corrected(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_biome
) -> None:
    freezer.move_to(local(2026, 11, 17, 12))
    await _states(hass, lamp1="on", lamp2="on", heat="on")
    biome = await setup_biome()
    on = async_mock_service(hass, "switch", "turn_on")
    async_mock_service(hass, "switch", "turn_off")
    await biome.async_set_dry_run(False)
    await _states(hass, lamp1="unavailable")
    assert biome.problems["lamp1"] == "unavailable"
    await _states(hass, lamp1="off")
    assert [c.data["entity_id"] for c in on] == ["switch.lamp1"]
    assert "lamp1" not in biome.problems


async def test_pause_and_failed_commands(hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_biome) -> None:
    freezer.move_to(local(2026, 11, 17, 12))
    await _states(hass, lamp1="off", lamp2="on", heat="on")
    biome = await setup_biome()
    on = async_mock_service(hass, "switch", "turn_on")
    async_mock_service(hass, "switch", "turn_off")
    await biome.async_set_paused(True)
    await biome.async_set_dry_run(False)
    await _tick(hass, freezer)
    assert not on
    await biome.async_set_paused(False)
    await hass.async_block_till_done()
    assert len(on) == 1
    # The mock does not change the state, so the command never takes.
    # Retries come a minute apart, not only with the check every 10 minutes.
    for _ in range(3):
        await _tick(hass, freezer, 1)
    assert biome.problems["lamp1"] == "failed"
    registry = er.async_get(hass)
    problem = next(e for e in registry.entities.values() if e.unique_id.endswith("lamp1_device_problem"))
    assert hass.states.get(problem.entity_id).state == "on"


async def test_profile_choice_and_entities(hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_biome) -> None:
    freezer.move_to(local(2026, 11, 17, 12))
    await _states(hass, lamp1="on", lamp2="on", heat="on")
    biome = await setup_biome()
    async_mock_service(hass, "switch", "turn_on")
    off = async_mock_service(hass, "switch", "turn_off")
    registry = er.async_get(hass)
    select = next(e for e in registry.entities.values() if e.unique_id.endswith("_profile"))
    assert hass.states.get(select.entity_id).state == "Winter"
    await biome.async_set_dry_run(False)
    await hass.services.async_call(
        "select", "select_option", {"entity_id": select.entity_id, "option": "Sommer"}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(select.entity_id).state == "Sommer"
    assert hass.states.get(select.entity_id).attributes["until"] == "2027-04-01"
    assert [c.data["entity_id"] for c in off] == ["switch.heat"]  # no heating in summer
    snapshot = biome.snapshot()
    assert snapshot["profile"]["manual"]
    assert {d["id"] for d in snapshot["devices"]} == {"lamp1", "lamp2", "heat"}


async def test_no_profile_switches_nothing(hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_biome) -> None:
    from .conftest import device

    freezer.move_to(local(2026, 11, 17, 12))
    await _states(hass, lamp1="on")
    biome = await setup_biome([device("lamp1", "Lampe 1", "switch.lamp1", {})])
    off = async_mock_service(hass, "switch", "turn_off")
    await biome.async_set_dry_run(False)
    await _tick(hass, freezer)
    assert not off


async def test_switches_on_time_between_checks(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_biome
) -> None:
    """The regular check runs every 10 minutes, but switching points come on the minute."""
    freezer.move_to(local(2026, 11, 17, 18, 41))
    await _states(hass, lamp1="on", lamp2="on", heat="on")
    biome = await setup_biome()
    off = async_mock_service(hass, "switch", "turn_off")
    await biome.async_set_dry_run(False)
    await hass.async_block_till_done()
    await _tick(hass, freezer, 3)  # 18:44
    assert not off
    await _tick(hass, freezer, 1)  # 18:45: lamp 2 goes off
    assert [c.data["entity_id"] for c in off] == ["switch.lamp2"]


async def test_max_on_switches_off_and_waits_for_the_next_window(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_biome
) -> None:
    """A rain device may stay on for 30 seconds by default, even when someone switches it on by hand."""
    from .conftest import device, profile

    freezer.move_to(local(2026, 11, 17, 12))
    await _states(hass, fogger="off")
    window = {"on": {"ref": "clock", "value": 600}, "off": {"ref": "clock", "value": 1080}}
    biome = await setup_biome(
        [
            profile("p", "Standard", "09:00", "19:00"),
            device("fogger", "Nebler", "switch.fogger", {"p": {"spans": [window]}}, kind="rain"),
        ]
    )
    off = async_mock_service(hass, "switch", "turn_off")
    on = async_mock_service(hass, "switch", "turn_on")
    await biome.async_set_dry_run(False)
    await hass.async_block_till_done()
    assert len(on) == 1  # the plan wants it on from 10:00 to 18:00
    hass.states.async_set("switch.fogger", "on", context=on[0].context)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert [c.data["entity_id"] for c in off] == ["switch.fogger"]
    assert biome.problems["fogger"] == "max_on"
    assert any(i["kind"] == "max_on" for i in biome.log_items)
    # It stays off for the rest of the window, also when the device has not reported yet.
    await _tick(hass, freezer, 10)
    assert len(on) == 1
    # Switching off that does not take is tried again within seconds.
    freezer.tick(timedelta(seconds=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(off) >= 2


async def test_dry_run_remembers_what_it_would_switch_across_a_reload(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_biome
) -> None:
    freezer.move_to(local(2026, 11, 17, 12))
    await _states(hass, lamp1="off", lamp2="on", heat="on")
    biome = await setup_biome()
    entry = biome.entry
    assert sum(1 for i in biome.log_items if i["kind"] == "would_switch") == 1
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert sum(1 for i in entry.runtime_data.log_items if i["kind"] == "would_switch") == 1


async def test_manual_switch_without_switching_point_ends(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_biome
) -> None:
    """A heat mat that runs around the clock and is switched off for cleaning comes back after the manual time."""
    from .conftest import device, profile

    freezer.move_to(local(2026, 11, 17, 12))
    await _states(hass, mat="on")
    biome = await setup_biome(
        [
            profile("p", "Standard", "09:00", "19:00"),
            device("mat", "Heizmatte", "switch.mat", {"p": {"mode": "always"}}, kind="heat"),
        ]
    )
    on = async_mock_service(hass, "switch", "turn_on")
    async_mock_service(hass, "switch", "turn_off")
    await biome.async_set_dry_run(False)
    hass.states.async_set("switch.mat", "off", context=Context(user_id="matt"))
    await hass.async_block_till_done()
    assert biome.overrides["mat"]["until"].startswith("2026-11-17T13:00")
    freezer.move_to(local(2026, 11, 17, 13, 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert [c.data["entity_id"] for c in on] == ["switch.mat"]


async def test_pause_still_cuts_off_after_the_longest_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_biome
) -> None:
    from .conftest import device, profile

    freezer.move_to(local(2026, 11, 17, 12))
    await _states(hass, fogger="off")
    biome = await setup_biome(
        [
            profile("p", "Standard", "09:00", "19:00"),
            device("fogger", "Nebler", "switch.fogger", {"p": {"active": False}}, kind="rain"),
        ]
    )
    off = async_mock_service(hass, "switch", "turn_off")
    await biome.async_set_dry_run(False)
    await biome.async_set_paused(True)
    hass.states.async_set("switch.fogger", "on", context=Context(user_id="matt"))
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert [c.data["entity_id"] for c in off] == ["switch.fogger"]


async def test_interval_switches_have_a_log_of_their_own(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_biome
) -> None:
    from .conftest import device, profile

    freezer.move_to(local(2026, 11, 17, 7, 59))
    await _states(hass, fogger="off")
    window = {"on": {"ref": "clock", "value": 480}, "off": {"ref": "clock", "value": 1200}, "every": 15, "pulse": 20}
    biome = await setup_biome(
        [
            profile("p", "Standard", "09:00", "19:00"),
            device("fogger", "Nebler", "switch.fogger", {"p": {"spans": [window]}}, kind="rain"),
        ]
    )
    on = async_mock_service(hass, "switch", "turn_on")
    off = async_mock_service(hass, "switch", "turn_off")
    await biome.async_set_dry_run(False)
    for _ in range(3):
        await _tick(hass, freezer, 1)
        if on:
            hass.states.async_set("switch.fogger", "on", context=on[-1].context)
            await hass.async_block_till_done()
        freezer.tick(timedelta(seconds=25))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        if off:
            hass.states.async_set("switch.fogger", "off", context=off[-1].context)
            await hass.async_block_till_done()
        freezer.move_to(local(2026, 11, 17, 8, 14 + 15 * _))
    assert not any(i["kind"] == "switched" for i in biome.log_items)
    assert any(i["kind"] == "switched" for i in biome.pulse_items)
    last = biome.snapshot()["pulse_log"]["fogger"]
    assert 1 <= len(last) <= 2
    assert all(i.get("routine") for i in biome.full_log() if i["kind"] == "switched")


async def test_longest_time_on_cuts_once_per_time_on(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, setup_biome
) -> None:
    """A device that does not follow, and one around the clock with a limit: no cutting off every second."""
    from .conftest import device, profile

    freezer.move_to(local(2026, 11, 17, 12))
    await _states(hass, stuck="on", mist="on")
    biome = await setup_biome(
        [
            profile("p", "Standard", "09:00", "19:00"),
            device("stuck", "Pumpe", "switch.stuck", {"p": {"active": False}}, kind="rain"),
            device("mist", "Nebel", "switch.mist", {"p": {"mode": "always"}}, kind="rain"),
        ]
    )
    off = async_mock_service(hass, "switch", "turn_off")
    on = async_mock_service(hass, "switch", "turn_on")
    await biome.async_set_dry_run(False)
    for _ in range(40):
        freezer.tick(timedelta(seconds=3))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    cuts = [i for i in biome.log_items if i["kind"] == "max_on"]
    assert sorted(i["name"] for i in cuts) == ["Nebel", "Pumpe"]
    assert not on  # around the clock, but off until midnight after the cut
    assert sum(1 for c in off if c.data["entity_id"] == "switch.stuck") <= 10  # retried, not every second
    assert biome.problems["mist"] in ("max_on", "failed")  # the mock does not follow
    assert datetime.fromisoformat(biome._cutoff["mist"].isoformat()) == local(2026, 11, 18, 0, 0)
