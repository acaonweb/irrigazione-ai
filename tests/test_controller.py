"""Test del motore di irrigazione."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.irrigazione_ai.const import DOMAIN

from .conftest import VALVE_1, VALVE_2, WEATHER, install_fake_valves, make_entry


async def _setup(hass: HomeAssistant, calls=None, **kwargs):
    entry = make_entry(**kwargs)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    install_fake_valves(hass, calls if calls is not None else [])
    return entry


def _entity(hass: HomeAssistant, domain: str, suffix: str) -> str:
    ids = [e for e in hass.states.async_entity_ids(domain) if e.endswith(suffix)]
    assert ids, f"nessuna entità {domain}.*{suffix}"
    return ids[0]


async def test_entities_created(hass: HomeAssistant, valves) -> None:
    """Entità dell'impianto e delle zone."""
    await _setup(hass, valves)
    assert hass.states.get("switch.irrigazione").state == "off"
    assert hass.states.get("switch.irrigazione_rain_block").state == "on"
    assert hass.states.get("select.irrigazione_frequency").state == "twice_weekly"
    assert hass.states.get("sensor.irrigazione_status").state == "idle"
    # u=50, T=20, sunny -> 50.4*1.1 = 55.4 -> 55
    assert hass.states.get("sensor.secondo_piano_planned_duration").state == "55"
    assert hass.states.get("sensor.irrigazione_next_run") is not None


async def test_full_cycle_parallel(hass: HomeAssistant, valves) -> None:
    """Ciclo completo: le valvole si aprono e si richiudono."""
    entry = await _setup(hass, valves)
    await hass.services.async_call(DOMAIN, "start", {"duration": 1}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(VALVE_1).state == "off"
    assert hass.states.get(VALVE_2).state == "off"
    opened = [c for c in valves if c.service == "turn_on"]
    assert {c.data["entity_id"] for c in opened} == {VALVE_1, VALVE_2}
    assert entry.runtime_data.running is False
    assert entry.runtime_data.last_run_end is not None


async def test_stop_closes_valves(hass: HomeAssistant, valves, slow_zone_sleep) -> None:
    """Fermando il ciclo le valvole si chiudono."""
    entry = await _setup(hass, valves)
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(VALVE_1).state == "on"
    assert hass.states.get(VALVE_2).state == "on"
    assert hass.states.get("switch.irrigazione").state == "on"
    assert int(hass.states.get("sensor.irrigazione_time_remaining").state) > 0

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.irrigazione"}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(VALVE_1).state == "off"
    assert hass.states.get(VALVE_2).state == "off"
    assert entry.runtime_data.running is False


async def test_sequential(hass: HomeAssistant, valves, slow_zone_sleep) -> None:
    """In sequenza si apre una zona alla volta."""
    entry = await _setup(hass, valves, run_mode="sequential")
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(VALVE_1).state == "on"
    assert hass.states.get(VALVE_2).state == "off"
    await entry.runtime_data.async_stop()
    await hass.async_block_till_done()
    assert hass.states.get(VALVE_1).state == "off"


async def test_rain_block(hass: HomeAssistant, valves) -> None:
    """Con pioggia e blocco attivo non parte; con force sì."""
    entry = await _setup(hass, valves)
    hass.states.async_set(WEATHER, "rainy", {"temperature": 10})
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    await hass.async_block_till_done()
    assert not [c for c in valves if c.service == "turn_on"]
    assert hass.states.get("sensor.irrigazione_status").state == "blocked"
    assert entry.runtime_data.last_block == "rain"

    await hass.services.async_call(DOMAIN, "start", {"force": True}, blocking=True)
    await hass.async_block_till_done()
    assert [c for c in valves if c.service == "turn_on"]


async def test_rain_block_disabled(hass: HomeAssistant, valves) -> None:
    """Blocco pioggia spento: parte anche con pioggia."""
    await _setup(hass, valves)
    hass.states.async_set(WEATHER, "rainy", {"temperature": 10})
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.irrigazione_rain_block"}, blocking=True
    )
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    await hass.async_block_till_done()
    assert [c for c in valves if c.service == "turn_on"]


async def test_manual_timer(hass: HomeAssistant, valves) -> None:
    """Il timer manuale sostituisce la formula."""
    entry = await _setup(hass, valves)
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.irrigazione_manual_timer", "option": "30"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.secondo_piano_planned_duration").state == "30"
    zone = next(iter(entry.runtime_data.zones.values()))
    assert entry.runtime_data.planned_minutes(zone) == 30


async def test_safety_close_manual_open(hass: HomeAssistant, valves) -> None:
    """Valvola aperta a mano: si chiude dopo i minuti di sicurezza."""
    await _setup(hass, valves, safety=60)
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": VALVE_1}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(VALVE_1).state == "on"

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=61))
    await hass.async_block_till_done()
    assert hass.states.get(VALVE_1).state == "off"


async def test_unload_closes_valves(hass: HomeAssistant, valves, slow_zone_sleep) -> None:
    """Scaricando l'integrazione durante un ciclo le valvole si chiudono."""
    entry = await _setup(hass, valves)
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(VALVE_1).state == "on"
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(VALVE_1).state == "off"
