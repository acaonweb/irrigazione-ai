"""Blocchi meteo prima di un ciclo: pioggia prevista, gelo, vento forte.

Ogni controllo usa solo i dati che ci sono. Se il servizio meteo non dà le
previsioni orarie, il vento o la temperatura, quel controllo si salta e
l'irrigazione va avanti: un dato mancante non blocca mai l'impianto.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from .const import RAIN_FORECAST_MM, RAIN_FORECAST_PROBABILITY, RAIN_STATES

_LOGGER = logging.getLogger(__name__)

# Fattori di conversione verso km/h
_WIND_UNITS: dict[str, float] = {
    "km/h": 1.0,
    "kmh": 1.0,
    "m/s": 3.6,
    "mph": 1.609344,
    "mi/h": 1.609344,
    "kn": 1.852,
    "kt": 1.852,
    "knots": 1.852,
    "ft/s": 1.09728,
}


@dataclass(frozen=True)
class Block:
    """Motivo per cui un ciclo non parte."""

    reason: str  # rain_forecast, frost, wind
    values: dict[str, Any]


def wind_kmh(value: Any, unit: str | None) -> float | None:
    """Velocità del vento in km/h (None se il valore o l'unità non si capiscono)."""
    try:
        speed = float(value)
    except (TypeError, ValueError):
        return None
    factor = _WIND_UNITS.get((unit or "km/h").strip().lower())
    if factor is None:
        return None
    return round(speed * factor, 1)


def wind_from_state(state: State | None, attribute: str | None = None) -> float | None:
    """Vento da un sensore (stato) o da un'entità meteo (attributo wind_speed)."""
    if state is None:
        return None
    if attribute:
        return wind_kmh(
            state.attributes.get(attribute), state.attributes.get("wind_speed_unit")
        )
    return wind_kmh(state.state, state.attributes.get("unit_of_measurement"))


def _item_time(item: dict[str, Any]) -> datetime | None:
    raw = item.get("datetime") or item.get("time")
    if not raw:
        return None
    parsed = raw if isinstance(raw, datetime) else dt_util.parse_datetime(str(raw))
    return dt_util.as_utc(parsed) if parsed else None


def _window(
    forecast: list[dict[str, Any]] | None, hours: int, now: datetime
) -> list[dict[str, Any]]:
    """Voci orarie che cadono nelle prossime `hours` ore (compresa l'ora in corso)."""
    if not forecast or hours <= 0:
        return []
    end = now + timedelta(hours=hours)
    items = []
    for item in forecast:
        when = _item_time(item)
        if when is None:
            continue
        if when + timedelta(hours=1) > now and when < end:
            items.append(item)
    return items


def _rainy(item: dict[str, Any]) -> bool:
    if item.get("condition") in RAIN_STATES:
        return True
    try:
        if float(item.get("precipitation") or 0) >= RAIN_FORECAST_MM:
            return True
    except (TypeError, ValueError):
        pass
    try:
        return float(item.get("precipitation_probability") or 0) >= RAIN_FORECAST_PROBABILITY
    except (TypeError, ValueError):
        return False


def rain_expected(
    forecast: list[dict[str, Any]] | None, hours: int, now: datetime
) -> dict[str, Any] | None:
    """Prima ora piovosa nelle prossime `hours` ore, None se non ce ne sono o mancano i dati."""
    for item in _window(forecast, hours, now):
        if _rainy(item):
            when = _item_time(item)
            return {
                "at": dt_util.as_local(when).strftime("%H:%M") if when else "",
                "condition": item.get("condition"),
                "precipitation": item.get("precipitation"),
                "probability": item.get("precipitation_probability"),
            }
    return None


def min_temperature(
    current: float | None, forecast: list[dict[str, Any]] | None, hours: int, now: datetime
) -> float | None:
    """Temperatura più bassa fra quella attuale e le prossime ore."""
    values = [current] if current is not None else []
    for item in _window(forecast, hours, now):
        try:
            values.append(float(item["temperature"]))
        except (KeyError, TypeError, ValueError):
            continue
    return min(values) if values else None


async def async_hourly_forecast(
    hass: HomeAssistant, weather_entity: str | None
) -> list[dict[str, Any]] | None:
    """Previsioni orarie grezze dell'entità meteo (None se non disponibili)."""
    if not weather_entity or not hass.services.has_service("weather", "get_forecasts"):
        return None
    try:
        response = await hass.services.async_call(
            "weather",
            "get_forecasts",
            {"entity_id": weather_entity, "type": "hourly"},
            blocking=True,
            return_response=True,
        )
    except Exception as err:  # noqa: BLE001 - previsioni orarie non supportate
        _LOGGER.debug("Previsioni orarie di %s non disponibili: %s", weather_entity, err)
        return None
    return (response or {}).get(weather_entity, {}).get("forecast") or None
