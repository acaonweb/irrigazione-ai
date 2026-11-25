"""Autoapprendimento per zona."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.irrigazione_ai.const import (
    CONF_ZONE_LEARNING,
    DOMAIN,
    LEARN_WINDOW,
)
from custom_components.irrigazione_ai.learning import apply_factor, next_factor

from .conftest import MOISTURE_1, WEATHER, install_fake_valves, make_entry


@pytest.mark.parametrize(
    ("peak", "expected"),
    [(60, 1.0), (57, 1.0), (40, 1.15), (50, 1.1), (75, 0.85), (68, 0.92)],
)
def test_next_factor(peak, expected) -> None:
    """Dentro la tolleranza non cambia; il passo massimo è 15%."""
    factor, _change = next_factor(1.0, peak, 60)
    assert factor == pytest.approx(expected)


def test_factor_limits() -> None:
    """Il fattore resta fra 0,5 e 2."""
    assert next_factor(1.95, 10, 60)[0] == 2.0
    assert next_factor(0.52, 95, 60)[0] == 0.5


def test_apply_factor() -> None:
    """Minuti corretti e sempre fra minimo e massimo; 0 resta 0."""
    assert apply_factor(30, 1.2, 15, 120) == 36
    assert apply_factor(20, 0.5, 15, 120) == 15
    assert apply_factor(100, 1.5, 15, 120) == 120
    assert apply_factor(0, 1.5, 15, 120) == 0


async def _setup(hass: HomeAssistant, calls: list, learning: bool = True):
    entry = make_entry()
    entry.add_to_hass(hass)
    sub_id = next(iter(entry.subentries))
    sub = entry.subentries[sub_id]
    hass.config_entries.async_update_subentry(
        entry, sub, data={**sub.data, CONF_ZONE_LEARNING: learning}
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    install_fake_valves(hass, calls)
    return entry, sub_id


async def _cycle(hass: HomeAssistant) -> None:
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)


def _window_passes(hass: HomeAssistant) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=LEARN_WINDOW + 5))


async def test_low_peak_raises_factor(hass: HomeAssistant, valves) -> None:
    """Il terriccio arriva solo al 45%: la prossima volta più acqua."""
    hass.states.async_set(MOISTURE_1, "30")
    entry, zone_id = await _setup(hass, valves)
    controller = entry.runtime_data
    zone = controller.zones[zone_id]
    before = controller.planned_minutes(zone)
    await _cycle(hass)
    assert controller.observing(zone_id)
    hass.states.async_set(MOISTURE_1, "45")
    hass.states.async_set(MOISTURE_1, "42")
    _window_passes(hass)
    await hass.async_block_till_done()
    assert not controller.observing(zone_id)
    data = controller.learning.zones[zone_id]
    assert data.last_peak == 45
    assert data.factor == pytest.approx(1.15)
    assert data.samples == 1
    hass.states.async_set(MOISTURE_1, "30")
    assert controller.planned_minutes(zone) == min(zone.max_duration, round(before * 1.15))


async def test_rain_during_window_skips(hass: HomeAssistant, valves) -> None:
    """Se piove mentre si osserva, il campione si scarta."""
    hass.states.async_set(MOISTURE_1, "30")
    entry, zone_id = await _setup(hass, valves)
    controller = entry.runtime_data
    await _cycle(hass)
    hass.states.async_set(WEATHER, "rainy", {"temperature": 15})
    hass.states.async_set(MOISTURE_1, "80")
    _window_passes(hass)
    await hass.async_block_till_done()
    data = controller.learning.zones[zone_id]
    assert data.factor == 1.0
    assert data.last_result == "skipped_rain"


async def test_off_means_no_effect(hass: HomeAssistant, valves) -> None:
    """Spento: nessuna osservazione, fattore non applicato."""
    entry, zone_id = await _setup(hass, valves, learning=False)
    controller = entry.runtime_data
    controller.learning.get(zone_id).factor = 1.5
    zone = controller.zones[zone_id]
    assert controller.learned_factor(zone) == 1.0
    await _cycle(hass)
    assert not controller.observing(zone_id)


async def test_fixed_duration_not_learned(hass: HomeAssistant, valves) -> None:
    """Un ciclo con durata fissa non insegna nulla."""
    entry, zone_id = await _setup(hass, valves)
    await hass.services.async_call(DOMAIN, "start", {"duration": 5}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not entry.runtime_data.observing(zone_id)


async def test_zone_without_sensor_ignored(hass: HomeAssistant, valves) -> None:
    """La seconda zona non ha sensore: l'interruttore c'è ma non osserva."""
    entry, _zone_id = await _setup(hass, valves)
    controller = entry.runtime_data
    other = [zid for zid in controller.zones if zid != _zone_id][0]
    sub = entry.subentries[other]
    hass.config_entries.async_update_subentry(
        entry, sub, data={**sub.data, CONF_ZONE_LEARNING: True}
    )
    await hass.async_block_till_done()
    assert not controller.learning_active(controller.zones[other])
    await _cycle(hass)
    assert not controller.observing(other)


async def test_switch_and_reset(hass: HomeAssistant, valves) -> None:
    """L'interruttore cambia la zona senza ricaricare; l'azione azzera il fattore."""
    entry, zone_id = await _setup(hass, valves, learning=False)
    controller = entry.runtime_data
    switch_id = er.async_get(hass).async_get_entity_id("switch", DOMAIN, f"{zone_id}_zone_learning")
    assert hass.states.get(switch_id).state == "off"
    await hass.services.async_call("switch", "turn_on", {"entity_id": switch_id}, blocking=True)
    await hass.async_block_till_done()
    assert entry.runtime_data is controller  # nessuna ricarica
    assert controller.zones[zone_id].learning
    assert hass.states.get(switch_id).state == "on"
    controller.learning.get(zone_id).factor = 1.3
    await hass.services.async_call(DOMAIN, "reset_learning", {"entity_id": switch_id}, blocking=True)
    assert controller.learning.factor(zone_id) == 1.0
