"""Fixture comuni."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigazione_ai.const import (
    CONF_CLOSE_ON_STARTUP,
    CONF_COEFFICIENT,
    CONF_EXPOSURE,
    CONF_FLOW_RATE,
    CONF_MAX_DURATION,
    CONF_MIN_DURATION,
    CONF_MOISTURE,
    CONF_NOTIFY,
    CONF_RUN_MODE,
    CONF_SAFETY_MINUTES,
    CONF_SOIL_VOLUME,
    CONF_SUNSET_OFFSET,
    CONF_TWICE_WEEKLY_DAYS,
    CONF_VALVE,
    CONF_WEATHER,
    CONF_WEEKLY_DAY,
    CONF_ZONE_NAME,
    DOMAIN,
    SUBENTRY_ZONE,
)

VALVE_1 = "switch.valvola01"
VALVE_2 = "switch.valvola02"
WEATHER = "weather.casa"
MOISTURE_1 = "sensor.umidita_01"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Abilita le integrazioni custom in tutti i test."""


@pytest.fixture(autouse=True)
def fast_sleep():
    """Le attese del motore durano un istante."""

    async def _fast(_seconds: float) -> None:
        await asyncio.sleep(0)

    with patch("custom_components.irrigazione_ai.controller._sleep", _fast):
        yield


@pytest.fixture
def slow_zone_sleep():
    """Le zone restano aperte finché il test non le ferma."""
    gate = asyncio.Event()

    async def _sleep(seconds: float) -> None:
        if seconds > 10:
            await gate.wait()
        else:
            await asyncio.sleep(0)

    with patch("custom_components.irrigazione_ai.controller._sleep", _sleep):
        yield gate


@pytest.fixture
def valves(hass: HomeAssistant) -> list[ServiceCall]:
    """Stati iniziali per due finte valvole switch e il meteo."""
    hass.states.async_set(VALVE_1, "off")
    hass.states.async_set(VALVE_2, "off")
    hass.states.async_set(WEATHER, "sunny", {"temperature": 20, "humidity": 60})
    hass.states.async_set(MOISTURE_1, "50", {"device_class": "moisture"})
    return []


def install_fake_valves(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Sostituisce switch.turn_on/off con servizi finti che cambiano lo stato.

    Va chiamata dopo il setup: caricando la piattaforma switch, HA registra
    i servizi veri e sovrascriverebbe questi.
    """

    async def _turn_on(call: ServiceCall) -> None:
        calls.append(call)
        for entity_id in _ids(call):
            if entity_id in (VALVE_1, VALVE_2) or entity_id.startswith("switch.valvola"):
                hass.states.async_set(entity_id, "on")
            else:
                await _real_on(call)

    async def _turn_off(call: ServiceCall) -> None:
        calls.append(call)
        for entity_id in _ids(call):
            if entity_id in (VALVE_1, VALVE_2) or entity_id.startswith("switch.valvola"):
                hass.states.async_set(entity_id, "off")
            else:
                await _real_off(call)

    services = hass.services.async_services()["switch"]
    real_on = services["turn_on"]
    real_off = services["turn_off"]

    async def _real_on(call: ServiceCall) -> None:
        await real_on.job.target(call)

    async def _real_off(call: ServiceCall) -> None:
        await real_off.job.target(call)

    hass.services.async_register("switch", "turn_on", _turn_on)
    hass.services.async_register("switch", "turn_off", _turn_off)


def _ids(call: ServiceCall) -> list[str]:
    ids = call.data["entity_id"]
    return [ids] if isinstance(ids, str) else list(ids)


def zone_data(name: str, valve: str, moisture: str | None = None) -> dict[str, Any]:
    """Dati di una zona."""
    data: dict[str, Any] = {
        CONF_ZONE_NAME: name,
        CONF_VALVE: valve,
        CONF_FLOW_RATE: 0.726,
        CONF_MIN_DURATION: 15,
        CONF_MAX_DURATION: 120,
        CONF_COEFFICIENT: 1.0,
        CONF_SOIL_VOLUME: 100.0,
        CONF_EXPOSURE: "north",
    }
    if moisture:
        data[CONF_MOISTURE] = moisture
    return data


def make_entry(run_mode: str = "parallel", safety: int = 60) -> MockConfigEntry:
    """Impianto con due zone."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Irrigazione",
        data={"name": "Irrigazione"},
        options={
            CONF_WEATHER: WEATHER,
            CONF_SUNSET_OFFSET: 5,
            CONF_WEEKLY_DAY: "sun",
            CONF_TWICE_WEEKLY_DAYS: ["thu", "sun"],
            CONF_RUN_MODE: run_mode,
            CONF_SAFETY_MINUTES: safety,
            CONF_CLOSE_ON_STARTUP: False,
            CONF_NOTIFY: [],
        },
        subentries_data=[
            {
                "subentry_type": SUBENTRY_ZONE,
                "data": zone_data("Secondo piano", VALVE_1, MOISTURE_1),
                "title": "Secondo piano",
                "unique_id": VALVE_1,
            },
            {
                "subentry_type": SUBENTRY_ZONE,
                "data": zone_data("Sottotetto", VALVE_2),
                "title": "Sottotetto",
                "unique_id": VALVE_2,
            },
        ],
    )
