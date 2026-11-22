"""Nomi delle entità con HA in italiano."""

from homeassistant.core import HomeAssistant

from .conftest import make_entry


async def test_italian_entity_ids(hass: HomeAssistant, valves) -> None:
    """Con la lingua italiana gli entity_id sono in italiano."""
    hass.config.language = "it"
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    ids = sorted(
        e for e in hass.states.async_entity_ids()
        if e.split(".")[1].startswith(("irrigazione", "secondo_piano", "sottotetto"))
    )
    print("\n".join(ids))
    assert "switch.irrigazione_blocco_pioggia" in ids
    assert "sensor.secondo_piano_durata_prevista" in ids
