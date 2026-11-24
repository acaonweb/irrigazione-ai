"""Allarme terriccio secco: soglia, attesa di 5 minuti, una sola notifica, isteresi."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .conftest import MOISTURE_1, install_fake_valves, make_entry

DRY = "binary_sensor.secondo_piano_dry_soil"


async def _setup(hass: HomeAssistant, calls: list, **options):
    sent: list[ServiceCall] = []

    async def _push(call: ServiceCall) -> None:
        sent.append(call)

    hass.services.async_register("notify", "pushover", _push)
    entry = make_entry(notify_services=["notify.pushover"], **options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    install_fake_valves(hass, calls)
    return entry, sent


async def _wait(hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: int) -> None:
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()


async def test_dry_alarm(hass: HomeAssistant, valves, freezer: FrozenDateTimeFactory) -> None:
    """Sotto soglia per 5 minuti: una notifica; torna normale sopra soglia + 3."""
    _entry, sent = await _setup(hass, valves)
    assert hass.states.get(DRY).state == "off"
    assert hass.states.get(DRY).attributes["threshold"] == 25

    hass.states.async_set(MOISTURE_1, "20")
    await hass.async_block_till_done()
    await _wait(hass, freezer, 3)
    assert hass.states.get(DRY).state == "off"  # non ancora 5 minuti
    await _wait(hass, freezer, 3)
    assert hass.states.get(DRY).state == "on"
    dry_msgs = [c for c in sent if "Dry soil" in c.data["message"]]
    assert len(dry_msgs) == 1
    assert "Secondo piano is at 20% (threshold 25%)" in dry_msgs[0].data["message"]

    # Scende ancora: nessuna nuova notifica
    hass.states.async_set(MOISTURE_1, "15")
    await hass.async_block_till_done()
    await _wait(hass, freezer, 10)
    assert len([c for c in sent if "Dry soil" in c.data["message"]]) == 1

    # 26% non basta (isteresi), 28% sì
    hass.states.async_set(MOISTURE_1, "26")
    await hass.async_block_till_done()
    assert hass.states.get(DRY).state == "on"
    hass.states.async_set(MOISTURE_1, "28")
    await hass.async_block_till_done()
    assert hass.states.get(DRY).state == "off"


async def test_short_dip_no_alarm(
    hass: HomeAssistant, valves, freezer: FrozenDateTimeFactory
) -> None:
    """Un calo di 2 minuti non fa scattare l'allarme."""
    _entry, sent = await _setup(hass, valves)
    hass.states.async_set(MOISTURE_1, "20")
    await hass.async_block_till_done()
    await _wait(hass, freezer, 2)
    hass.states.async_set(MOISTURE_1, "40")
    await hass.async_block_till_done()
    await _wait(hass, freezer, 10)
    assert hass.states.get(DRY).state == "off"
    assert not [c for c in sent if "Dry soil" in c.data["message"]]


async def test_dry_alarm_off(hass: HomeAssistant, valves, freezer: FrozenDateTimeFactory) -> None:
    """Soglia 0: allarme spento, sensore non disponibile."""
    _entry, sent = await _setup(hass, valves, dry_threshold=0)
    hass.states.async_set(MOISTURE_1, "5")
    await hass.async_block_till_done()
    await _wait(hass, freezer, 10)
    assert hass.states.get(DRY).state == "unavailable"
    assert not sent


async def test_no_notify_at_startup(hass: HomeAssistant, valves) -> None:
    """Già secco all'avvio: sensore acceso ma nessuna notifica."""
    hass.states.async_set(MOISTURE_1, "10", {"device_class": "moisture"})
    _entry, sent = await _setup(hass, valves)
    assert hass.states.get(DRY).state == "on"
    assert not sent
