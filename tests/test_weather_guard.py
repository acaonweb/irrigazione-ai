"""Blocchi meteo: pioggia prevista, gelo, vento. Senza dati non si blocca nulla."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.util import dt as dt_util

from custom_components.irrigazione_ai.const import (
    CONF_FROST_TEMP,
    CONF_RAIN_FORECAST_HOURS,
    CONF_WIND_MAX,
    CONF_WIND_SENSOR,
    DOMAIN,
)
from custom_components.irrigazione_ai.weather_guard import (
    min_temperature,
    rain_expected,
    wind_kmh,
)

from .conftest import VALVE_1, WEATHER, install_fake_valves, make_entry

WIND = "sensor.vento"


def _hours(*items: dict[str, Any]) -> list[dict[str, Any]]:
    now = dt_util.utcnow().replace(minute=0, second=0, microsecond=0)
    return [
        {"datetime": (now + timedelta(hours=i)).isoformat(), **item}
        for i, item in enumerate(items)
    ]


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [(10, "m/s", 36.0), (20, "km/h", 20.0), (10, "mph", 16.1), (10, "kn", 18.5),
     ("x", "km/h", None), (10, "furlong", None), (12, None, 12.0)],
)
def test_wind_units(value, unit, expected) -> None:
    """Conversione in km/h; unità sconosciuta = nessun dato."""
    assert wind_kmh(value, unit) == expected


def test_rain_expected_window() -> None:
    """Solo le ore dentro la finestra contano."""
    now = dt_util.utcnow().replace(minute=0, second=0, microsecond=0)
    forecast = _hours({"condition": "sunny"}, {"condition": "cloudy"}, {"condition": "rainy"})
    assert rain_expected(forecast, 2, now) is None
    assert rain_expected(forecast, 3, now) is not None
    by_mm = _hours({"condition": "cloudy", "precipitation": 1.2})
    assert rain_expected(by_mm, 1, now) is not None
    by_prob = _hours({"condition": "cloudy", "precipitation_probability": 80})
    assert rain_expected(by_prob, 1, now) is not None
    assert rain_expected(None, 3, now) is None
    assert rain_expected(forecast, 0, now) is None


def test_min_temperature() -> None:
    """Minimo fra attuale e previsioni; nessun dato = None."""
    now = dt_util.utcnow().replace(minute=0, second=0, microsecond=0)
    forecast = _hours({"temperature": 6}, {"temperature": 2}, {"temperature": 1}, {"temperature": -5})
    assert min_temperature(8, forecast, 3, now) == 1
    assert min_temperature(None, None, 3, now) is None
    assert min_temperature(4, None, 3, now) == 4


def _register_forecast(hass: HomeAssistant, forecast: list[dict[str, Any]] | None) -> None:
    async def _get(call: ServiceCall) -> dict[str, Any]:
        if forecast is None:
            raise ValueError("hourly not supported")
        return {WEATHER: {"forecast": forecast}}

    hass.services.async_register(
        "weather", "get_forecasts", _get, supports_response=SupportsResponse.ONLY
    )


async def _setup(hass: HomeAssistant, calls: list, **options: Any):
    entry = make_entry(**options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    install_fake_valves(hass, calls)
    return entry


async def _start(hass: HomeAssistant, data: dict[str, Any] | None = None) -> None:
    await hass.services.async_call(DOMAIN, "start", data or {}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)


def _opened(calls: list) -> bool:
    return any(c.service == "turn_on" and c.data["entity_id"] == VALVE_1 for c in calls)


async def test_rain_forecast_blocks(hass: HomeAssistant, valves) -> None:
    """Pioggia prevista fra un'ora: ciclo saltato, nel registro."""
    entry = await _setup(hass, valves)
    _register_forecast(hass, _hours({"condition": "cloudy"}, {"condition": "rainy"}))
    await _start(hass)
    assert not _opened(valves)
    assert entry.runtime_data.last_block == "rain_forecast"
    assert entry.runtime_data.history.events[-1].summary == "Watering skipped: rain expected"


async def test_rain_forecast_follows_rain_block_switch(hass: HomeAssistant, valves) -> None:
    """Con il blocco pioggia spento la previsione non conta."""
    entry = await _setup(hass, valves)
    entry.runtime_data.rain_block = False
    _register_forecast(hass, _hours({"condition": "rainy"}))
    await _start(hass)
    assert _opened(valves)


