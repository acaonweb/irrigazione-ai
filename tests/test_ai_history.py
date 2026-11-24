"""Pioggia delle ultime ore dallo storico (recorder)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.irrigazione_ai.ai import async_rain_history


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_mock, enable_custom_integrations) -> None:
    """Il recorder deve partire prima di hass (sovrascrive la fixture di conftest)."""


async def test_rain_history(hass: HomeAssistant, freezer) -> None:
    """3 ore di pioggia su 12 = 25%."""
    start = dt_util.utcnow()
    freezer.move_to(start)
    hass.states.async_set("weather.casa", "sunny")
    await async_wait_recording_done(hass)
    freezer.move_to(start + timedelta(hours=6))
    hass.states.async_set("weather.casa", "rainy")
    await async_wait_recording_done(hass)
    freezer.move_to(start + timedelta(hours=9))
    hass.states.async_set("weather.casa", "cloudy")
    await async_wait_recording_done(hass)
    freezer.move_to(start + timedelta(hours=12))

    rain = await async_rain_history(hass, "weather.casa", 12)
    assert rain is not None
    assert rain["rained"] is True
    assert rain["rain_hours"] == 3.0
    assert rain["rain_percent"] == 25

    # Nessun dato per un'entità sconosciuta
    assert await async_rain_history(hass, "weather.nessuna", 12) is None


async def test_rain_history_from_sensor(hass: HomeAssistant, freezer) -> None:
    """Con il sensore pioggia lo storico arriva dal sensore, non dal meteo."""
    start = dt_util.utcnow()
    freezer.move_to(start)
    hass.states.async_set("weather.casa", "rainy")
    hass.states.async_set("sensor.pioggia_mm_h", "0")
    await async_wait_recording_done(hass)
    freezer.move_to(start + timedelta(hours=10))
    hass.states.async_set("sensor.pioggia_mm_h", "1.2")
    await async_wait_recording_done(hass)
    freezer.move_to(start + timedelta(hours=12))

    rain = await async_rain_history(hass, "weather.casa", 12, rain_sensor="sensor.pioggia_mm_h")
    assert rain["source"] == "rain_sensor"
    assert rain["rain_hours"] == 2.0
