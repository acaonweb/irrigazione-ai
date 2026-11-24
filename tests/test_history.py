"""Test di storico (calendario) e consumi d'acqua."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.irrigazione_ai.const import DOMAIN

from .conftest import VALVE_1, WEATHER, install_fake_valves, make_entry

CAL = "calendar.irrigazione_irrigation_log"



async def _setup(hass: HomeAssistant, calls):
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    install_fake_valves(hass, calls)
    return entry


async def _events(hass: HomeAssistant, start, end) -> list[dict]:
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {"entity_id": CAL, "start_date_time": start, "end_date_time": end},
        blocking=True,
        return_response=True,
    )
    return response[CAL]["events"]


def _num(hass: HomeAssistant, entity_id: str) -> float:
    return float(hass.states.get(entity_id).state)


async def test_manual_opening_counts_water(hass: HomeAssistant, valves, freezer) -> None:
    """Valvola aperta a mano 10 minuti: 7,26 L ed evento nel registro."""
    t0 = dt_util.utcnow()
    await _setup(hass, valves)
    await hass.services.async_call("switch", "turn_on", {"entity_id": VALVE_1}, blocking=True)
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)  # conteggio periodico mentre è aperta
    await hass.async_block_till_done()
    assert 3.5 < _num(hass, "sensor.secondo_piano_water_today") < 3.8

    freezer.tick(timedelta(minutes=5))
    await hass.services.async_call("switch", "turn_off", {"entity_id": VALVE_1}, blocking=True)
    await hass.async_block_till_done()
    assert _num(hass, "sensor.secondo_piano_water_total") == 7.3
    assert _num(hass, "sensor.irrigazione_water_today") == 7.3

    events = await _events(hass, t0 - timedelta(hours=1), t0 + timedelta(hours=1))
    assert [e["summary"] for e in events if "Manual" in e["summary"]] == [
        "Manual opening: Secondo piano"
    ]
    assert "7.3 L" in events[0]["description"]


async def test_cycle_event_and_live_water(hass: HomeAssistant, valves, freezer, slow_zone_sleep) -> None:
    """Ciclo interrotto dopo 5 minuti: litri di entrambe le zone ed evento."""
    t0 = dt_util.utcnow()
    await _setup(hass, valves)
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    await hass.async_block_till_done()

    events = await _events(hass, t0 - timedelta(hours=1), t0 + timedelta(hours=3))
    assert any(e["summary"] == "Watering in progress" for e in events)

    freezer.tick(timedelta(minutes=5))
    await hass.services.async_call(DOMAIN, "stop", {}, blocking=True)
    await hass.async_block_till_done()

    # 2 zone x 5 min x 0,726 L/min = 7,26 L
    assert _num(hass, "sensor.irrigazione_water_today") == 7.3
    events = await _events(hass, t0 - timedelta(hours=1), t0 + timedelta(hours=3))
    cycle = [e for e in events if e["summary"].startswith("Watering (action)")]
    assert cycle[0]["summary"] == "Watering (action) (stopped)"
    assert "Secondo piano: 55 min, 3.6 L" in cycle[0]["description"]
    assert "Total: 7.3 L" in cycle[0]["description"]
    # Nessuna "apertura manuale" per le valvole aperte dal ciclo
    assert not [e for e in events if e["summary"].startswith("Manual opening")]


async def test_block_event(hass: HomeAssistant, valves) -> None:
    """Ciclo bloccato dalla pioggia: evento nel registro."""
    t0 = dt_util.utcnow()
    await _setup(hass, valves)
    hass.states.async_set(WEATHER, "rainy")
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    await hass.async_block_till_done()
    events = await _events(hass, t0 - timedelta(hours=1), t0 + timedelta(hours=1))
    assert "Watering skipped: rain" in [e["summary"] for e in events]


async def test_planned_event(hass: HomeAssistant, valves) -> None:
    """Il calendario mostra la prossima irrigazione prevista."""
    await _setup(hass, valves)
    await hass.services.async_call(
        "irrigazione_ai", "set_schedule",
        {"entity_id": "select.secondo_piano_schedule", "mode": "daily"}, blocking=True,
    )
    now = dt_util.utcnow()
    events = await _events(hass, now, now + timedelta(days=2))
    assert any(e["summary"] == "Planned watering" for e in events)


async def test_counters_persist_and_day_reset(hass: HomeAssistant, valves, freezer) -> None:
    """I litri restano dopo un riavvio; quelli di oggi si azzerano a mezzanotte."""
    entry = await _setup(hass, valves)
    await hass.services.async_call("switch", "turn_on", {"entity_id": VALVE_1}, blocking=True)
    freezer.tick(timedelta(minutes=10))
    await hass.services.async_call("switch", "turn_off", {"entity_id": VALVE_1}, blocking=True)
    await hass.async_block_till_done()
    assert _num(hass, "sensor.secondo_piano_water_total") == 7.3

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert _num(hass, "sensor.secondo_piano_water_total") == 7.3

    midnight = dt_util.start_of_local_day() + timedelta(days=1, seconds=5)
    freezer.move_to(midnight)
    async_fire_time_changed(hass, midnight)
    await hass.async_block_till_done()
    assert _num(hass, "sensor.secondo_piano_water_today") == 0
    assert _num(hass, "sensor.secondo_piano_water_total") == 7.3
