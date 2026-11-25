"""Interruttori: irrigazione generale, blocco pioggia, AI e autoapprendimento per zona."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import IrrigazioneConfigEntry
from .const import SERVICE_RESET_LEARNING, SOURCE_MANUAL
from .controller import ZoneConfig
from .entity import IrrigazioneEntity, ZoneEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrrigazioneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Crea gli interruttori."""
    controller = entry.runtime_data
    async_add_entities(
        [IrrigationSwitch(controller), RainBlockSwitch(controller), AiSwitch(controller)]
    )
    for zone_id, zone in controller.zones.items():
        async_add_entities([LearningSwitch(controller, zone)], config_subentry_id=zone_id)
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_RESET_LEARNING, None, "async_reset_learning"
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
    """Blocca l'avvio quando piove (sensore pioggia o, in mancanza, meteo)."""

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


class AiSwitch(IrrigazioneEntity, SwitchEntity, RestoreEntity):
    """Se acceso, l'AI decide se e quanto irrigare a ogni ciclo."""

    def __init__(self, controller) -> None:
        """Inizializza."""
        super().__init__(controller, "ai_analysis")

    async def async_added_to_hass(self) -> None:
        """Ripristina lo stato (spento di default)."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self.controller.ai_enabled = last.state == "on"

    @property
    def available(self) -> bool:
        """Disponibile solo se un provider AI è configurato."""
        return self.controller.ai_configured

    @property
    def is_on(self) -> bool:
        """Analisi AI attiva."""
        return self.controller.ai_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Attiva."""
        self.controller.ai_enabled = True
        self.controller.async_update_listeners()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disattiva."""
        self.controller.ai_enabled = False
        self.controller.async_update_listeners()


class LearningSwitch(ZoneEntity, SwitchEntity):
    """Autoapprendimento della zona: corregge da sola la dose dopo ogni irrigazione."""

    def __init__(self, controller, zone: ZoneConfig) -> None:
        """Inizializza."""
        super().__init__(controller, zone, "zone_learning")

    @property
    def _zone(self) -> ZoneConfig | None:
        return self.controller.zones.get(self.zone.zone_id)

    @property
    def available(self) -> bool:
        """Disponibile finché la zona esiste."""
        return self._zone is not None

    @property
    def is_on(self) -> bool:
        """Autoapprendimento acceso."""
        zone = self._zone
        return bool(zone and zone.learning)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Fattore appreso e ultima osservazione."""
        zone = self._zone
        if zone is None:
            return {}
        data = self.controller.learning.zones.get(zone.zone_id)
        return {
            "factor": data.factor if data else 1.0,
            "applied": self.controller.learned_factor(zone),
            "samples": data.samples if data else 0,
            "target": self.controller.learn_target,
            "last_before": data.last_before if data else None,
            "last_peak": data.last_peak if data else None,
            "last_result": data.last_result if data else None,
            "last_at": data.last_at if data else None,
            "observing": self.controller.observing(zone.zone_id),
            "has_sensor": zone.moisture_sensor is not None,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Accende."""
        self.controller.async_set_learning(self.zone.zone_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Spegne (il fattore appreso resta, ma non si applica)."""
        self.controller.async_set_learning(self.zone.zone_id, False)

    async def async_reset_learning(self) -> None:
        """Azione irrigazione_ai.reset_learning: riparte da fattore 1."""
        self.controller.async_reset_learning(self.zone.zone_id)
