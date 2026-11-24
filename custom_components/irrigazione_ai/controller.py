"""Motore di irrigazione: programmazione, cicli, sicurezza."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    STATE_ON,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
)
from homeassistant.core import (
    CoreState,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_sunrise,
    async_track_sunset,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util

from .ai import (
    AiError,
    AiResult,
    async_forecast,
    async_query,
    async_rain_history,
    build_prompt,
    parse_result,
)
from .calc import (
    calculate_duration,
    clamp_minutes,
    formula_variables,
    zone_irrigates_on,
)
from .const import (
    AI_NONE,
    AI_ON_ERROR_DISABLE,
    AI_ON_ERROR_SKIP,
    CLOSE_RETRIES,
    CLOSE_RETRY_DELAY,
    CONF_AI_INSTRUCTIONS,
    CONF_AI_ON_ERROR,
    CONF_AI_PROMPT,
    CONF_AI_PROVIDER,
    CONF_CLOSE_ON_STARTUP,
    CONF_COEFFICIENT,
    CONF_DRY_THRESHOLD,
    CONF_EXPOSURE,
    CONF_FLOW_RATE,
    CONF_FORMULA,
    CONF_HUMIDITY,
    CONF_MAX_DURATION,
    CONF_MIN_DURATION,
    CONF_MOISTURE,
    CONF_NOTIFY,
    CONF_PLANTS,
    CONF_RAIN_SENSOR,
    CONF_RUN_MODE,
    CONF_SAFETY_MINUTES,
    CONF_SOIL_VOLUME,
    CONF_START_MODE,
    CONF_START_TIME,
    CONF_SUNSET_OFFSET,
    CONF_TEMPERATURE,
    CONF_VALVE,
    CONF_WEATHER,
    CONF_ZONE_ANCHOR,
    CONF_ZONE_DAYS,
    CONF_ZONE_NAME,
    CONF_ZONE_SCHEDULE,
    DEFAULT_AI_ON_ERROR,
    DEFAULT_CLOSE_ON_STARTUP,
    DEFAULT_COEFFICIENT,
    DEFAULT_DRY_THRESHOLD,
    DEFAULT_EXPOSURE,
    DEFAULT_FLOW_RATE,
    DEFAULT_FORMULA,
    DEFAULT_MAX_DURATION,
    DEFAULT_MIN_DURATION,
    DEFAULT_RUN_MODE,
    DEFAULT_SAFETY_MINUTES,
    DEFAULT_SCHEDULE,
    DEFAULT_SOIL_VOLUME,
    DEFAULT_START_MODE,
    DEFAULT_START_TIME,
    DEFAULT_SUNSET_OFFSET,
    DEFAULT_ZONE_DAYS,
    DOMAIN,
    DRY_DELAY,
    DRY_HYSTERESIS,
    RAIN_STATES,
    RUN_MODE_SEQUENTIAL,
    SCHEDULE_ALTERNATE,
    SCHEDULE_DAYS,
    SCHEDULE_KEYS,
    SCHEDULE_OFF,
    SCHEDULES,
    SOURCE_SCHEDULE,
    SOURCE_SERVICE,
    START_MODE_SUNRISE,
    START_MODE_TIME,
    STARTUP_CLOSE_DELAY,
    STATUS_BLOCKED,
    STATUS_IDLE,
    STATUS_RUNNING,
    SUBENTRY_ZONE,
    WEEKDAYS,
    sensor_says_rain,
)
from .formula import FormulaError, render_formula
from .history import IrrigationHistory
from .live import LiveActivity
from .messages import tr

_LOGGER = logging.getLogger(__name__)

OPEN_STATES = {STATE_ON, STATE_OPEN, STATE_OPENING}


async def _sleep(seconds: float) -> None:
    """Attesa (sostituibile nei test)."""
    await asyncio.sleep(seconds)


@dataclass(frozen=True)
class ZoneConfig:
    """Configurazione di una zona (da subentry)."""

    zone_id: str
    name: str
    valve: str
    moisture_sensor: str | None
    flow_rate: float
    min_duration: int
    max_duration: int
    coefficient: float
    soil_volume: float
    exposure: str
    formula: str | None = None
    plants: str | None = None
    schedule: str = DEFAULT_SCHEDULE
    days: tuple[str, ...] = tuple(DEFAULT_ZONE_DAYS)
    anchor: date | None = None

    def irrigates_on(self, day: date) -> bool:
        """True se la zona va irrigata nel giorno (locale)."""
        return zone_irrigates_on(day, self.schedule, self.days, self.anchor)

    @classmethod
    def from_subentry(cls, subentry_id: str, data: dict[str, Any]) -> ZoneConfig:
        """Crea la configurazione dai dati della subentry."""
        return cls(
            zone_id=subentry_id,
            name=data[CONF_ZONE_NAME],
            valve=data[CONF_VALVE],
            moisture_sensor=data.get(CONF_MOISTURE) or None,
            flow_rate=float(data.get(CONF_FLOW_RATE, DEFAULT_FLOW_RATE)),
            min_duration=int(data.get(CONF_MIN_DURATION, DEFAULT_MIN_DURATION)),
            max_duration=int(data.get(CONF_MAX_DURATION, DEFAULT_MAX_DURATION)),
            coefficient=float(data.get(CONF_COEFFICIENT, DEFAULT_COEFFICIENT)),
            soil_volume=float(data.get(CONF_SOIL_VOLUME, DEFAULT_SOIL_VOLUME)),
            exposure=data.get(CONF_EXPOSURE, DEFAULT_EXPOSURE),
            formula=(data.get(CONF_FORMULA) or "").strip() or None,
            plants=(data.get(CONF_PLANTS) or "").strip() or None,
            schedule=(
                data.get(CONF_ZONE_SCHEDULE)
                if data.get(CONF_ZONE_SCHEDULE) in SCHEDULES
                else DEFAULT_SCHEDULE
            ),
            days=tuple(
                d for d in WEEKDAYS if d in data.get(CONF_ZONE_DAYS, DEFAULT_ZONE_DAYS)
            ),
            anchor=_parse_date(data.get(CONF_ZONE_ANCHOR)),
        )


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def structure_key(entry: ConfigEntry) -> str:
    """Impronta della configurazione esclusa la programmazione delle zone.

    Se cambia solo la programmazione (giorni, modalità) non serve ricaricare.
    """
    zones = {
        sub_id: {
            "title": sub.title,
            **{k: v for k, v in sub.data.items() if k not in SCHEDULE_KEYS},
        }
        for sub_id, sub in entry.subentries.items()
    }
    return json.dumps(
        {"data": dict(entry.data), "options": dict(entry.options), "zones": zones},
        sort_keys=True,
        default=str,
    )


@dataclass
class ZoneRun:
    """Stato di una zona nel ciclo in corso."""

    minutes: int
    starts_at: datetime
    ends_at: datetime
    active: bool = False
    done: bool = False


def _float_state(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """Valore numerico di un'entità, None se non disponibile."""
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return None
    try:
        return float(state.state)
    except ValueError:
        return None


