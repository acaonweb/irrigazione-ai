"""Sensori dell'impianto e delle zone."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)

from . import IrrigazioneConfigEntry
from .const import CONF_TEMPERATURE, CONF_WEATHER, STATUSES
from .controller import IrrigationController, ZoneConfig
from .entity import IrrigazioneEntity, ZoneEntity

REFRESH = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrrigazioneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Crea i sensori."""
    controller = entry.runtime_data
    async_add_entities(
        [
            StatusSensor(controller),
            RemainingSensor(controller),
            NextRunSensor(controller),
            LastBlockSensor(controller),
            LastRunSensor(controller),
        ]
    )
    for zone_id, zone in controller.zones.items():
        async_add_entities(
            [ZoneDurationSensor(controller, zone), ZoneEndSensor(controller, zone)],
            config_subentry_id=zone_id,
        )


class _PeriodicMixin(IrrigazioneEntity):
    """Aggiorna lo stato a intervalli (per valori che dipendono dall'ora)."""

    _interval: timedelta = REFRESH

    async def async_added_to_hass(self) -> None:
        """Avvia l'aggiornamento periodico."""
        await super().async_added_to_hass()

        @callback
        def _tick(_now: datetime) -> None:
            self.async_write_ha_state()

        self.async_on_remove(async_track_time_interval(self.hass, _tick, self._interval))


class StatusSensor(IrrigazioneEntity, SensorEntity):
    """Stato dell'impianto: fermo, in corso, bloccato."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUSES

    def __init__(self, controller: IrrigationController) -> None:
        """Inizializza."""
        super().__init__(controller, "status")

    @property
    def native_value(self) -> str:
        """Stato."""
        return self.controller.status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Dettagli del ciclo."""
        c = self.controller
        return {
            "source": c.run_source if c.running else None,
            "zones": {
                c.zones[zid].name: {
                    "minutes": run.minutes,
                    "active": run.active,
                    "ends_at": run.ends_at.isoformat(),
                }
                for zid, run in c.zone_runs.items()
                if zid in c.zones
            }
            if c.running
            else {},
        }


class RemainingSensor(_PeriodicMixin, SensorEntity):
    """Minuti alla fine del ciclo in corso."""

    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_device_class = SensorDeviceClass.DURATION

    def __init__(self, controller: IrrigationController) -> None:
        """Inizializza."""
        super().__init__(controller, "remaining")

    @property
    def native_value(self) -> int:
        """Minuti rimanenti."""
        return self.controller.remaining_minutes()


class NextRunSensor(_PeriodicMixin, SensorEntity):
    """Prossima irrigazione programmata."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _interval = timedelta(minutes=10)

    def __init__(self, controller: IrrigationController) -> None:
        """Inizializza."""
        super().__init__(controller, "next_run")

    @property
    def native_value(self) -> datetime | None:
        """Data e ora."""
        return self.controller.next_run()


class LastBlockSensor(IrrigazioneEntity, SensorEntity):
    """Ultimo avvio bloccato (con motivo)."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, controller: IrrigationController) -> None:
        """Inizializza."""
        super().__init__(controller, "last_block")

    @property
    def native_value(self) -> datetime | None:
        """Quando."""
        return self.controller.last_block_at

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Motivo (rain, ...) e se è ancora l'ultimo evento."""
        return {
            "reason": self.controller.last_block,
            "active": self.controller.last_block is not None,
        }


class LastRunSensor(IrrigazioneEntity, SensorEntity):
    """Fine dell'ultimo ciclo."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, controller: IrrigationController) -> None:
        """Inizializza."""
        super().__init__(controller, "last_run")

    @property
    def native_value(self) -> datetime | None:
        """Quando."""
        return self.controller.last_run_end


class ZoneDurationSensor(ZoneEntity, SensorEntity):
    """Durata che verrebbe usata ora per la zona (formula o timer manuale).

    Si aggiorna quando cambiano sensori e meteo, e ogni 5 minuti per le
    formule personalizzate che leggono altre entità.
    """

    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_device_class = SensorDeviceClass.DURATION

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        """Inizializza."""
        super().__init__(controller, zone, "zone_duration")

    async def async_added_to_hass(self) -> None:
        """Si aggiorna quando cambiano i dati di ingresso."""
        await super().async_added_to_hass()
        cfg = self.controller.config
        sources = [
            e
            for e in (
                self.zone.moisture_sensor,
                cfg.get(CONF_TEMPERATURE),
                cfg.get(CONF_WEATHER),
            )
            if e
        ]
        if sources:

            @callback
            def _changed(_event) -> None:
                self.async_write_ha_state()

            self.async_on_remove(
                async_track_state_change_event(self.hass, sources, _changed)
            )

        @callback
        def _tick(_now: datetime) -> None:
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_time_interval(self.hass, _tick, timedelta(minutes=5))
        )

    @property
    def native_value(self) -> int:
        """Minuti."""
        return self.controller.planned_minutes(self.zone)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Dati usati nel calcolo."""
        c = self.controller
        formula_minutes = c.calculated_minutes(self.zone)
        _formula, source = c.zone_formula(self.zone)
        return {
            "formula": source,
            "formula_error": c.formula_errors.get(self.zone.zone_id),
            "moisture": c.zone_moisture(self.zone),
            "temperature": c.outdoor_temperature(),
            "weather": c.weather_state(),
            "formula_minutes": formula_minutes,
            "manual_timer": c.manual_timer or None,
            "liters": round(c.planned_minutes(self.zone) * self.zone.flow_rate, 1),
        }


class ZoneEndSensor(ZoneEntity, SensorEntity):
    """Ora di fine prevista della zona durante un ciclo."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        """Inizializza."""
        super().__init__(controller, zone, "zone_end")

    @property
    def native_value(self) -> datetime | None:
        """Fine prevista (None se la zona non è nel ciclo in corso)."""
        c = self.controller
        run = c.zone_runs.get(self.zone.zone_id)
        if not c.running or run is None or run.done:
            return None
        return run.ends_at
