"""Interruttori: irrigazione generale e blocco pioggia."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import IrrigazioneConfigEntry
from .const import SOURCE_MANUAL
from .entity import IrrigazioneEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrrigazioneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Crea gli interruttori."""
    controller = entry.runtime_data
    async_add_entities(
        [IrrigationSwitch(controller), RainBlockSwitch(controller)]
    )


class IrrigationSwitch(IrrigazioneEntity, SwitchEntity):
    """Acceso = ciclo in corso. Accenderlo avvia un ciclo, spegnerlo lo ferma."""

    _attr_name = None

    def __init__(self, controller) -> None:
        """Inizializza."""
        super().__init__(controller, "irrigation")

    @property
    def is_on(self) -> bool:
        """Ciclo in corso."""
        return self.controller.running

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Avvia un ciclo."""
        await self.controller.async_start(SOURCE_MANUAL)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Ferma il ciclo."""
        await self.controller.async_stop()


class RainBlockSwitch(IrrigazioneEntity, SwitchEntity, RestoreEntity):
    """Blocca l'avvio quando il meteo indica pioggia."""

    def __init__(self, controller) -> None:
        """Inizializza."""
        super().__init__(controller, "rain_block")

    async def async_added_to_hass(self) -> None:
        """Ripristina lo stato."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self.controller.rain_block = last.state != STATE_OFF

    @property
    def is_on(self) -> bool:
        """Blocco attivo."""
        return self.controller.rain_block

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Attiva il blocco."""
        self.controller.rain_block = True
        self.controller.async_update_listeners()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disattiva il blocco."""
        self.controller.rain_block = False
        self.controller.async_update_listeners()
