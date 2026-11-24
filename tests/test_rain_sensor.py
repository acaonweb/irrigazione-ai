"""Sensore pioggia proprio: decide al posto del meteo."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant

from custom_components.irrigazione_ai.const import DOMAIN, sensor_says_rain

from .conftest import VALVE_1, WEATHER, install_fake_valves, make_entry

RAIN = "binary_sensor.pioggia_balcone"


@pytest.mark.parametrize(
    ("state", "expected"),
    [("on", True), ("off", False), ("0", False), ("0.4", True), ("Raining", True),
     ("dry", False), ("unavailable", None), (None, None)],
)
def test_sensor_says_rain(state, expected) -> None:
    """Binario, numerico e testuale."""
    assert sensor_says_rain(state) is expected


async def _setup(hass: HomeAssistant, calls: list):
    entry = make_entry(rain_sensor=RAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    install_fake_valves(hass, calls)
    return entry


async def test_sensor_blocks_even_if_weather_sunny(hass: HomeAssistant, valves) -> None:
    """Il sensore dice pioggia, il meteo sereno: niente irrigazione."""
    hass.states.async_set(RAIN, "on")
    entry = await _setup(hass, valves)
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    await hass.async_block_till_done()
    assert not [c for c in valves if c.service == "turn_on"]
    assert entry.runtime_data.last_block == "rain"
    event = entry.runtime_data.history.events[-1]
    assert "Rain sensor" in event.description


async def test_sensor_dry_overrides_rainy_weather(hass: HomeAssistant, valves) -> None:
    """Il meteo dice pioggia ma il sensore no: si irriga."""
    hass.states.async_set(RAIN, "off")
    hass.states.async_set(WEATHER, "rainy", {"temperature": 20, "humidity": 90})
    await _setup(hass, valves)
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert VALVE_1 in {c.data["entity_id"] for c in valves if c.service == "turn_on"}


async def test_sensor_unavailable_falls_back_to_weather(hass: HomeAssistant, valves) -> None:
    """Sensore non disponibile: decide il meteo."""
    hass.states.async_set(RAIN, "unavailable")
    hass.states.async_set(WEATHER, "rainy", {"temperature": 20, "humidity": 90})
    entry = await _setup(hass, valves)
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    await hass.async_block_till_done()
    assert entry.runtime_data.last_block == "rain"
    assert "Weather: rainy" in entry.runtime_data.history.events[-1].description