async def test_force_ignores_weather_blocks(hass: HomeAssistant, valves) -> None:
    """force: true avvia comunque."""
    await _setup(hass, valves)
    _register_forecast(hass, _hours({"condition": "rainy"}))
    await _start(hass, {"force": True, "duration": 1})
    assert _opened(valves)


async def test_no_forecast_service_does_not_block(hass: HomeAssistant, valves) -> None:
    """Meteo senza previsioni orarie: il controllo si salta e si irriga."""
    entry = await _setup(hass, valves)
    _register_forecast(hass, None)
    await _start(hass)
    assert _opened(valves)
    assert entry.runtime_data.last_block is None


async def test_frost_blocks(hass: HomeAssistant, valves) -> None:
    """Temperatura sotto la soglia: ciclo saltato."""
    hass.states.async_set(WEATHER, "sunny", {"temperature": 1.5, "humidity": 80})
    entry = await _setup(hass, valves)
    await _start(hass)
    assert not _opened(valves)
    assert entry.runtime_data.last_block == "frost"
    assert "1.5 °C" in entry.runtime_data.history.events[-1].description


async def test_frost_from_forecast(hass: HomeAssistant, valves) -> None:
    """Fa ancora caldo ma fra due ore gela."""
    entry = await _setup(hass, valves, **{CONF_RAIN_FORECAST_HOURS: 0})
    _register_forecast(hass, _hours({"temperature": 8}, {"temperature": 4}, {"temperature": 0}))
    await _start(hass)
    assert entry.runtime_data.last_block == "frost"


async def test_frost_off(hass: HomeAssistant, valves) -> None:
    """Campo vuoto (None) = controllo del gelo spento."""
    hass.states.async_set(WEATHER, "sunny", {"temperature": -2, "humidity": 80})
    await _setup(hass, valves, **{CONF_FROST_TEMP: None})
    await _start(hass)
    assert _opened(valves)


async def test_wind_from_weather(hass: HomeAssistant, valves) -> None:
    """Vento dell'entità meteo, convertito da m/s."""
    hass.states.async_set(
        WEATHER, "windy", {"temperature": 20, "wind_speed": 12, "wind_speed_unit": "m/s"}
    )
    entry = await _setup(hass, valves)
    await _start(hass)
    assert entry.runtime_data.last_block == "wind"
    assert "43.2 km/h" in entry.runtime_data.history.events[-1].description


async def test_wind_sensor_preferred_and_fallback(hass: HomeAssistant, valves) -> None:
    """Il sensore vento decide; se non risponde, si usa il meteo; senza dati si irriga."""
    hass.states.async_set(WIND, "10", {"unit_of_measurement": "km/h"})
    hass.states.async_set(
        WEATHER, "sunny", {"temperature": 20, "wind_speed": 60, "wind_speed_unit": "km/h"}
    )
    entry = await _setup(hass, valves, **{CONF_WIND_SENSOR: WIND})
    controller = entry.runtime_data
    assert controller.wind_speed() == 10
    hass.states.async_set(WIND, "unavailable")
    assert controller.wind_speed() == 60
    hass.states.async_set(WEATHER, "sunny", {"temperature": 20})
    assert controller.wind_speed() is None
    assert await controller.async_weather_block() is None


async def test_wind_off(hass: HomeAssistant, valves) -> None:
    """Soglia 0 = controllo spento."""
    hass.states.async_set(
        WEATHER, "windy", {"temperature": 20, "wind_speed": 80, "wind_speed_unit": "km/h"}
    )
    await _setup(hass, valves, **{CONF_WIND_MAX: 0})
    await _start(hass)
    assert _opened(valves)


async def test_italian_numbers(hass: HomeAssistant, valves) -> None:
    """In italiano i decimali hanno la virgola."""
    hass.config.language = "it"
    hass.states.async_set(WEATHER, "sunny", {"temperature": 1.5})
    entry = await _setup(hass, valves)
    await _start(hass)
    event = entry.runtime_data.history.events[-1]
    assert event.summary == "Irrigazione saltata: rischio gelo"
    assert "1,5 °C" in event.description
