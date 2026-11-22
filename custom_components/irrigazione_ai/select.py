"""Selettori: frequenza e timer manuale."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import IrrigazioneConfigEntry
from .const import FREQUENCIES, MANUAL_TIMER_OPTIONS
from .entity import IrrigazioneEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrrigazioneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Crea i selettori."""
    controller = entry.runtime_data
    async_add_entities([FrequencySelect(controller), ManualTimerSelect(controller)])


class FrequencySelect(IrrigazioneEntity, SelectEntity, RestoreEntity):
    """Quanti giorni a settimana irrigare."""

    _attr_options = FREQUENCIES

    def __init__(self, controller) -> None:
        """Inizializza."""
        super().__init__(controller, "frequency")

    async def async_added_to_hass(self) -> None:
        """Ripristina il valore."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in FREQUENCIES:
            self.controller.frequency = last.state

    @property
    def current_option(self) -> str:
        """Frequenza attuale."""
        return self.controller.frequency

    async def async_select_option(self, option: str) -> None:
        """Cambia frequenza."""
        self.controller.frequency = option
        self.controller.async_update_listeners()


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
