"""Live Activity (iOS) / Live Update (Android) tramite l'app companion.

Una sola attività per impianto (stesso `tag`): si apre all'avvio di un ciclo
o di un'apertura manuale, si aggiorna in silenzio quando una zona parte o
finisce e si chiude con il riepilogo dei litri; dopo 5 minuti sparisce.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .const import CONF_LIVE_DEVICES, CONF_LIVE_URL, LIVE_CLEAR_DELAY, ZONE_NUMBERS
from .messages import liters_text, tr

if TYPE_CHECKING:
    from .controller import IrrigationController
    from .history import HistoryEvent

_LOGGER = logging.getLogger(__name__)

COLOR_ACTIVE = "#26A69A"
COLOR_DONE = "#4CAF50"
COLOR_STOPPED = "#FF9800"


def _hhmm(when: datetime) -> str:
    return dt_util.as_local(when).strftime("%H:%M")


class LiveActivity:
    """Gestisce la Live Activity di un impianto."""

    def __init__(self, controller: IrrigationController) -> None:
        """Inizializza."""
        self.controller = controller
        self.hass = controller.hass
        self.tag = f"irrigazione_ai_{controller.entry.entry_id}"
        self.active = False
        self._clear_unsub: Callable[[], None] | None = None

    @property
    def devices(self) -> list[str]:
        """Servizi notify dei dispositivi (notify.mobile_app_...)."""
        return list(self.controller.config.get(CONF_LIVE_DEVICES) or [])

    def _number(self, index: int) -> str:
        return ZONE_NUMBERS[index] if index < len(ZONE_NUMBERS) else f"{index + 1}."

    def _lines(self) -> tuple[list[str], datetime | None]:
        """Righe delle zone attive e ora di fine più lontana."""
        c = self.controller
        lines: list[str] = []
        last_end: datetime | None = None
        for index, (zone_id, zone) in enumerate(c.zones.items()):
            number = self._number(index)
            run = c.zone_runs.get(zone_id) if c.running else None
            if run is not None:
                if run.done:
                    lines.append("☑️ " + tr(self.hass, "live_zone_done", zone=zone.name))
                elif run.active or run.starts_at <= dt_util.utcnow() + timedelta(seconds=5):
                    lines.append(
                        f"{number} "
                        + tr(self.hass, "live_zone_ends", zone=zone.name, time=_hhmm(run.ends_at))
                    )
                    last_end = max(last_end or run.ends_at, run.ends_at)
                else:
                    lines.append(
                        "⏳ "
                        + tr(self.hass, "live_zone_waiting", zone=zone.name, time=_hhmm(run.starts_at))
                    )
                    last_end = max(last_end or run.ends_at, run.ends_at)
            elif c.history.is_open(zone_id):
                close_at = c.manual_close_at.get(zone.valve)
                tail = (
                    tr(self.hass, "live_manual_close", time=_hhmm(close_at)) if close_at else ""
                )
                lines.append(f"{number} " + tr(self.hass, "live_manual", zone=zone.name) + tail)
                if close_at:
                    last_end = max(last_end or close_at, close_at)
        return lines, last_end

    async def async_update(self, *, silent: bool) -> None:
        """Mostra o aggiorna l'attività con lo stato attuale."""
        if not self.devices:
            return
        lines, last_end = self._lines()
        if not lines:
            return
        c = self.controller
        if c.running:
            title = tr(self.hass, "live_running") + (" · AI" if c.ai_last_used else "")
        else:
            title = tr(self.hass, "live_valve_open")
        self._cancel_clear()
        self.active = True
        await self._send(
            title,
            "\n".join(lines),
            critical=_hhmm(last_end) if last_end else "",
            icon="mdi:valve-open",
            color=COLOR_ACTIVE,
            silent=silent,
        )

    async def async_finish(self, event: HistoryEvent | None, *, interrupted: bool) -> None:
        """Chiude l'attività con il riepilogo e la toglie dopo 5 minuti."""
        if not self.devices or not self.active:
            return
        lines: list[str] = []
        total = 0.0
        if event is not None:
            for zone in event.zones.values():
                total += zone.get("liters", 0)
                lines.append(
                    f"☑️ {zone['name']} · {zone['minutes']} min · "
                    f"{liters_text(self.hass, zone['liters'])} L"
                )
            if len(event.zones) > 1:
                lines.append(tr(self.hass, "live_total", liters=liters_text(self.hass, total)))
        title = tr(self.hass, "live_stopped" if interrupted else "live_done")
        await self._send(
            title,
            "\n".join(lines) or tr(self.hass, "live_all_done"),
            critical=tr(self.hass, "live_finished"),
            icon="mdi:check-circle",
            color=COLOR_STOPPED if interrupted else COLOR_DONE,
            silent=False,
        )
        self.active = False
        self._schedule_clear()

    async def _send(
        self, title: str, message: str, *, critical: str, icon: str, color: str, silent: bool
    ) -> None:
        data: dict[str, Any] = {
            "live_update": True,
            "tag": self.tag,
            "critical_text": critical,
            "notification_icon": icon,
            "notification_icon_color": color,
            "color": color,
            "silent": silent,
        }
        if url := self.controller.config.get(CONF_LIVE_URL):
            data["url"] = url
            data["clickAction"] = url
        await self._call_all({"title": title, "message": message, "data": data})

    async def _call_all(self, payload: dict[str, Any]) -> None:
        for device in self.devices:
            service = device.removeprefix("notify.")
            if not self.hass.services.has_service("notify", service):
                _LOGGER.debug("Servizio notify.%s non disponibile", service)
                continue
            try:
                await self.hass.services.async_call("notify", service, payload, blocking=False)
            except Exception:  # noqa: BLE001
                _LOGGER.warning("Live Activity su notify.%s non riuscita", service)

    def _cancel_clear(self) -> None:
        if self._clear_unsub is not None:
            self._clear_unsub()
            self._clear_unsub = None

    def _schedule_clear(self) -> None:
        self._cancel_clear()

        async def _clear(_now: datetime) -> None:
            self._clear_unsub = None
            if self.active:
                return  # nel frattempo è partito qualcos'altro
            await self._call_all({"message": "clear_notification", "data": {"tag": self.tag}})

        self._clear_unsub = async_call_later(self.hass, LIVE_CLEAR_DELAY, _clear)

    @callback
    def shutdown(self) -> None:
        """Annulla i timer."""
        self._cancel_clear()
