"""Sensori binari: terriccio secco per zona."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IrrigazioneConfigEntry
from .controller import IrrigationController, ZoneConfig
from .entity import ZoneEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrrigazioneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Un sensore 'Terriccio secco' per ogni zona con sensore di umidità."""
    controller = entry.runtime_data
    for zone_id, zone in controller.zones.items():
        if zone.moisture_sensor:
            async_add_entities(
                [DrySoilSensor(controller, zone)], config_subentry_id=zone_id
            )


class DrySoilSensor(ZoneEntity, BinarySensorEntity):
    """Acceso quando il terriccio resta sotto la soglia per 5 minuti."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        """Inizializza."""
        super().__init__(controller, zone, "zone_dry")

    @property
    def available(self) -> bool:
        """Non disponibile se l'allarme è spento (soglia 0)."""
        return self.controller.dry_threshold > 0

    @property
    def is_on(self) -> bool:
        """Terriccio secco."""
        return bool(self.controller.dry.get(self.zone.zone_id))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Umidità attuale e soglia."""
        zone = self.controller.zones.get(self.zone.zone_id, self.zone)
        return {
            "moisture": self.controller.zone_moisture(zone),
            "threshold": self.controller.dry_threshold,
        }
