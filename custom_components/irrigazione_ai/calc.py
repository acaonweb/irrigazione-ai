"""Calcolo della durata di irrigazione (formula meteo).

Funzioni pure, senza dipendenze da Home Assistant, per poterle testare
facilmente.
"""

from __future__ import annotations

from datetime import date, datetime

from .const import (
    FREQ_DAILY,
    FREQ_OFF,
    FREQ_TWICE_WEEKLY,
    FREQ_WEEKLY,
    SCHEDULE_ALTERNATE,
    SCHEDULE_DAILY,
    SCHEDULE_DAYS,
    WEEKDAYS,
)

# Fattore moltiplicativo per stato meteo (entità weather di HA).
WEATHER_FACTORS: dict[str, float] = {
    "sunny": 1.1,
    "clear-night": 1.0,
    "partlycloudy": 0.8,
    "cloudy": 0.5,
    "fog": 0.6,
    "windy": 1.0,
    "windy-variant": 0.8,
    "lightning": 0.5,
    "rainy": 0.2,
    "pouring": 0.2,
    "lightning-rainy": 0.2,
    "snowy-rainy": 0.2,
    "hail": 0.2,
    "snowy": 0.2,
    "exceptional": 1.0,
}

DEFAULT_MOISTURE = 50.0
DEFAULT_TEMPERATURE = 20.0
MIN_MOISTURE = 10.0


def weather_factor(weather: str | None) -> float:
    """Fattore moltiplicativo per lo stato meteo."""
    return WEATHER_FACTORS.get(weather or "", 1.0)


def clamp_minutes(value: float, min_minutes: int, max_minutes: int) -> int:
    """Limita e arrotonda una durata."""
    low, high = min(min_minutes, max_minutes), max(min_minutes, max_minutes)
    return int(round(min(max(value, low), high)))


def formula_variables(
    *,
    moisture: float | None,
    temperature: float | None,
    humidity: float | None,
    weather: str | None,
    coefficient: float,
    flow_rate: float,
    soil_volume: float,
    exposure: str,
    min_duration: int,
    max_duration: int,
    plants: str | None = None,
) -> dict[str, object]:
    """Variabili a disposizione della formula personalizzata.

    moisture ha un minimo del 10% (50% se manca il sensore) e temperature
    vale 20 °C se manca, così la formula non divide mai per zero.
    """
    hum = DEFAULT_MOISTURE if moisture is None else moisture
    return {
        "moisture": max(hum, MIN_MOISTURE),
        "moisture_raw": moisture,
        "temperature": DEFAULT_TEMPERATURE if temperature is None else temperature,
        "humidity": humidity,
        "weather": weather or "",
        "weather_factor": weather_factor(weather),
        "coefficient": coefficient,
        "flow_rate": flow_rate,
        "soil_volume": soil_volume,
        "exposure": exposure,
        "min_duration": min_duration,
        "max_duration": max_duration,
        "plants": plants or "",
    }


def calculate_duration(
    moisture: float | None,
    temperature: float | None,
    weather: str | None,
    *,
    coefficient: float = 1.0,
    min_minutes: int = 15,
    max_minutes: int = 120,
) -> int:
    """Durata in minuti per una zona.

    Formula storica dell'impianto:
        t = (20 + 20 * (100 - u) / u + 20 * T / 25) * 0.9
    con u = umidità del terriccio (minimo 10%), T = temperatura esterna,
    poi moltiplicata per il fattore meteo e il coefficiente della zona e
    limitata tra min_minutes e max_minutes.
    """
    hum = DEFAULT_MOISTURE if moisture is None else moisture
    hum = max(hum, MIN_MOISTURE)
    temp = DEFAULT_TEMPERATURE if temperature is None else temperature

    minutes = (20 + 20 * (100 - hum) / hum + 20 * temp / 25) * 0.9
    minutes *= weather_factor(weather)
    minutes *= coefficient
    return clamp_minutes(minutes, min_minutes, max_minutes)


def is_irrigation_day(
    when: datetime,
    frequency: str,
    weekly_day: str,
    twice_weekly_days: list[str],
) -> bool:
    """True se `when` (ora locale) è un giorno di irrigazione."""
    day = WEEKDAYS[when.weekday()]
    if frequency == FREQ_OFF:
        return False
    if frequency == FREQ_DAILY:
        return True
    if frequency == FREQ_WEEKLY:
        return day == weekly_day
    if frequency == FREQ_TWICE_WEEKLY:
        return day in twice_weekly_days
    return False


def zone_irrigates_on(
    day: date, mode: str, days: list[str] | tuple[str, ...], anchor: date | None
) -> bool:
    """True se la zona va irrigata nel giorno (locale) indicato."""
    if mode == SCHEDULE_DAILY:
        return True
    if mode == SCHEDULE_DAYS:
        return WEEKDAYS[day.weekday()] in days
    if mode == SCHEDULE_ALTERNATE:
        # Un giorno sì e uno no, contando dal giorno in cui è stato scelto
        if anchor is None:
            return True
        return (day - anchor).days % 2 == 0
    return False
