"""Selettori: programmazione delle zone e timer manuale."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import IrrigazioneConfigEntry
from .const import (
    ATTR_DAYS,
    ATTR_MODE,
    DOMAIN,
    MANUAL_TIMER_OPTIONS,
    SCHEDULES,
    SERVICE_SET_SCHEDULE,
    WEEKDAYS,
)
from .controller import ZoneConfig
from .entity import IrrigazioneEntity, ZoneEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrrigazioneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Crea i selettori."""
    controller = entry.runtime_data
    async_add_entities([ManualTimerSelect(controller)])
    for zone_id, zone in controller.zones.items():
        async_add_entities(
            [ZoneScheduleSelect(controller, zone)], config_subentry_id=zone_id
        )
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_SCHEDULE,
        {
            vol.Optional(ATTR_MODE): vol.In(SCHEDULES),
            vol.Optional(ATTR_DAYS): vol.All(cv.ensure_list, [vol.In(WEEKDAYS)]),
        },
        "async_set_schedule",
    )


class ZoneScheduleSelect(ZoneEntity, SelectEntity):
    """Quando irrigare la zona: spenta, un giorno sì e uno no, giorni scelti, sempre.

    I giorni scelti sono nell'attributo `days` e si cambiano con l'azione
    irrigazione_ai.set_schedule (la card la usa).
    """

    _attr_options = SCHEDULES

    def __init__(self, controller, zone: ZoneConfig) -> None:
        """Inizializza."""
        super().__init__(controller, zone, "zone_schedule")

    @property
    def _zone(self) -> ZoneConfig | None:
        return self.controller.zones.get(self.zone.zone_id)

    @property
    def available(self) -> bool:
        """Disponibile finché la zona esiste."""
        return self._zone is not None

    @property
    def current_option(self) -> str | None:
        """Modalità attuale."""
        zone = self._zone
        return zone.schedule if zone else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Giorni scelti e prossima irrigazione della zona."""
        zone = self._zone
        if zone is None:
            return {}
        nxt = self.controller.next_run(zone.zone_id)
        return {
            "days": list(zone.days),
            "alternate_from": zone.anchor.isoformat() if zone.anchor else None,
            "next_run": nxt.isoformat() if nxt else None,
        }

    async def async_select_option(self, option: str) -> None:
        """Cambia modalità."""
        self.controller.async_set_schedule(self.zone.zone_id, mode=option)

    async def async_set_schedule(
        self, mode: str | None = None, days: list[str] | None = None
    ) -> None:
        """Azione irrigazione_ai.set_schedule."""
        if mode is None and days is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="schedule_empty"
            )
        self.controller.async_set_schedule(self.zone.zone_id, mode=mode, days=days)


class ManualTimerSelect(IrrigazioneEntity, SelectEntity, RestoreEntity):
    """Durata fissa per tutte le zone (off = formula)."""

    _attr_options = MANUAL_TIMER_OPTIONS

    def __init__(self, controller) -> None:
        """Inizializza."""
        super().__init__(controller, "manual_timer")

    async def async_added_to_hass(self) -> None:
        """Ripristina il valore."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in MANUAL_TIMER_OPTIONS:
            self.controller.manual_timer = 0 if last.state == "off" else int(last.state)

    @property
    def current_option(self) -> str:
        """Valore attuale."""
        timer = self.controller.manual_timer
        return "off" if timer <= 0 else str(timer)

    async def async_select_option(self, option: str) -> None:
        """Imposta il timer."""
        self.controller.manual_timer = 0 if option == "off" else int(option)
        self.controller.async_update_listeners()
