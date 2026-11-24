"""Sensori dell'impianto e delle zone."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)

from . import IrrigazioneConfigEntry
from .const import (
    AI_RESULT_ERROR,
    AI_RESULT_IRRIGATE,
    AI_RESULT_SKIP,
    AI_RESULTS,
    CONF_HUMIDITY,
    CONF_TEMPERATURE,
    CONF_TWICE_WEEKLY_DAYS,
    CONF_WEATHER,
    CONF_WEEKLY_DAY,
    DEFAULT_TWICE_WEEKLY_DAYS,
    DEFAULT_WEEKLY_DAY,
    DOMAIN,
    STATUSES,
)
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
            AiDecisionSensor(controller),
            WaterSensor(controller, "water_today", "day"),
            WaterSensor(controller, "water_month", "month"),
            WaterSensor(controller, "water_total", "total"),
        ]
    )
    for zone_id, zone in controller.zones.items():
        async_add_entities(
            [
                ZoneDurationSensor(controller, zone),
                ZoneEndSensor(controller, zone),
                ZoneAiSensor(controller, zone),
                ZoneWaterSensor(controller, zone, "zone_water_today", "day"),
                ZoneWaterSensor(controller, zone, "zone_water_total", "total"),
            ],
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

    def _entity_map(self) -> dict[str, Any]:
        """Entità dell'impianto e delle zone (usate dalla card Lovelace)."""
        reg = er.async_get(self.hass)
        c = self.controller
        entry_id = c.entry.entry_id

        def find(domain: str, unique_id: str) -> str | None:
            return reg.async_get_entity_id(domain, DOMAIN, unique_id)

        system = {
            key: find(domain, f"{entry_id}_{key}")
            for domain, key in (
                ("switch", "irrigation"),
                ("switch", "rain_block"),
                ("switch", "ai_analysis"),
                ("select", "frequency"),
                ("select", "manual_timer"),
                ("button", "start"),
                ("button", "stop"),
                ("button", "analyze"),
                ("sensor", "remaining"),
                ("sensor", "next_run"),
                ("sensor", "last_run"),
                ("sensor", "last_block"),
                ("sensor", "ai_decision"),
                ("sensor", "water_today"),
                ("sensor", "water_month"),
                ("calendar", "calendar"),
            )
        }
        zones = [
            {
                "name": zone.name,
                "valve": zone.valve,
                "moisture": zone.moisture_sensor,
                "duration": find("sensor", f"{zone_id}_zone_duration"),
                "end": find("sensor", f"{zone_id}_zone_end"),
                "ai": find("sensor", f"{zone_id}_zone_ai_duration"),
                "water_today": find("sensor", f"{zone_id}_zone_water_today"),
                "water_total": find("sensor", f"{zone_id}_zone_water_total"),
            }
            for zone_id, zone in c.zones.items()
        ]
        cfg = c.config
        system["water_total"] = find("sensor", f"{entry_id}_water_total")
        return {
            "system": system,
            "zones": zones,
            "ai": c.ai_configured,
            "weather": cfg.get(CONF_WEATHER),
            "temperature": cfg.get(CONF_TEMPERATURE),
            "humidity": cfg.get(CONF_HUMIDITY),
            "weekly_day": cfg.get(CONF_WEEKLY_DAY, DEFAULT_WEEKLY_DAY),
            "twice_weekly_days": list(cfg.get(CONF_TWICE_WEEKLY_DAYS, DEFAULT_TWICE_WEEKLY_DAYS)),
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Dettagli del ciclo ed entità per la card."""
        c = self.controller
        return {
            "card": self._entity_map(),
            "source": c.run_source if c.running else None,
            "config_pending": c.reload_pending,
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


class AiDecisionSensor(IrrigazioneEntity, SensorEntity):
    """Esito dell'ultima analisi AI: irrigare, saltare o errore."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = AI_RESULTS

    def __init__(self, controller: IrrigationController) -> None:
        """Inizializza."""
        super().__init__(controller, "ai_decision")

    @property
    def available(self) -> bool:
        """Disponibile solo se un provider AI è configurato."""
        return self.controller.ai_configured

    @property
    def native_value(self) -> str | None:
        """Esito più recente (errore se l'ultimo tentativo è fallito)."""
        c = self.controller
        result = c.ai_result
        if c.ai_error and (result is None or (c.ai_error_at and c.ai_error_at > result.at)):
            return AI_RESULT_ERROR
        if result is None:
            return None
        return AI_RESULT_IRRIGATE if result.irrigate else AI_RESULT_SKIP

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Motivo, ora, provider, litri per zona."""
        c = self.controller
        result = c.ai_result
        return {
            "reason": result.reason if result else None,
            "analyzed_at": result.at.isoformat() if result else None,
            "provider": result.provider if result else None,
            "error": c.ai_error,
            "zones": {
                z.name: {"liters": z.liters, "minutes": z.minutes, "reason": z.reason}
                for z in result.zones.values()
            }
            if result
            else {},
        }


class ZoneAiSensor(ZoneEntity, SensorEntity):
    """Minuti decisi dall'AI per la zona nell'ultima analisi."""

    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_device_class = SensorDeviceClass.DURATION

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        """Inizializza."""
        super().__init__(controller, zone, "zone_ai_duration")

    @property
    def available(self) -> bool:
        """Disponibile solo se un provider AI è configurato."""
        return self.controller.ai_configured

    @property
    def native_value(self) -> int | None:
        """Minuti (None prima della prima analisi)."""
        result = self.controller.ai_result
        if result is None or self.zone.zone_id not in result.zones:
            return None
        return result.zones[self.zone.zone_id].minutes

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Litri e motivo."""
        result = self.controller.ai_result
        zr = result.zones.get(self.zone.zone_id) if result else None
        return {
            "liters": zr.liters if zr else None,
            "reason": zr.reason if zr else None,
        }


class _WaterMixin:
    """Litri erogati (contatore che si azzera a inizio giorno/mese)."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 1


class WaterSensor(_WaterMixin, IrrigazioneEntity, SensorEntity):
    """Acqua di tutte le zone: oggi, questo mese, totale."""

    def __init__(self, controller: IrrigationController, key: str, period: str) -> None:
        """Inizializza."""
        super().__init__(controller, key)
        self._period = period

    @property
    def native_value(self) -> float:
        """Litri."""
        c = self.controller
        return getattr(c.history.totals(list(c.zones)), self._period)


class ZoneWaterSensor(_WaterMixin, ZoneEntity, SensorEntity):
    """Acqua di una zona: oggi o totale."""

    def __init__(
        self, controller: IrrigationController, zone: ZoneConfig, key: str, period: str
    ) -> None:
        """Inizializza."""
        super().__init__(controller, zone, key)
        self._period = period

    @property
    def native_value(self) -> float:
        """Litri."""
        return round(getattr(self.controller.history.zone(self.zone.zone_id), self._period), 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Per il totale: anche il mese in corso."""
        if self._period != "total":
            return None
        return {"month": round(self.controller.history.zone(self.zone.zone_id).month, 1)}
