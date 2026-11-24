"""Calendario: storico delle irrigazioni e prossimo ciclo previsto."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import IrrigazioneConfigEntry
from .controller import IrrigationController
from .entity import IrrigazioneEntity
from .history import HistoryEvent

BLOCK_LENGTH = timedelta(minutes=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrrigazioneConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Crea il calendario."""
    async_add_entities([IrrigationCalendar(entry.runtime_data)])


def _to_event(item: HistoryEvent) -> CalendarEvent:
    start = dt_util.as_local(item.start_dt)
    end = dt_util.as_local(item.end_dt)
    if end <= start:
        end = start + BLOCK_LENGTH
    return CalendarEvent(
        start=start,
        end=end,
        summary=item.summary,
        description=item.description or None,
        uid=item.uid,
    )


class IrrigationCalendar(IrrigazioneEntity, CalendarEntity):
    """Cicli eseguiti, aperture manuali, cicli saltati e prossimo ciclo."""

    def __init__(self, controller: IrrigationController) -> None:
        """Inizializza."""
        super().__init__(controller, "calendar")

    def _planned_event(self) -> CalendarEvent | None:
        """Prossimo ciclo programmato (stima con le durate attuali)."""
        c = self.controller
        if c.running:
            return None
        when = c.next_run()
        if when is None or not c.zones:
            return None
        due = c.zones_due(dt_util.as_local(when).date())
        minutes = {c.zones[zid].name: c.planned_minutes(c.zones[zid]) for zid in due}
        length = max(minutes.values(), default=0)
        if c.config.get("run_mode") == "sequential":
            length = sum(minutes.values())
        start = dt_util.as_local(when)
        lines = [f"{name}: {mins} min (stima)" for name, mins in minutes.items()]
        if c.ai_active:
            lines.append("La durata la deciderà l'AI al momento dell'avvio.")
        return CalendarEvent(
            start=start,
            end=start + timedelta(minutes=max(length, 1)),
            summary="Irrigazione prevista",
            description="\n".join(lines),
            uid=f"{c.entry.entry_id}_planned",
        )

    def _running_event(self) -> CalendarEvent | None:
        """Ciclo in corso."""
        c = self.controller
        if not c.running or not c.zone_runs:
            return None
        start = min(run.starts_at for run in c.zone_runs.values())
        end = max(run.ends_at for run in c.zone_runs.values())
        return CalendarEvent(
            start=dt_util.as_local(start),
            end=dt_util.as_local(end),
            summary="Irrigazione in corso",
            uid=f"{c.entry.entry_id}_running",
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Evento in corso o il prossimo."""
        return self._running_event() or self._planned_event()

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Eventi nell'intervallo richiesto."""
        events = [
            _to_event(item)
            for item in self.controller.history.events_between(
                dt_util.as_utc(start_date), dt_util.as_utc(end_date)
            )
        ]
        for extra in (self._running_event(), self._planned_event()):
            if extra is not None and extra.start < end_date and extra.end > start_date:
                events.append(extra)
        return sorted(events, key=lambda e: e.start)