class IrrigationController:
    """Gestisce un impianto (una config entry) e le sue zone."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Inizializza il controller."""
        self.hass = hass
        self.entry = entry
        self.zones: dict[str, ZoneConfig] = {
            subentry_id: ZoneConfig.from_subentry(subentry_id, dict(sub.data))
            for subentry_id, sub in entry.subentries.items()
            if sub.subentry_type == SUBENTRY_ZONE
        }

        # Impostazioni modificate dalle entità (ripristinate al riavvio)
        self.manual_timer: int = 0
        self.rain_block: bool = True

        # Stato del ciclo
        self.running = False
        # Opzioni o zone cambiate durante un ciclo: si ricarica alla fine
        self.reload_pending = False
        self.structure = structure_key(entry)
        self.run_source: str | None = None
        self.zone_runs: dict[str, ZoneRun] = {}
        self.last_block: str | None = None
        self.last_block_at: datetime | None = None
        self.last_run_end: datetime | None = None

        self.formula_errors: dict[str, str] = {}

        # Analisi AI
        self.ai_enabled: bool = False
        self.ai_result: AiResult | None = None
        self.ai_error: str | None = None
        self.ai_error_at: datetime | None = None
        self.ai_last_used: bool = False
        self._ai_lock = asyncio.Lock()

        self.history = IrrigationHistory(hass, entry.entry_id)
        self.live = LiveActivity(self)
        self.manual_close_at: dict[str, datetime] = {}

        self._run_task: asyncio.Task | None = None
        self._unsubs: list[Callable[[], None]] = []
        self._safety_timers: dict[str, Callable[[], None]] = {}

        # Allarme terriccio secco: zone secche e timer in attesa
        self.dry: dict[str, bool] = {}
        self._dry_timers: dict[str, Callable[[], None]] = {}

    # ------------------------------------------------------------------
    # Configurazione
    # ------------------------------------------------------------------
    @property
    def config(self) -> dict[str, Any]:
        """Configurazione dell'impianto (data + options)."""
        return {**self.entry.data, **self.entry.options}

    @property
    def signal(self) -> str:
        """Segnale dispatcher per aggiornare le entità."""
        return f"{DOMAIN}_{self.entry.entry_id}_update"

    @property
    def status(self) -> str:
        """Stato sintetico dell'impianto."""
        if self.running:
            return STATUS_RUNNING
        if self.last_block:
            return STATUS_BLOCKED
        return STATUS_IDLE

    def _zone_by_valve(self, entity_id: str) -> ZoneConfig | None:
        for zone in self.zones.values():
            if zone.valve == entity_id:
                return zone
        return None

    # ------------------------------------------------------------------
    # Ciclo di vita
    # ------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Avvia ascoltatori e programmazione (storico già caricato)."""
        now = dt_util.utcnow()
        for zone in self.zones.values():
            if self._is_open(zone.valve):
                # Valvola già aperta (es. riavvio): si conta da adesso
                self.history.valve_opened(zone.zone_id, now, manual=False)
        self._unsubs.append(
            async_track_time_interval(self.hass, self._handle_tick, timedelta(seconds=30))
        )
        self._unsubs.append(
            async_track_time_change(
                self.hass, self._handle_midnight, hour=0, minute=0, second=5
            )
        )
        self._unsubs.append(self._track_start())
        self._setup_dry_alarm()
        valves = [zone.valve for zone in self.zones.values()]
        if valves:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, valves, self._handle_valve_change
                )
            )
        if self.config.get(CONF_CLOSE_ON_STARTUP, DEFAULT_CLOSE_ON_STARTUP):
            if self.hass.state is CoreState.running:
                self._schedule_startup_close()
            else:
                self._unsubs.append(
                    self.hass.bus.async_listen_once(
                        EVENT_HOMEASSISTANT_STARTED,
                        lambda _event: self._schedule_startup_close(),
                    )
                )

    async def async_shutdown(self) -> None:
        """Ferma tutto (scarico dell'integrazione)."""
        self.reload_pending = False  # si sta già scaricando
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        for cancel in (*self._safety_timers.values(), *self._dry_timers.values()):
            cancel()
        self._safety_timers.clear()
        self._dry_timers.clear()
        self.live.shutdown()
        if self.running:
            await self.async_stop(notify=False)
        self._count_water()
        await self.history.async_save()

    @callback
    def _handle_tick(self, _now: datetime) -> None:
        """Aggiorna i litri delle valvole aperte."""
        if self._count_water():
            self.history.schedule_save()
            self.async_update_listeners()

    @callback
    def _handle_midnight(self, _now: datetime) -> None:
        """Nuovo giorno (e forse nuovo mese): azzera i contatori parziali."""
        self._count_water()
        self.history.rollover()
        self.history.schedule_save()
        self.async_update_listeners()

    def _count_water(self) -> bool:
        """Conta l'acqua delle valvole aperte fino ad ora."""
        now = dt_util.utcnow()
        counted = False
        for zone in self.zones.values():
            if self.history.is_open(zone.zone_id):
                self.history.accumulate(zone.zone_id, zone.flow_rate, now)
                counted = True
        return counted

    @callback
    def _schedule_startup_close(self) -> None:
        """Dopo l'avvio, chiude le valvole rimaste aperte (es. riavvio a metà ciclo)."""

        async def _close_open_valves(_now: datetime) -> None:
            if self.running:
                return
            for zone in self.zones.values():
                if self._is_open(zone.valve):
                    _LOGGER.warning(
                        "Valvola %s aperta all'avvio senza ciclo attivo: la chiudo",
                        zone.valve,
                    )
                    await self._close_valve(zone.valve)

        self._unsubs.append(
            async_call_later(self.hass, STARTUP_CLOSE_DELAY, _close_open_valves)
        )

    @callback
    def async_update_listeners(self) -> None:
        """Notifica le entità."""
        async_dispatcher_send(self.hass, self.signal)

    # ------------------------------------------------------------------
    # Calcoli
    # ------------------------------------------------------------------
    def weather_state(self) -> str | None:
        """Stato attuale dell'entità meteo."""
        entity_id = self.config.get(CONF_WEATHER)
        state = self.hass.states.get(entity_id) if entity_id else None
        return state.state if state else None

    def outdoor_temperature(self) -> float | None:
        """Temperatura esterna: sensore dedicato o attributo dell'entità meteo."""
        value = _float_state(self.hass, self.config.get(CONF_TEMPERATURE))
        if value is not None:
            return value
        entity_id = self.config.get(CONF_WEATHER)
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is not None:
            try:
                return float(state.attributes.get("temperature"))
            except (TypeError, ValueError):
                return None
        return None

    def outdoor_humidity(self) -> float | None:
        """Umidità esterna: sensore dedicato o attributo dell'entità meteo."""
        value = _float_state(self.hass, self.config.get(CONF_HUMIDITY))
        if value is not None:
            return value
        entity_id = self.config.get(CONF_WEATHER)
        state = self.hass.states.get(entity_id) if entity_id else None
        if state is not None:
            try:
                return float(state.attributes.get("humidity"))
            except (TypeError, ValueError):
                return None
        return None

    # ------------------------------------------------------------------
    # Allarme terriccio secco
    # ------------------------------------------------------------------
    @property
    def dry_threshold(self) -> int:
        """Soglia di umidità del terriccio sotto cui scatta l'allarme (0 = spento)."""
        return int(self.config.get(CONF_DRY_THRESHOLD, DEFAULT_DRY_THRESHOLD))

    def _setup_dry_alarm(self) -> None:
        sensors = {z.moisture_sensor: z.zone_id for z in self.zones.values() if z.moisture_sensor}
        if not sensors or self.dry_threshold <= 0:
            return
        # Stato iniziale senza notificare (es. dopo un riavvio)
        for zone_id in sensors.values():
            moisture = self.zone_moisture(self.zones[zone_id])
            self.dry[zone_id] = moisture is not None and moisture < self.dry_threshold

        @callback
        def _changed(event: Event[EventStateChangedData]) -> None:
            zone_id = sensors.get(event.data["entity_id"])
            if zone_id in self.zones:
                self._check_dry(zone_id)

        self._unsubs.append(
            async_track_state_change_event(self.hass, list(sensors), _changed)
        )

    @callback
    def _check_dry(self, zone_id: str) -> None:
        zone = self.zones[zone_id]
        moisture = self.zone_moisture(zone)
        threshold = self.dry_threshold
        if moisture is None:
            return
        if moisture < threshold:
            if not self.dry.get(zone_id) and zone_id not in self._dry_timers:

                async def _confirm(_now: datetime) -> None:
                    self._dry_timers.pop(zone_id, None)
                    current = self.zone_moisture(zone)
                    if current is None or current >= threshold or self.dry.get(zone_id):
                        return
                    self.dry[zone_id] = True
                    self.async_update_listeners()
                    await self._notify(
                        tr(
                            self.hass,
                            "notify_dry",
                            zone=zone.name,
                            moisture=round(current),
                            threshold=threshold,
                        )
                    )

                self._dry_timers[zone_id] = async_call_later(self.hass, DRY_DELAY, _confirm)
            return
        if cancel := self._dry_timers.pop(zone_id, None):
            cancel()
        if self.dry.get(zone_id) and moisture >= threshold + DRY_HYSTERESIS:
            self.dry[zone_id] = False
            self.async_update_listeners()

    def zone_moisture(self, zone: ZoneConfig) -> float | None:
        """Umidità del terriccio della zona."""
        return _float_state(self.hass, zone.moisture_sensor)

    def system_formula(self) -> str:
        """Formula dell'impianto (predefinita se non impostata)."""
        return (self.config.get(CONF_FORMULA) or "").strip() or DEFAULT_FORMULA

    def zone_formula(self, zone: ZoneConfig) -> tuple[str, str]:
        """Formula usata per la zona e da dove viene (zone/system/default)."""
        if zone.formula:
            return zone.formula, "zone"
        custom = (self.config.get(CONF_FORMULA) or "").strip()
        if custom and custom != DEFAULT_FORMULA:
            return custom, "system"
        return DEFAULT_FORMULA, "default"

    def zone_variables(self, zone: ZoneConfig) -> dict[str, Any]:
        """Variabili a disposizione della formula per la zona."""
        return formula_variables(
            moisture=self.zone_moisture(zone),
            temperature=self.outdoor_temperature(),
            humidity=self.outdoor_humidity(),
            weather=self.weather_state(),
            raining=self.is_raining(),
            coefficient=zone.coefficient,
            flow_rate=zone.flow_rate,
            soil_volume=zone.soil_volume,
            exposure=zone.exposure,
            min_duration=zone.min_duration,
            max_duration=zone.max_duration,
            plants=zone.plants,
        )

    def calculated_minutes(self, zone: ZoneConfig) -> int:
        """Durata calcolata con la formula (personalizzata o predefinita).

        Se la formula personalizzata fallisce si usa quella predefinita e
        l'errore resta in formula_errors (mostrato dal sensore della zona).
        """
        formula, _source = self.zone_formula(zone)
        try:
            value = render_formula(self.hass, formula, self.zone_variables(zone))
        except FormulaError as err:
            message = str(err)
            if self.formula_errors.get(zone.zone_id) != message:
                _LOGGER.warning(
                    "Formula della zona %s non valida (%s): uso quella predefinita",
                    zone.name,
                    message,
                )
            self.formula_errors[zone.zone_id] = message
            return calculate_duration(
                self.zone_moisture(zone),
                self.outdoor_temperature(),
                self.weather_state(),
                coefficient=zone.coefficient,
                min_minutes=zone.min_duration,
                max_minutes=zone.max_duration,
            )
        self.formula_errors.pop(zone.zone_id, None)
        return clamp_minutes(value, zone.min_duration, zone.max_duration)

    def planned_minutes(self, zone: ZoneConfig) -> int:
        """Durata che verrebbe usata ora (timer manuale o formula)."""
        if self.manual_timer > 0:
            return self.manual_timer
        return self.calculated_minutes(zone)

    def rain_sensor_state(self) -> bool | None:
        """Cosa dice il sensore pioggia (None se non c'è o non risponde)."""
        entity_id = self.config.get(CONF_RAIN_SENSOR)
        state = self.hass.states.get(entity_id) if entity_id else None
        return sensor_says_rain(state.state if state else None)

    def is_raining(self) -> bool:
        """True se piove: decide il sensore pioggia, se non c'è (o non risponde) il meteo."""
        sensor = self.rain_sensor_state()
        if sensor is not None:
            return sensor
        return self.weather_state() in RAIN_STATES

    def rain_description(self) -> str:
        """Da dove arriva l'informazione sulla pioggia (per il registro)."""
        entity_id = self.config.get(CONF_RAIN_SENSOR)
        if entity_id and self.rain_sensor_state() is not None:
            state = self.hass.states.get(entity_id)
            return tr(self.hass, "block_rain_sensor_desc", sensor=state.name, state=state.state)
        return tr(self.hass, "block_rain_desc", weather=self.weather_state())

    def remaining_minutes(self) -> int:
        """Minuti rimanenti al termine del ciclo in corso."""
        if not self.running or not self.zone_runs:
            return 0
        end = max(run.ends_at for run in self.zone_runs.values())
        return max(0, int(round((end - dt_util.utcnow()).total_seconds() / 60)))

    @property
    def start_mode(self) -> str:
        """Riferimento dell'orario: alba, tramonto o orario fisso."""
        return str(self.config.get(CONF_START_MODE, DEFAULT_START_MODE))

    def _start_offset(self) -> timedelta:
        return timedelta(
            minutes=int(self.config.get(CONF_SUNSET_OFFSET, DEFAULT_SUNSET_OFFSET))
        )

    def _start_time(self) -> tuple[int, int]:
        raw = str(self.config.get(CONF_START_TIME) or DEFAULT_START_TIME)
        parsed = dt_util.parse_time(raw) or dt_util.parse_time(DEFAULT_START_TIME)
        return parsed.hour, parsed.minute

    def _track_start(self) -> Callable[[], None]:
        """Registra il trigger dell'avvio programmato."""
        mode = self.start_mode
        if mode == START_MODE_TIME:
            hour, minute = self._start_time()
            return async_track_time_change(
                self.hass, self._handle_start, hour=hour, minute=minute, second=0
            )
        track = async_track_sunrise if mode == START_MODE_SUNRISE else async_track_sunset
        return track(self.hass, self._handle_start, self._start_offset())

    def start_on(self, day: Any) -> datetime | None:
        """Orario di avvio (UTC) per un giorno locale, senza controllare la frequenza."""
        mode = self.start_mode
        if mode == START_MODE_TIME:
            hour, minute = self._start_time()
            local = datetime.combine(
                day, time(hour, minute), tzinfo=dt_util.get_default_time_zone()
            )
            return dt_util.as_utc(local)
        event = SUN_EVENT_SUNRISE if mode == START_MODE_SUNRISE else SUN_EVENT_SUNSET
        when = get_astral_event_date(self.hass, event, day)
        if when is None:
            return None
        return when + self._start_offset()

    def zones_due(self, day: date) -> list[str]:
        """Zone da irrigare nel giorno (locale)."""
        return [zid for zid, zone in self.zones.items() if zone.irrigates_on(day)]

    def next_run(self, zone_id: str | None = None) -> datetime | None:
        """Prossima irrigazione programmata (UTC), dell'impianto o di una zona."""
        today = dt_util.now().date()
        now = dt_util.utcnow()
        for offset in range(15):
            day = today + timedelta(days=offset)
            if zone_id is None:
                if not self.zones_due(day):
                    continue
            elif zone_id not in self.zones or not self.zones[zone_id].irrigates_on(day):
                continue
            when = self.start_on(day)
            if when is not None and when > now:
                return when
        return None

    @callback
    def refresh_zones(self) -> None:
        """Rilegge le zone (cambiata solo la programmazione: niente ricarica)."""
        self.zones = {
            subentry_id: ZoneConfig.from_subentry(subentry_id, dict(sub.data))
            for subentry_id, sub in self.entry.subentries.items()
            if sub.subentry_type == SUBENTRY_ZONE
        }
        self.async_update_listeners()

    @callback
    def async_set_schedule(
        self, zone_id: str, mode: str | None = None, days: list[str] | None = None
    ) -> None:
        """Cambia modalità e/o giorni di una zona (dalla card o da un'azione)."""
        sub = self.entry.subentries[zone_id]
        data = dict(sub.data)
        current = data.get(CONF_ZONE_SCHEDULE, DEFAULT_SCHEDULE)
        if days is not None:
            days = [d for d in WEEKDAYS if d in days]
            data[CONF_ZONE_DAYS] = days
            if mode is None:
                mode = SCHEDULE_DAYS if days else SCHEDULE_OFF
        if mode is not None:
            if mode == SCHEDULE_DAYS and not data.get(CONF_ZONE_DAYS):
                data[CONF_ZONE_DAYS] = list(DEFAULT_ZONE_DAYS)
            if mode == SCHEDULE_ALTERNATE and (
                current != SCHEDULE_ALTERNATE or not data.get(CONF_ZONE_ANCHOR)
            ):
                # Si parte da oggi: oggi sì, domani no, ...
                data[CONF_ZONE_ANCHOR] = dt_util.now().date().isoformat()
            data[CONF_ZONE_SCHEDULE] = mode
        if data != dict(sub.data):
            self.hass.config_entries.async_update_subentry(self.entry, sub, data=data)

    # ------------------------------------------------------------------
    # Analisi AI
    # ------------------------------------------------------------------
    @property
    def ai_configured(self) -> bool:
        """True se è stato scelto un provider AI."""
        return (self.config.get(CONF_AI_PROVIDER) or AI_NONE) != AI_NONE

    @property
    def ai_active(self) -> bool:
        """L'analisi AI decide i cicli."""
        return self.ai_configured and self.ai_enabled

    async def async_build_ai_context(self) -> dict[str, Any]:
        """Dati inviati al modello."""
        weather_entity = self.config.get(CONF_WEATHER)
        now = dt_util.now()
        return {
            "now": now.isoformat(timespec="minutes"),
            "location": {
                "latitude": round(self.hass.config.latitude, 1),
                "longitude": round(self.hass.config.longitude, 1),
            },
            "weather_now": {
                "condition": self.weather_state(),
                "temperature_c": self.outdoor_temperature(),
                "humidity_percent": self.outdoor_humidity(),
            },
            "raining_now": self.is_raining(),
            "rain_last_hours": await async_rain_history(
                self.hass, weather_entity, rain_sensor=self.config.get(CONF_RAIN_SENSOR)
            ),
            "forecast_next_hours": await async_forecast(self.hass, weather_entity),
            "zones": [
                {
                    "index": index,
                    "name": zone.name,
                    "plants": zone.plants,
                    "soil_moisture_percent": self.zone_moisture(zone),
                    "soil_volume_liters": zone.soil_volume,
                    "exposure": zone.exposure,
                    "flow_rate_liters_per_minute": zone.flow_rate,
                    "min_minutes": zone.min_duration,
                    "max_minutes": zone.max_duration,
                    "formula_minutes": self.calculated_minutes(zone),
                }
                for index, zone in enumerate(self.zones.values(), start=1)
            ],
        }

    async def async_analyze(self) -> AiResult:
        """Chiede all'AI se e quanto irrigare. Solleva AiError se fallisce."""
        if not self.ai_configured:
            raise AiError("analisi AI non configurata")
        if not self.zones:
            raise AiError("nessuna zona configurata")
        async with self._ai_lock:
            try:
                context = await self.async_build_ai_context()
                prompt = build_prompt(
                    self.hass,
                    context,
                    self.hass.config.language or "en",
                    self.config.get(CONF_AI_INSTRUCTIONS),
                    self.config.get(CONF_AI_PROMPT),
                )
                data = await async_query(self.hass, self.config, prompt, len(self.zones))
                result = parse_result(
                    data, list(self.zones.values()), self.config[CONF_AI_PROVIDER]
                )
            except AiError as err:
                self.ai_error = str(err)
                self.ai_error_at = dt_util.utcnow()
                self.async_update_listeners()
                _LOGGER.warning("Analisi AI non riuscita: %s", err)
                raise
            self.ai_result = result
            self.ai_error = None
            self.async_update_listeners()
            return result

    # ------------------------------------------------------------------
    # Programmazione
    # ------------------------------------------------------------------
    @callback
    def _handle_start(self, _now: datetime | None = None) -> None:
        due = self.zones_due(dt_util.now().date())
        if not due:
            return
        self.hass.async_create_task(self.async_start(SOURCE_SCHEDULE, zone_ids=due))

    # ------------------------------------------------------------------
    # Avvio / arresto
    # ------------------------------------------------------------------
    async def async_start(
        self,
        source: str,
        duration: int | None = None,
        force: bool = False,
        zone_ids: list[str] | None = None,
    ) -> bool:
        """Avvia un ciclo (tutte le zone o solo `zone_ids`). False se non parte."""
        if self.running:
            _LOGGER.debug("Ciclo già in corso, avvio ignorato")
            return False
        if not self.zones:
            _LOGGER.warning("Nessuna zona configurata")
            return False
        if zone_ids is None:
            # Avvio manuale: tutte le zone tranne quelle spente
            zone_ids = [
                zid for zid, zone in self.zones.items() if zone.schedule != SCHEDULE_OFF
            ]
        if not zone_ids:
            _LOGGER.info("Tutte le zone sono spente: nessuna irrigazione")
            return False

        if self.rain_block and not force and self.is_raining():
            self.last_block = "rain"
            self.last_block_at = dt_util.utcnow()
            self.history.add_block(
                tr(self.hass, "block_rain"),
                self.rain_description(),
            )
            self.async_update_listeners()
            await self._notify(tr(self.hass, "notify_rain"))
            return False

        durations: dict[str, int] = {}
        self.ai_last_used = False
        use_ai = duration is None and self.manual_timer <= 0 and self.ai_active
        if use_ai:
            try:
                result = await self.async_analyze()
            except AiError as err:
                on_error = self.config.get(CONF_AI_ON_ERROR, DEFAULT_AI_ON_ERROR)
                if on_error == AI_ON_ERROR_SKIP:
                    self.last_block = "ai_error"
                    self.last_block_at = dt_util.utcnow()
                    self.history.add_block(tr(self.hass, "block_ai_error"), str(err))
                    self.async_update_listeners()
                    await self._notify(tr(self.hass, "notify_ai_error_skip", error=err))
                    return False
                if on_error == AI_ON_ERROR_DISABLE:
                    self.ai_enabled = False
                    self.async_update_listeners()
                    await self._notify(tr(self.hass, "notify_ai_error_disable", error=err))
                else:
                    await self._notify(tr(self.hass, "notify_ai_error_formula", error=err))
            else:
                if not result.irrigate:
                    self.last_block = "ai"
                    self.last_block_at = dt_util.utcnow()
                    self.history.add_block(tr(self.hass, "block_ai"), result.reason)
                    self.async_update_listeners()
                    await self._notify(tr(self.hass, "notify_ai_skip", reason=result.reason))
                    return False
                durations = {
                    zone_id: zr.minutes
                    for zone_id, zr in result.zones.items()
                    if zr.minutes > 0
                    and zone_id in self.zones
                    and (zone_ids is None or zone_id in zone_ids)
                }
                self.ai_last_used = True

        if not self.ai_last_used:
            for zone_id, zone in self.zones.items():
                if zone_ids is not None and zone_id not in zone_ids:
                    continue
                minutes = duration if duration is not None else self.planned_minutes(zone)
                if minutes > 0:
                    durations[zone_id] = int(minutes)
        if not durations:
            return False

        self._plan(durations)
        titles = {SOURCE_SCHEDULE: "cycle_schedule", SOURCE_SERVICE: "cycle_service"}
        summary = tr(self.hass, titles.get(source, "cycle_manual"))
        note = None
        if self.ai_last_used and self.ai_result is not None:
            summary += " · AI"
            note = (
                tr(self.hass, "note_ai", reason=self.ai_result.reason)
                if self.ai_result.reason
                else None
            )
        elif duration is None and self.manual_timer > 0:
            note = tr(self.hass, "note_timer", minutes=self.manual_timer)
        self.history.cycle_started(
            summary,
            {zid: (self.zones[zid].name, mins) for zid, mins in durations.items()},
            note,
        )
        self.last_block = None
        self.running = True
        self.run_source = source
        self.async_update_listeners()

        details = ", ".join(
            f"{self.zones[zid].name}: {mins} min" for zid, mins in durations.items()
        )
        origin = " (AI)" if self.ai_last_used else ""
        await self.live.async_update(silent=False)
        await self._notify(tr(self.hass, "notify_started", origin=origin, details=details))

        self._run_task = self.entry.async_create_background_task(
            self.hass, self._async_run(), name=f"{DOMAIN}_run_{self.entry.entry_id}"
        )
        return True

    def _plan(self, durations: dict[str, int]) -> None:
        """Calcola orari di inizio/fine di ogni zona."""
        now = dt_util.utcnow()
        sequential = self.config.get(CONF_RUN_MODE, DEFAULT_RUN_MODE) == RUN_MODE_SEQUENTIAL
        self.zone_runs = {}
        start = now
        for zone_id, minutes in durations.items():
            end = start + timedelta(minutes=minutes)
            self.zone_runs[zone_id] = ZoneRun(minutes=minutes, starts_at=start, ends_at=end)
            if sequential:
                start = end

    async def _async_run(self) -> None:
        sequential = self.config.get(CONF_RUN_MODE, DEFAULT_RUN_MODE) == RUN_MODE_SEQUENTIAL
        try:
            if sequential:
                for zone_id in list(self.zone_runs):
                    await self._async_run_zone(zone_id)
            else:
                await asyncio.gather(
                    *(self._async_run_zone(zone_id) for zone_id in list(self.zone_runs))
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception("Errore durante il ciclo di irrigazione")
            await self._close_all()
        self._count_water()
        event = self.history.cycle_finished(interrupted=False)
        self.running = False
        self.last_run_end = dt_util.utcnow()
        self._run_task = None
        self.async_update_listeners()
        await self.live.async_finish(event, interrupted=False)
        await self._notify(tr(self.hass, "notify_finished"))
        self._apply_pending_reload()

    @callback
    def _apply_pending_reload(self) -> None:
        """Applica la configurazione salvata durante il ciclo appena finito."""
        if self.reload_pending:
            self.reload_pending = False
            _LOGGER.info("Ciclo finito: applico la nuova configurazione")
            self.hass.config_entries.async_schedule_reload(self.entry.entry_id)

    async def _async_run_zone(self, zone_id: str) -> None:
        zone = self.zones[zone_id]
        run = self.zone_runs[zone_id]
        # Ricalcola gli orari a partire da adesso (in sequenza le zone
        # successive partono quando finisce la precedente).
        run.starts_at = dt_util.utcnow()
        run.ends_at = run.starts_at + timedelta(minutes=run.minutes)
        run.active = True
        self.async_update_listeners()
        await self._open_valve(zone.valve)
        try:
            await _sleep(run.minutes * 60)
        finally:
            run.active = False
            run.done = True
        if self._is_open(zone.valve):
            await self._close_valve(zone.valve)
        self.async_update_listeners()
        if any(not r.done for r in self.zone_runs.values()):
            await self.live.async_update(silent=True)

    async def async_stop(self, notify: bool = True) -> None:
        """Interrompe il ciclo in corso e chiude le valvole."""
        was_running = self.running
        task = self._run_task
        self._run_task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        for run in self.zone_runs.values():
            run.active = False
        await self._close_all()
        self.running = False
        if was_running:
            self._count_water()
            event = self.history.cycle_finished(interrupted=True)
            self.last_run_end = dt_util.utcnow()
            await self.live.async_finish(event, interrupted=True)
        self.async_update_listeners()
        if was_running and notify:
            await self._notify(tr(self.hass, "notify_stopped"))
        self._apply_pending_reload()

    # ------------------------------------------------------------------
    # Valvole
    # ------------------------------------------------------------------
    def _is_open(self, entity_id: str) -> bool:
        state = self.hass.states.get(entity_id)
        return state is not None and state.state in OPEN_STATES

    async def _open_valve(self, entity_id: str) -> None:
        domain = entity_id.split(".", 1)[0]
        service = "open_valve" if domain == "valve" else "turn_on"
        await self.hass.services.async_call(
            domain, service, {"entity_id": entity_id}, blocking=True
        )

    async def _close_valve(self, entity_id: str) -> None:
        domain = entity_id.split(".", 1)[0]
        service = "close_valve" if domain == "valve" else "turn_off"
        for attempt in range(CLOSE_RETRIES):
            try:
                await self.hass.services.async_call(
                    domain, service, {"entity_id": entity_id}, blocking=True
                )
            except Exception:  # noqa: BLE001 - riproviamo comunque
                _LOGGER.warning("Chiusura di %s fallita (tentativo %s)", entity_id, attempt + 1)
            await _sleep(CLOSE_RETRY_DELAY)
            if not self._is_open(entity_id):
                return
        _LOGGER.error("Impossibile chiudere la valvola %s", entity_id)
        await self._notify(tr(self.hass, "notify_valve_stuck", valve=entity_id))

    async def _close_all(self) -> None:
        to_close = [z.valve for z in self.zones.values() if self._is_open(z.valve)]
        if to_close:
            await asyncio.gather(*(self._close_valve(v) for v in to_close))

    # ------------------------------------------------------------------
    # Sicurezza per aperture manuali
    # ------------------------------------------------------------------
    @callback
    def _handle_valve_change(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        new_state = event.data["new_state"]
        zone = self._zone_by_valve(entity_id)
        if zone is None or new_state is None:
            return
        is_open = new_state.state in OPEN_STATES
        run = self.zone_runs.get(zone.zone_id) if self.running else None
        by_cycle = run is not None and run.active

        if not is_open:
            manual_event = self.history.valve_closed(
                zone.zone_id, zone.name, zone.flow_rate, new_state.last_changed
            )
            if cancel := self._safety_timers.pop(entity_id, None):
                cancel()
            self.manual_close_at.pop(entity_id, None)
            self.async_update_listeners()
            if not self.running and self.live.active:
                if any(self.history.is_open(z) for z in self.zones):
                    self.hass.async_create_task(self.live.async_update(silent=True))
                else:
                    self.hass.async_create_task(
                        self.live.async_finish(manual_event, interrupted=False)
                    )
            return

        was_counting = self.history.is_open(zone.zone_id)
        self.history.valve_opened(zone.zone_id, new_state.last_changed, manual=not by_cycle)
        if by_cycle or was_counting:
            return  # aperta dal ciclo, o già nota

        minutes = int(self.config.get(CONF_SAFETY_MINUTES, DEFAULT_SAFETY_MINUTES))
        if minutes > 0 and entity_id not in self._safety_timers:

            async def _safety_close(_now: datetime) -> None:
                self._safety_timers.pop(entity_id, None)
                if self._is_open(entity_id):
                    await self._close_valve(entity_id)
                    await self._notify(
                        tr(self.hass, "notify_safety", zone=zone.name, minutes=minutes)
                    )

            self._safety_timers[entity_id] = async_call_later(
                self.hass, minutes * 60, _safety_close
            )
            self.manual_close_at[entity_id] = dt_util.utcnow() + timedelta(minutes=minutes)
        self.async_update_listeners()
        if not self.running:
            self.hass.async_create_task(self.live.async_update(silent=self.live.active))

    # ------------------------------------------------------------------
    # Notifiche
    # ------------------------------------------------------------------
    async def _notify(self, message: str) -> None:
        services = self.config.get(CONF_NOTIFY) or []
        title = self.entry.title
        for service in services:
            domain, _, name = service.partition(".")
            if not name:
                domain, name = "notify", domain
            try:
                await self.hass.services.async_call(
                    domain, name, {"title": title, "message": message}, blocking=False
                )
            except Exception:  # noqa: BLE001
                _LOGGER.warning("Notifica tramite %s fallita", service)
