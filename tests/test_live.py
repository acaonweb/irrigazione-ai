"""Test di Live Activity / Live Update, card e mappa delle entità."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.irrigazione_ai.const import DOMAIN

from .conftest import VALVE_1, install_fake_valves, make_entry


async def _setup(hass: HomeAssistant, calls):
    pushes: list[ServiceCall] = []

    async def _push(call: ServiceCall) -> None:
        pushes.append(call)

    hass.services.async_register("notify", "mobile_app_iphone", _push)
    entry = make_entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            "live_devices": ["notify.mobile_app_iphone"],
            "live_url": "/lovelace/irrigazione",
        },
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    install_fake_valves(hass, calls)
    return entry, pushes


async def test_cycle_live_activity(hass: HomeAssistant, valves, freezer) -> None:
    """Avvio con suono, fine con riepilogo, chiusura dopo 5 minuti."""
    entry, pushes = await _setup(hass, valves)
    await hass.services.async_call(DOMAIN, "start", {"duration": 1}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    first = pushes[0].data
    assert first["title"] == "💧 Watering"
    assert "1️⃣ Secondo piano · ends" in first["message"]
    assert "2️⃣ Sottotetto · ends" in first["message"]
    assert first["data"]["live_update"] is True
    assert first["data"]["silent"] is False
    assert first["data"]["url"] == "/lovelace/irrigazione"
    tag = first["data"]["tag"]

    last = pushes[-1].data
    assert last["title"] == "☑️ Watering finished"
    assert "Total" in last["message"]
    assert last["data"]["tag"] == tag
    # aggiornamenti intermedi silenziosi
    assert all(p.data["data"]["silent"] for p in pushes[1:-1])

    freezer.tick(timedelta(minutes=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert pushes[-1].data["message"] == "clear_notification"
    assert pushes[-1].data["data"]["tag"] == tag


async def test_manual_live_activity(hass: HomeAssistant, valves, freezer) -> None:
    """Apertura manuale: attività con ora di chiusura di sicurezza."""
    _entry, pushes = await _setup(hass, valves)
    await hass.services.async_call("switch", "turn_on", {"entity_id": VALVE_1}, blocking=True)
    await hass.async_block_till_done()
    assert pushes[0].data["title"] == "💧 Valve open"
    assert "opened by hand · closes" in pushes[0].data["message"]

    freezer.tick(timedelta(minutes=10))
    await hass.services.async_call("switch", "turn_off", {"entity_id": VALVE_1}, blocking=True)
    await hass.async_block_till_done()
    assert pushes[-1].data["title"] == "☑️ Watering finished"
    assert "Secondo piano · 10 min · 7.3 L" in pushes[-1].data["message"]


async def test_no_devices_no_push(hass: HomeAssistant, valves) -> None:
    """Senza dispositivi configurati non parte nessuna Live Activity."""
    pushes: list[ServiceCall] = []
    hass.services.async_register("notify", "mobile_app_iphone", lambda c: pushes.append(c))
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    install_fake_valves(hass, valves)
    await hass.services.async_call(DOMAIN, "start", {"duration": 1}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert pushes == []


async def test_card_entity_map(hass: HomeAssistant, valves) -> None:
    """Il sensore Stato espone le entità per la card."""
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    card = hass.states.get("sensor.irrigazione_status").attributes["card"]
    assert card["system"]["irrigation"] == "switch.irrigazione"
    assert card["system"]["calendar"] == "calendar.irrigazione_irrigation_log"
    assert card["zones"][0]["valve"] == VALVE_1
    assert card["zones"][0]["duration"] == "sensor.secondo_piano_planned_duration"


async def test_cycle_event_summary(hass, valves) -> None:
    """Avvio da azione: titolo dell'evento e testi della Live Activity."""
    entry, pushes = await _setup(hass, valves)
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert pushes[0].data["title"] == "💧 Watering"
    assert pushes[-1].data["title"] == "☑️ Watering finished"
    assert "Total" in pushes[-1].data["message"]
    assert entry.runtime_data.history.events[-1].summary == "Watering (action)"
