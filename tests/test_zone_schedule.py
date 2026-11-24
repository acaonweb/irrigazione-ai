"""Programmazione per zona: spenta, un giorno sì e uno no, giorni scelti, sempre."""

from __future__ import annotations

from datetime import date, timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    mock_restore_cache,
)

from custom_components.irrigazione_ai.calc import zone_irrigates_on
from custom_components.irrigazione_ai.const import DOMAIN

from .conftest import VALVE_1, VALVE_2, install_fake_valves, make_entry

Z1 = "select.secondo_piano_schedule"
Z2 = "select.sottotetto_schedule"


def test_zone_irrigates_on() -> None:
    """Regole dei giorni."""
    mon = date(2026, 11, 23)
    assert not zone_irrigates_on(mon, "off", ["mon"], None)
    assert zone_irrigates_on(mon, "daily", [], None)
    assert zone_irrigates_on(mon, "days", ["mon", "wed"], None)
    assert not zone_irrigates_on(mon + timedelta(days=1), "days", ["mon", "wed"], None)
    assert zone_irrigates_on(mon, "alternate", [], mon)
    assert not zone_irrigates_on(mon + timedelta(days=1), "alternate", [], mon)
    assert zone_irrigates_on(mon + timedelta(days=2), "alternate", [], mon)
    assert zone_irrigates_on(mon - timedelta(days=2), "alternate", [], mon)


async def _setup(hass: HomeAssistant, calls: list, entry=None, **options):
    await hass.config.async_set_time_zone("Europe/Rome")
    entry = entry or make_entry(**options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    install_fake_valves(hass, calls)
    return entry


async def test_migration_keeps_weekly_day(hass: HomeAssistant, valves) -> None:
    """La vecchia frequenza 'una volta a settimana' (lunedì) passa alle zone."""
    entry = make_entry(weekly_day="mon")
    entry.add_to_hass(hass)
    reg = er.async_get(hass)
    reg.async_get_or_create(
        "select", DOMAIN, f"{entry.entry_id}_frequency",
        suggested_object_id="irrigazione_frequency", config_entry=entry,
    )
    mock_restore_cache(hass, [State("select.irrigazione_frequency", "weekly")])
    await _setup(hass, valves, entry=entry)

    for zone in (Z1, Z2):
        state = hass.states.get(zone)
        assert state.state == "days"
        assert state.attributes["days"] == ["mon"]
    assert reg.async_get("select.irrigazione_frequency") is None
    for sub in entry.subentries.values():
        assert sub.data["schedule"] == "days" and sub.data["days"] == ["mon"]


async def test_migration_off_stays_off(hass: HomeAssistant, valves) -> None:
    """Frequenza spenta: zone spente."""
    entry = make_entry()
    entry.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "select", DOMAIN, f"{entry.entry_id}_frequency",
        suggested_object_id="irrigazione_frequency", config_entry=entry,
    )
    mock_restore_cache(hass, [State("select.irrigazione_frequency", "off")])
    await _setup(hass, valves, entry=entry)
    assert hass.states.get(Z1).state == "off"
    assert hass.states.get("sensor.irrigazione_next_run").state == "unknown"


async def test_set_days_without_reload(hass: HomeAssistant, valves) -> None:
    """Cambiare i giorni dalla card non ricarica l'integrazione."""
    entry = await _setup(hass, valves)
    controller = entry.runtime_data
    await hass.services.async_call(
        DOMAIN, "set_schedule",
        {"entity_id": Z1, "days": ["sun", "mon", "wed", "sat"]}, blocking=True,
    )
    await hass.async_block_till_done()
    assert entry.runtime_data is controller
    state = hass.states.get(Z1)
    assert state.state == "days"
    assert state.attributes["days"] == ["mon", "wed", "sat", "sun"]
    sub = next(s for s in entry.subentries.values() if s.title == "Secondo piano")
    assert sub.data["days"] == ["mon", "wed", "sat", "sun"]
    assert state.attributes["next_run"] is not None

    # Nessun giorno = zona spenta
    await hass.services.async_call(
        DOMAIN, "set_schedule", {"entity_id": Z1, "days": []}, blocking=True
    )
    assert hass.states.get(Z1).state == "off"
    assert hass.states.get(Z1).attributes["next_run"] is None
    assert entry.runtime_data is controller


async def test_alternate_starts_today(
    hass: HomeAssistant, valves, freezer: FrozenDateTimeFactory
) -> None:
    """Un giorno sì e uno no: oggi sì, domani no, dopodomani sì."""
    freezer.move_to("2026-11-24 08:00:00+00:00")  # martedì 09:00 a Roma
    entry = await _setup(hass, valves, start_mode="time", start_time="21:00:00")
    await hass.services.async_call(
        "select", "select_option", {"entity_id": Z1, "option": "alternate"}, blocking=True
    )
    await hass.services.async_call(
        "select", "select_option", {"entity_id": Z2, "option": "off"}, blocking=True
    )
    state = hass.states.get(Z1)
    assert state.attributes["alternate_from"] == "2026-11-24"
    controller = entry.runtime_data
    zone_id = next(z for z, c in controller.zones.items() if c.name == "Secondo piano")
    first = dt_util.as_local(controller.next_run(zone_id))
    assert (first.date(), first.hour) == (date(2026, 11, 24), 21)

    freezer.move_to("2026-11-24 21:00:00+00:00")  # 22:00, dopo il ciclo
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    nxt = dt_util.as_local(controller.next_run(zone_id))
    assert nxt.date() == date(2026, 11, 26)


async def test_scheduled_cycle_only_due_zones(
    hass: HomeAssistant, valves, freezer: FrozenDateTimeFactory
) -> None:
    """All'orario partono solo le zone in programma quel giorno."""
    freezer.move_to("2026-11-24 08:00:00+00:00")  # martedì
    await _setup(hass, valves, start_mode="time", start_time="21:00:00")
    await hass.services.async_call(
        DOMAIN, "set_schedule", {"entity_id": Z1, "days": ["tue"]}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN, "set_schedule", {"entity_id": Z2, "days": ["wed"]}, blocking=True
    )
    freezer.move_to("2026-11-24 20:00:00+00:00")  # 21:00 a Roma
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    opened = {c.data["entity_id"] for c in valves if c.service == "turn_on"}
    assert opened == {VALVE_1}
    assert VALVE_2 not in opened


async def test_manual_start_all_zones(hass: HomeAssistant, valves) -> None:
    """'Avvia ora' irriga le zone non spente, anche se oggi non sono in programma."""
    await _setup(hass, valves)
    await hass.services.async_call(
        DOMAIN, "set_schedule", {"entity_id": Z1, "days": ["wed"]}, blocking=True
    )
    await hass.services.async_call(
        "select", "select_option", {"entity_id": Z2, "option": "off"}, blocking=True
    )
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    opened = {c.data["entity_id"] for c in valves if c.service == "turn_on"}
    assert opened == {VALVE_1}
