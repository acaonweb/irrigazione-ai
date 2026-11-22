"""Pulsanti: avvia ora, ferma."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IrrigazioneConfigEntry
from .ai import AiError
from .const import SOURCE_MANUAL
from .entity import IrrigazioneEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrrigazioneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Crea i pulsanti."""
    controller = entry.runtime_data
    async_add_entities(
        [StartButton(controller), StopButton(controller), AnalyzeButton(controller)]
    )


class StartButton(IrrigazioneEntity, ButtonEntity):
    """Avvia subito un ciclo."""

    def __init__(self, controller) -> None:
        """Inizializza."""
        super().__init__(controller, "start")

    async def async_press(self) -> None:
        """Avvia."""
        await self.controller.async_start(SOURCE_MANUAL)


class StopButton(IrrigazioneEntity, ButtonEntity):
    """Ferma il ciclo e chiude le valvole."""

    def __init__(self, controller) -> None:
        """Inizializza."""
        super().__init__(controller, "stop")

    async def async_press(self) -> None:
        """Ferma."""
        await self.controller.async_stop()


class AnalyzeButton(IrrigazioneEntity, ButtonEntity):
    """Chiede subito all'AI una valutazione, senza irrigare."""

    def __init__(self, controller) -> None:
        """Inizializza."""
        super().__init__(controller, "analyze")

    @property
    def available(self) -> bool:
        """Disponibile solo se un provider AI è configurato."""
        return self.controller.ai_configured

    async def async_press(self) -> None:
        """Analizza."""
        try:
            await self.controller.async_analyze()
        except AiError as err:
            raise HomeAssistantError(f"Analisi AI non riuscita: {err}") from err
