"""Storico delle irrigazioni e consumi d'acqua (persistenti)."""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
SAVE_DELAY = 10
MAX_EVENTS = 1000

KIND_CYCLE = "cycle"
KIND_MANUAL = "manual"
KIND_BLOCK = "block"


@dataclass
class HistoryEvent:
    """Un evento dello storico (ciclo, apertura manuale o blocco)."""

    uid: str
    kind: str
    start: str  # ISO UTC
    end: str  # ISO UTC
    summary: str
    description: str = ""
    zones: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def start_dt(self) -> datetime:
        """Inizio."""
        return dt_util.parse_datetime(self.start) or dt_util.utcnow()

    @property
    def end_dt(self) -> datetime:
        """Fine."""
        return dt_util.parse_datetime(self.end) or self.start_dt


@dataclass
class ZoneCounters:
    """Litri erogati da una zona."""

    total: float = 0.0
    day: float = 0.0
    month: float = 0.0


class IrrigationHistory:
    """Consumi per zona ed eventi, salvati in .storage."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Inizializza."""
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"irrigazione_ai.{entry_id}"
        )
        self.counters: dict[str, ZoneCounters] = {}
        self.events: list[HistoryEvent] = []
        self._day: str = ""
        self._month: str = ""
        # Valvole aperte: zone_id -> momento dell'ultimo conteggio
        self._open_since: dict[str, datetime] = {}
        # Ciclo in corso
        self._cycle: dict[str, Any] | None = None
        # Aperture manuali in corso: zone_id -> (inizio, litri all'inizio)
        self._manual: dict[str, tuple[datetime, float]] = {}

    # ------------------------------------------------------------------
    # Persistenza
    # ------------------------------------------------------------------
    async def async_load(self) -> None:
        """Carica i dati salvati."""
        data = await self._store.async_load() or {}
        self._day = data.get("day", "")
        self._month = data.get("month", "")
        self.counters = {
            zone_id: ZoneCounters(**values)
            for zone_id, values in data.get("counters", {}).items()
        }
        self.events = [HistoryEvent(**item) for item in data.get("events", [])]
        self._rollover(dt_util.now())

    def _data(self) -> dict[str, Any]:
        return {
            "day": self._day,
            "month": self._month,
            "counters": {zid: asdict(c) for zid, c in self.counters.items()},
            "events": [asdict(e) for e in self.events[-MAX_EVENTS:]],
        }

    def schedule_save(self) -> None:
        """Salva con un piccolo ritardo (raggruppa le scritture)."""
        self._store.async_delay_save(self._data, SAVE_DELAY)

    async def async_save(self) -> None:
        """Salva subito."""
        await self._store.async_save(self._data())

    async def async_remove(self) -> None:
        """Cancella i dati (integrazione rimossa)."""
        await self._store.async_remove()

    # ------------------------------------------------------------------
    # Consumi
    # ------------------------------------------------------------------
    def _rollover(self, now_local: datetime) -> None:
        day = now_local.strftime("%Y-%m-%d")
        month = now_local.strftime("%Y-%m")
        if day != self._day:
            for c in self.counters.values():
                c.day = 0.0
            self._day = day
        if month != self._month:
            for c in self.counters.values():
                c.month = 0.0
            self._month = month

    def rollover(self) -> None:
        """Azzera giorno/mese se sono cambiati."""
        self._rollover(dt_util.now())

    def _add(self, zone_id: str, liters: float) -> None:
        self._rollover(dt_util.now())
        counters = self.counters.setdefault(zone_id, ZoneCounters())
        counters.total = round(counters.total + liters, 3)
        counters.day = round(counters.day + liters, 3)
        counters.month = round(counters.month + liters, 3)

    def zone(self, zone_id: str) -> ZoneCounters:
        """Contatori della zona (dopo l'eventuale cambio di giorno/mese)."""
        self._rollover(dt_util.now())
        return self.counters.get(zone_id, ZoneCounters())

    def totals(self, zone_ids: list[str]) -> ZoneCounters:
        """Somma dei contatori delle zone indicate."""
        out = ZoneCounters()
        for zone_id in zone_ids:
            c = self.zone(zone_id)
            out.total += c.total
            out.day += c.day
            out.month += c.month
        return ZoneCounters(round(out.total, 1), round(out.day, 1), round(out.month, 1))

    def is_open(self, zone_id: str) -> bool:
        """True se stiamo contando l'acqua della zona."""
        return zone_id in self._open_since

    def valve_opened(self, zone_id: str, when: datetime, *, manual: bool) -> None:
        """Una valvola si è aperta."""
        if zone_id in self._open_since:
            return
        self._open_since[zone_id] = when
        if manual:
            self._manual[zone_id] = (when, self.zone(zone_id).total)

    def accumulate(self, zone_id: str, flow_rate: float, now: datetime) -> float:
        """Aggiunge l'acqua erogata dall'ultimo conteggio. Ritorna i litri."""
        since = self._open_since.get(zone_id)
        if since is None:
            return 0.0
        seconds = max(0.0, (now - since).total_seconds())
        liters = flow_rate * seconds / 60
        if liters > 0:
            self._add(zone_id, liters)
        self._open_since[zone_id] = now
        return liters

    def valve_closed(
        self, zone_id: str, zone_name: str, flow_rate: float, when: datetime
    ) -> None:
        """Una valvola si è chiusa: conteggio finale ed eventuale evento manuale."""
        if zone_id not in self._open_since:
            return
        self.accumulate(zone_id, flow_rate, when)
        del self._open_since[zone_id]
        if (manual := self._manual.pop(zone_id, None)) is not None:
            start, liters_before = manual
            liters = self.zone(zone_id).total - liters_before
            minutes = max(0, round((when - start).total_seconds() / 60))
            self._add_event(
                HistoryEvent(
                    uid=uuid.uuid4().hex,
                    kind=KIND_MANUAL,
                    start=start.isoformat(),
                    end=max(when, start).isoformat(),
                    summary=f"Apertura manuale: {zone_name}",
                    description=f"{zone_name}: {minutes} min, {liters:.1f} L",
                    zones={zone_id: {"name": zone_name, "minutes": minutes, "liters": round(liters, 1)}},
                )
            )
        self.schedule_save()

    # ------------------------------------------------------------------
    # Eventi
    # ------------------------------------------------------------------
    def _add_event(self, event: HistoryEvent) -> None:
        self.events.append(event)
        if len(self.events) > MAX_EVENTS:
            self.events = self.events[-MAX_EVENTS:]

    def cycle_started(
        self,
        summary: str,
        planned: dict[str, tuple[str, int]],
        note: str | None = None,
    ) -> None:
        """Inizio di un ciclo. planned: zone_id -> (nome, minuti previsti)."""
        self._cycle = {
            "start": dt_util.utcnow(),
            "summary": summary,
            "note": note,
            "planned": planned,
            "before": {zid: self.zone(zid).total for zid in planned},
        }

    def cycle_finished(self, *, interrupted: bool) -> HistoryEvent | None:
        """Fine del ciclo: crea l'evento con litri e minuti reali."""
        cycle, self._cycle = self._cycle, None
        if cycle is None:
            return None
        end = dt_util.utcnow()
        zones: dict[str, dict[str, Any]] = {}
        lines = []
        total = 0.0
        for zone_id, (name, minutes) in cycle["planned"].items():
            liters = max(0.0, self.zone(zone_id).total - cycle["before"][zone_id])
            total += liters
            zones[zone_id] = {"name": name, "minutes": minutes, "liters": round(liters, 1)}
            lines.append(f"{name}: {minutes} min, {liters:.1f} L")
        if cycle["note"]:
            lines.append(cycle["note"])
        if interrupted:
            lines.append("Interrotta prima della fine.")
        lines.append(f"Totale: {total:.1f} L")
        summary = cycle["summary"] + (" (interrotta)" if interrupted else "")
        event = HistoryEvent(
            uid=uuid.uuid4().hex,
            kind=KIND_CYCLE,
            start=cycle["start"].isoformat(),
            end=max(end, cycle["start"]).isoformat(),
            summary=summary,
            description="\n".join(lines),
            zones=zones,
        )
        self._add_event(event)
        self.schedule_save()
        return event

    def add_block(self, summary: str, description: str = "") -> None:
        """Ciclo non partito (pioggia, AI...)."""
        now = dt_util.utcnow()
        self._add_event(
            HistoryEvent(
                uid=uuid.uuid4().hex,
                kind=KIND_BLOCK,
                start=now.isoformat(),
                end=now.isoformat(),
                summary=summary,
                description=description,
            )
        )
        self.schedule_save()

    def events_between(self, start: datetime, end: datetime) -> list[HistoryEvent]:
        """Eventi che si sovrappongono all'intervallo."""
        return [e for e in self.events if e.start_dt < end and e.end_dt >= start]
