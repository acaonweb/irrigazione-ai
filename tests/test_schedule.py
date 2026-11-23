"""Test dell'orario di partenza: tramonto, alba, orario fisso."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .conftest import VALVE_1, install_fake_valves, make_entry


async def _setup(hass: HomeAssistant, calls: list, **options):
    await hass.config.async_set_time_zone("Europe/Rome")
    hass.config.latitude, hass.config.longitude = 41.9, 12.5
    entry = make_entry(**options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    install_fake_valves(hass, calls)
    await hass.services.async_call(
        "select", "select_option",
        {"entity_id": "select.irrigazione_frequency", "option": "daily"},
        blocking=True,
    )
    return entry.runtime_data


async def test_default_is_sunset(hass: HomeAssistant, valves) -> None:
    """Senza scelta esplicita resta il tramonto + scostamento."""
    controller = await _setup(hass, valves)
    when = controller.next_run()
    sunset = get_astral_event_date(hass, SUN_EVENT_SUNSET, dt_util.as_local(when).date())
    assert when == sunset + timedelta(minutes=5)


async def test_sunrise_with_negative_offset(hass: HomeAssistant, valves) -> None:
    """Alba con scostamento negativo: parte prima dell'alba."""
    controller = await _setup(hass, valves, start_mode="sunrise", sunset_offset=-30)
    when = controller.next_run()
    sunrise = get_astral_event_date(hass, SUN_EVENT_SUNRISE, dt_util.as_local(when).date())
    assert when == sunrise - timedelta(minutes=30)


async def test_fixed_time(
    hass: HomeAssistant, valves, freezer: FrozenDateTimeFactory
) -> None:
    """Orario fisso: next_run alle 07:30 locali e il ciclo parte a quell'ora."""
    freezer.move_to("2026-11-23 05:00:00+00:00")  # 06:00 a Roma
    controller = await _setup(
        hass, valves, start_mode="time", start_time="07:30:00", sunset_offset=45
    )
    when = dt_util.as_local(controller.next_run())
    assert when.date() == datetime(2026, 11, 23).date()
    assert when.time() == time(7, 30)  # lo scostamento non si applica

    freezer.move_to("2026-11-23 06:30:00+00:00")
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    opened = [c for c in valves if c.service == "turn_on" and c.data["entity_id"] == VALVE_1]
    assert opened, "il ciclo doveva partire alle 07:30"
    # Il prossimo è domani alla stessa ora
    nxt = dt_util.as_local(controller.next_run())
    assert (nxt.date(), nxt.time()) == (datetime(2026, 11, 24).date(), time(7, 30))
