"""Migrazione della frequenza leggendo lo storico del recorder (senza cache di ripristino)."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.irrigazione_ai.const import DOMAIN

from .conftest import install_fake_valves, make_entry


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_mock, enable_custom_integrations) -> None:
    """Recorder attivo e integrazioni custom abilitate."""


async def test_migration_reads_recorder(hass: HomeAssistant, valves) -> None:
    """Senza cache di ripristino la vecchia frequenza arriva dallo storico."""
    entry = make_entry(weekly_day="mon")
    entry.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "select", DOMAIN, f"{entry.entry_id}_frequency",
        suggested_object_id="irrigazione_frequency", config_entry=entry,
    )
    hass.states.async_set("select.irrigazione_frequency", "weekly")
    await async_wait_recording_done(hass)
    hass.states.async_set("select.irrigazione_frequency", "unavailable")
    await async_wait_recording_done(hass)
    hass.states.async_remove("select.irrigazione_frequency")

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    install_fake_valves(hass, [])
    for zone in ("select.secondo_piano_schedule", "select.sottotetto_schedule"):
        state = hass.states.get(zone)
        assert state.state == "days"
        assert state.attributes["days"] == ["mon"]
