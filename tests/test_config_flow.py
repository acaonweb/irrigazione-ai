"""Test del wizard."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.irrigazione_ai.const import (
    CONF_RUN_MODE,
    CONF_SAFETY_MINUTES,
    CONF_VALVE,
    CONF_WEATHER,
    DOMAIN,
    SUBENTRY_ZONE,
)

from .conftest import VALVE_1, VALVE_2, WEATHER, make_entry, zone_data

SCHEDULE = {
    "sunset_offset": 5,
    "run_mode": "sequential",
    "safety_minutes": 60,
    "close_on_startup": True,
    "notify_services": ["notify.pushover"],
}


def _zone_input(name: str, valve: str) -> dict:
    data = zone_data(name, valve)
    data.pop("moisture_sensor", None)
    return data


async def test_full_wizard(hass: HomeAssistant, valves) -> None:
    """Impianto + due zone + programmazione."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Terrazzo", CONF_WEATHER: WEATHER}
    )
    assert result["step_id"] == "zone"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _zone_input("Secondo piano", VALVE_1)
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "zone"}
    )
    # Stessa valvola: errore
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _zone_input("Doppia", VALVE_1)
    )
    assert result["errors"] == {CONF_VALVE: "valve_in_use"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _zone_input("Sottotetto", VALVE_2)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "schedule"}
    )
    assert result["step_id"] == "schedule"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], SCHEDULE)
    assert result["step_id"] == "formula"

    # Gli errori di sintassi li blocca già il selettore template di HA;
    # qui un template valido che però non restituisce un numero.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"formula": "{{ weather }}"}
    )
    assert result["errors"] == {"formula": "formula_invalid"}
    assert "non è un numero" in result["description_placeholders"]["error"]
    # Variabile inesistente usata in un calcolo
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"formula": "{{ pippo * 2 }}"}
    )
    assert result["errors"] == {"formula": "formula_invalid"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"formula": "{{ 40 * coefficient }}"}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "formula_preview"
    assert "**Secondo piano**: 40 min" in result["description_placeholders"]["preview"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "ai"}
    )
    assert result["step_id"] == "ai"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ai_provider": "none"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.options["ai_provider"] == "none"
    assert entry.options["formula"] == "{{ 40 * coefficient }}"
    assert entry.title == "Terrazzo"
    assert entry.options[CONF_WEATHER] == WEATHER
    assert entry.options[CONF_RUN_MODE] == "sequential"
    assert entry.options[CONF_SAFETY_MINUTES] == 60
    zones = [s for s in entry.subentries.values() if s.subentry_type == SUBENTRY_ZONE]
    assert sorted(z.title for z in zones) == ["Secondo piano", "Sottotetto"]


async def test_min_greater_than_max(hass: HomeAssistant, valves) -> None:
    """Durata minima > massima."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Test", CONF_WEATHER: WEATHER}
    )
    bad = _zone_input("Zona", VALVE_1) | {"min_duration": 50, "max_duration": 20}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], bad)
    assert result["errors"] == {"max_duration": "min_greater_than_max"}


async def test_add_and_reconfigure_zone(hass: HomeAssistant, valves) -> None:
    """Aggiunta e modifica di una zona dopo la creazione."""
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("switch.valvola03", "off")
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ZONE), context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _zone_input("Orto", "switch.valvola03")
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert len(entry.subentries) == 3

    sub_id = next(s for s, sub in entry.subentries.items() if sub.title == "Orto")
    result = await entry.start_subentry_reconfigure_flow(hass, sub_id)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _zone_input("Orto grande", "switch.valvola03")
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries[sub_id].title == "Orto grande"


async def test_options_flow(hass: HomeAssistant, valves) -> None:
    """Modifica della programmazione."""
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_WEATHER: WEATHER, **SCHEDULE, "safety_minutes": 30}
    )
    assert result["step_id"] == "formula"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"formula": "{{ 25 }}"}
    )
    assert result["step_id"] == "formula_preview"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "ai"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"ai_provider": "none"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["safety_minutes"] == 30
    assert entry.options[CONF_RUN_MODE] == "sequential"
    assert entry.options["formula"] == "{{ 25 }}"
    assert hass.states.get("sensor.secondo_piano_planned_duration").state == "25"


async def test_zone_formula_invalid(hass: HomeAssistant, valves) -> None:
    """Formula della zona non valida: errore nel modulo."""
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hass.states.async_set("switch.valvola03", "off")
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_ZONE), context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _zone_input("Orto", "switch.valvola03") | {"formula": "{{ 'abc' }}"}
    )
    assert result["errors"] == {"formula": "formula_invalid"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _zone_input("Orto", "switch.valvola03") | {"formula": "{{ 33 }}"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get("sensor.orto_planned_duration").state == "33"


async def test_wizard_without_weather(hass: HomeAssistant, valves) -> None:
    """Il meteo è facoltativo."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Balcone"})
    assert result["step_id"] == "zone"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _zone_input("Fioriera", VALVE_1)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "schedule"}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], SCHEDULE)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"formula": "{{ 20 }}"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "ai"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"ai_provider": "none"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert hass.states.get("sensor.fioriera_planned_duration").state == "20"
