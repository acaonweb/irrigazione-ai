"""Autoapprendimento: ogni zona impara quanta acqua le serve davvero.

Dopo un'irrigazione completa si guarda fin dove sale l'umidità del terriccio
nelle ore successive. Se il picco resta sotto l'obiettivo, la prossima volta
la zona riceve un po' più d'acqua; se lo supera, un po' meno. La correzione
è un fattore che moltiplica i minuti della formula o dell'AI.

Si salta l'osservazione (il fattore non cambia) se la zona non ha un sensore,
se il ciclo è stato interrotto, se piove durante l'osservazione o se il
sensore non manda valori.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    LEARN_MAX_FACTOR,
    LEARN_MAX_STEP,
    LEARN_MIN_FACTOR,
    LEARN_TOLERANCE,
)

STORAGE_VERSION = 1
SAVE_DELAY = 10


@dataclass
class ZoneLearning:
    """Quanto appreso su una zona."""

    factor: float = 1.0
    samples: int = 0
    last_before: float | None = None
    last_peak: float | None = None
    last_change: float | None = None  # variazione del fattore all'ultima osservazione
    last_at: str | None = None  # ISO UTC
    last_result: str | None = None  # raised, lowered, kept, skipped_rain, skipped_no_data


def next_factor(factor: float, peak: float, target: float) -> tuple[float, float]:
    """Nuovo fattore dato il picco di umidità raggiunto. Restituisce (fattore, variazione)."""
    error = target - peak
    if abs(error) <= LEARN_TOLERANCE:
        return factor, 0.0
    step = max(-LEARN_MAX_STEP, min(LEARN_MAX_STEP, error / 100))
    new = max(LEARN_MIN_FACTOR, min(LEARN_MAX_FACTOR, round(factor * (1 + step), 3)))
    return new, round(new - factor, 3)


def apply_factor(minutes: int, factor: float, min_minutes: int, max_minutes: int) -> int:
    """Minuti corretti dal fattore appreso, sempre fra minimo e massimo."""
    if minutes <= 0:
        return minutes
    value = int(round(minutes * factor))
    return max(min_minutes, min(max_minutes, value))


class LearningStore:
    """Fattori appresi per zona, salvati in .storage."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Inizializza."""
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"irrigazione_ai.{entry_id}.learning"
        )
        self.zones: dict[str, ZoneLearning] = {}

    async def async_load(self) -> None:
        """Carica i dati salvati."""
        data = await self._store.async_load() or {}
        self.zones = {}
        for zone_id, values in data.get("zones", {}).items():
            known = {k: v for k, v in values.items() if k in ZoneLearning.__dataclass_fields__}
            self.zones[zone_id] = ZoneLearning(**known)

    def _data(self) -> dict[str, Any]:
        return {"zones": {zid: asdict(z) for zid, z in self.zones.items()}}

    def schedule_save(self) -> None:
        """Salva con un piccolo ritardo."""
        self._store.async_delay_save(self._data, SAVE_DELAY)

    async def async_save(self) -> None:
        """Salva subito."""
        await self._store.async_save(self._data())

    async def async_remove(self) -> None:
        """Cancella i dati (integrazione rimossa)."""
        await self._store.async_remove()

    def get(self, zone_id: str) -> ZoneLearning:
        """Dati della zona (creati se mancano)."""
        return self.zones.setdefault(zone_id, ZoneLearning())

    def factor(self, zone_id: str) -> float:
        """Fattore attuale della zona (1 se non ha ancora imparato nulla)."""
        zone = self.zones.get(zone_id)
        return zone.factor if zone else 1.0

    def record(
        self, zone_id: str, before: float | None, peak: float, target: float
    ) -> ZoneLearning:
        """Registra un'osservazione e aggiorna il fattore."""
        zone = self.get(zone_id)
        new, change = next_factor(zone.factor, peak, target)
        zone.factor = new
        zone.samples += 1
        zone.last_before = before
        zone.last_peak = peak
        zone.last_change = change
        zone.last_at = dt_util.utcnow().isoformat()
        zone.last_result = "raised" if change > 0 else "lowered" if change < 0 else "kept"
        self.schedule_save()
        return zone

    def skip(self, zone_id: str, result: str) -> None:
        """Osservazione scartata (pioggia, nessun dato)."""
        zone = self.get(zone_id)
        zone.last_result = result
        zone.last_at = dt_util.utcnow().isoformat()
        self.schedule_save()

    def reset(self, zone_id: str) -> None:
        """Ricomincia da capo."""
        self.zones[zone_id] = ZoneLearning()
        self.schedule_save()
