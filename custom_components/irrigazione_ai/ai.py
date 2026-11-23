"""Analisi AI: dati, prompt, chiamata al modello e lettura della risposta.

Sostituisce il workflow n8n (agente meteo + agente agronomo) con un'unica
richiesta. Funziona con un'entità AI Task di Home Assistant oppure
chiamando direttamente OpenAI, Anthropic, Google Gemini od Ollama.
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .calc import clamp_minutes
from .const import (
    AI_ANTHROPIC,
    AI_FORECAST_HOURS,
    AI_GEMINI,
    AI_OLLAMA,
    AI_OPENAI,
    AI_RAIN_HOURS,
    AI_TASK,
    AI_TIMEOUT,
    CONF_AI_API_KEY,
    CONF_AI_BASE_URL,
    CONF_AI_MODEL,
    CONF_AI_PROVIDER,
    CONF_AI_TASK_ENTITY,
    DEFAULT_AI_MODELS,
    DEFAULT_OLLAMA_URL,
    RAIN_STATES,
)

_LOGGER = logging.getLogger(__name__)

LANGUAGES = {"it": "Italian", "en": "English", "de": "German", "fr": "French", "es": "Spanish"}


class AiError(Exception):
    """Errore generico dell'analisi AI."""


class AiAuthError(AiError):
    """Chiave API non valida."""


class AiConnectionError(AiError):
    """Servizio non raggiungibile."""


@dataclass
class AiZoneResult:
    """Esito per una zona."""

    zone_id: str
    name: str
    liters: float
    minutes: int
    reason: str


@dataclass
class AiResult:
    """Esito di un'analisi."""

    irrigate: bool
    reason: str
    at: datetime
    provider: str
    zones: dict[str, AiZoneResult] = field(default_factory=dict)


# ----------------------------------------------------------------------
# Dati
# ----------------------------------------------------------------------


async def async_rain_history(
    hass: HomeAssistant, weather_entity: str | None, hours: int = AI_RAIN_HOURS
) -> dict[str, Any] | None:
    """Quanto ha piovuto nelle ultime ore secondo lo storico dell'entità meteo."""
    if not weather_entity or "recorder" not in hass.config.components:
        return None
    from homeassistant.components.recorder import get_instance, history  # noqa: PLC0415

    end = dt_util.utcnow()
    start = end - timedelta(hours=hours)
    try:
        states = await get_instance(hass).async_add_executor_job(
            history.state_changes_during_period,
            hass,
            start,
            end,
            weather_entity,
            True,  # no_attributes
            False,  # descending
            None,  # limit
            True,  # include_start_time_state
        )
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Storico meteo non disponibile", exc_info=True)
        return None
    items = states.get(weather_entity, [])
    if not items:
        return None
    rainy_seconds = 0.0
    for index, state in enumerate(items):
        begin = max(state.last_changed, start)
        finish = items[index + 1].last_changed if index + 1 < len(items) else end
        if state.state in RAIN_STATES and finish > begin:
            rainy_seconds += (finish - begin).total_seconds()
    total = hours * 3600
    return {
        "hours": hours,
        "rain_hours": round(rainy_seconds / 3600, 1),
        "rain_percent": round(100 * rainy_seconds / total),
        "rained": rainy_seconds > 0,
    }


async def async_forecast(
    hass: HomeAssistant, weather_entity: str | None, hours: int = AI_FORECAST_HOURS
) -> list[dict[str, Any]] | None:
    """Previsioni delle prossime ore (oraria, altrimenti giornaliera)."""
    if not weather_entity or not hass.services.has_service("weather", "get_forecasts"):
        return None
    for kind, count in (("hourly", hours), ("daily", 2)):
        try:
            response = await hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": weather_entity, "type": kind},
                blocking=True,
                return_response=True,
            )
        except Exception:  # noqa: BLE001 - tipo non supportato dall'entità
            continue
        forecast = (response or {}).get(weather_entity, {}).get("forecast") or []
        if forecast:
            return [
                {
                    "time": item.get("datetime"),
                    "condition": item.get("condition"),
                    "temperature": item.get("temperature"),
                    "precipitation_mm": item.get("precipitation"),
                    "precipitation_probability": item.get("precipitation_probability"),
                    "humidity": item.get("humidity"),
                }
                for item in forecast[:count]
            ]
    return None


# ----------------------------------------------------------------------
# Prompt
# ----------------------------------------------------------------------


# Prompt predefinito (template Jinja). Variabili: data_json (tutti i dati in
# JSON), data (gli stessi come dizionario), zones, weather_now,
# rain_last_hours, forecast_next_hours, notes (note del proprietario),
# language (lingua delle risposte). Il formato della risposta viene sempre
# aggiunto in fondo dall'integrazione.
DEFAULT_AI_PROMPT = """You are an agronomist expert in precision irrigation and a meteorologist.
Decide whether the garden should be watered now and how many liters each zone needs.

Data fields:
- weather_now: current condition, outdoor temperature (°C) and outdoor air humidity (%).
- rain_last_hours: hours and percentage of time it rained in the recent hours, and whether it rained at all.
- forecast_next_hours: hourly forecast (condition, temperature, precipitation in mm and its probability).
- zones: for each zone, soil_moisture_percent (0-100%), soil_volume_liters (liters of substrate to water), exposure (north/south/east/west: affects evaporation and sun), flow_rate_liters_per_minute, min_minutes/max_minutes and formula_minutes (the duration of the classic formula, for reference).

Data (JSON):
{{ data_json }}

Your goal, for each zone:
1. Estimate the expected evapotranspiration of the substrate.
2. Estimate how much water is already present thanks to rain (fallen and expected).
3. Compute the liters of water to add, sized on the soil volume: a larger substrate needs more liters to reach the same moisture.

Rules:
- If it rained for more than 50% of the recent hours, or significant rain is expected in the next hours, set irrigate to false; if it rained less, reduce the liters proportionally.
- If the soil moisture of a zone is above 70%, give that zone 0 liters.
- If the soil moisture is between 50% and 65%, still give a small maintenance amount, even for large soil volumes (over 1000 L).
- South exposure increases evaporation, north exposure reduces it.
- Higher temperatures increase the water need.
- Do not invent missing data: if something is missing or unclear, make a prudent estimate.
{%- if notes %}
- Notes from the owner: {{ notes }}
{%- endif %}"""


def output_instructions(zone_count: int, language: str) -> str:
    """Formato della risposta (sempre in fondo al prompt, non modificabile)."""
    lang = LANGUAGES.get(language.split("-")[0], "English")
    keys = ", ".join(
        f'"zone_{i}_liters": number, "zone_{i}_reason": "string"'
        for i in range(1, zone_count + 1)
    )
    return (
        "Answer ONLY with a JSON object with exactly these keys:\n"
        f'{{"irrigate": true or false, "reason": "string", {keys}}}\n'
        "The zone numbers refer to the 'index' field of each zone. "
        "Each liters value is just the number, without units. "
        f"Write every reason in {lang}: a short technical summary of what you computed, "
        "at most 15 words. If a zone gets 0 liters because of rain, its reason must only "
        "say that it rained enough. If irrigate is false, every zone gets 0 liters."
    )


def build_prompt(
    hass: HomeAssistant,
    context: dict[str, Any],
    language: str,
    notes: str | None,
    template: str | None = None,
) -> str:
    """Prompt completo: istruzioni (predefinite o personalizzate) + formato risposta.

    Solleva AiError se il template personalizzato non funziona.
    """
    from homeassistant.exceptions import TemplateError  # noqa: PLC0415
    from homeassistant.helpers.template import Template  # noqa: PLC0415

    source = (template or "").strip() or DEFAULT_AI_PROMPT
    data_json = json.dumps(context, ensure_ascii=False, default=str)
    variables = {
        "data": context,
        "data_json": data_json,
        "zones": context.get("zones", []),
        "weather_now": context.get("weather_now"),
        "rain_last_hours": context.get("rain_last_hours"),
        "forecast_next_hours": context.get("forecast_next_hours"),
        "notes": (notes or "").strip(),
        "language": LANGUAGES.get(language.split("-")[0], "English"),
    }
    try:
        instructions = Template(source, hass).async_render(variables, parse_result=False)
    except TemplateError as err:
        raise AiError(f"prompt non valido: {err}") from err
    except Exception as err:  # noqa: BLE001
        raise AiError(f"prompt non valido: {err}") from err
    instructions = str(instructions).strip()
    if not instructions:
        raise AiError("il prompt è vuoto")
    if "data" not in source:
        # Il prompt personalizzato non usa i dati: li aggiungiamo noi
        instructions += f"\n\nData (JSON):\n{data_json}"
    return f"{instructions}\n\n{output_instructions(len(context.get('zones', [])), language)}"


def build_structure(zone_count: int) -> dict[str, Any]:
    """Struttura per ai_task.generate_data (stesse chiavi del JSON)."""
    structure: dict[str, Any] = {
        "irrigate": {
            "description": "True if the garden should be watered now",
            "required": True,
            "selector": {"boolean": {}},
        },
        "reason": {
            "description": "Short explanation of the decision",
            "required": True,
            "selector": {"text": {}},
        },
    }
    for i in range(1, zone_count + 1):
        structure[f"zone_{i}_liters"] = {
            "description": f"Liters of water for zone {i}",
            "required": True,
            "selector": {"number": {"min": 0, "max": 100000, "step": 0.1, "mode": "box"}},
        }
        structure[f"zone_{i}_reason"] = {
            "description": f"Short explanation for zone {i}",
            "required": True,
            "selector": {"text": {}},
        }
    return structure


# ----------------------------------------------------------------------
# Chiamata al modello
# ----------------------------------------------------------------------


def parse_json_text(text: str) -> dict[str, Any]:
    """Estrae l'oggetto JSON dalla risposta testuale del modello."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise AiError("la risposta del modello non contiene JSON")
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as err:
        raise AiError(f"JSON non valido nella risposta: {err}") from err
    if not isinstance(data, dict):
        raise AiError("la risposta del modello non è un oggetto JSON")
    return data


def _error_message(body: str) -> str:
    """Il messaggio d'errore del provider (OpenAI, Anthropic, Gemini, Ollama)."""
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return body.strip()[:200]
    err = data.get("error") if isinstance(data, dict) else None
    if isinstance(err, dict):
        msg = err.get("message") or err.get("code") or err.get("type")
        if msg:
            return str(msg)[:300]
    if isinstance(err, str):
        return err[:300]
    return body.strip()[:200]


async def _post(
    hass: HomeAssistant, url: str, payload: dict[str, Any], headers: dict[str, str]
) -> dict[str, Any]:
    session = async_get_clientsession(hass)
    try:
        async with session.post(
            url,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=AI_TIMEOUT),
        ) as response:
            body = await response.text()
            if response.status in (401, 403) or (
                response.status == 400 and "API key" in body
            ):
                raise AiAuthError(f"HTTP {response.status}: {_error_message(body)}")
            if response.status >= 400:
                raise AiError(f"HTTP {response.status}: {_error_message(body)}")
            return json.loads(body)
    except (aiohttp.ClientError, TimeoutError) as err:
        raise AiConnectionError(f"servizio non raggiungibile: {err}") from err
    except json.JSONDecodeError as err:
        raise AiError("risposta non in formato JSON") from err


async def _query_text(hass: HomeAssistant, cfg: dict[str, Any], prompt: str) -> str:
    """Invia il prompt al provider scelto e restituisce il testo della risposta."""
    provider = cfg.get(CONF_AI_PROVIDER)
    model = (cfg.get(CONF_AI_MODEL) or "").strip() or DEFAULT_AI_MODELS.get(provider, "")
    key = (cfg.get(CONF_AI_API_KEY) or "").strip()
    try:
        if provider == AI_OPENAI:
            data = await _post(
                hass,
                "https://api.openai.com/v1/chat/completions",
                {
                    "model": model,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "user", "content": prompt}],
                },
                {"Authorization": f"Bearer {key}"},
            )
            return data["choices"][0]["message"]["content"]
        if provider == AI_ANTHROPIC:
            data = await _post(
                hass,
                "https://api.anthropic.com/v1/messages",
                {
                    "model": model,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                },
                {"x-api-key": key, "anthropic-version": "2023-06-01"},
            )
            return "".join(
                part.get("text", "") for part in data["content"] if part.get("type") == "text"
            )
        if provider == AI_GEMINI:
            data = await _post(
                hass,
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                {
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json"},
                },
                {"x-goog-api-key": key},
            )
            return data["candidates"][0]["content"]["parts"][0]["text"]
        if provider == AI_OLLAMA:
            base = (cfg.get(CONF_AI_BASE_URL) or DEFAULT_OLLAMA_URL).rstrip("/")
            data = await _post(
                hass,
                f"{base}/api/chat",
                {
                    "model": model,
                    "stream": False,
                    "format": "json",
                    "messages": [{"role": "user", "content": prompt}],
                },
                {},
            )
            return data["message"]["content"]
    except (KeyError, IndexError, TypeError) as err:
        raise AiError("risposta del modello in un formato inatteso") from err
    raise AiError(f"provider non supportato: {provider}")


async def async_query(
    hass: HomeAssistant, cfg: dict[str, Any], prompt: str, zone_count: int
) -> dict[str, Any]:
    """Chiede l'analisi al modello e restituisce il dizionario della risposta."""
    if cfg.get(CONF_AI_PROVIDER) == AI_TASK:
        entity_id = cfg.get(CONF_AI_TASK_ENTITY)
        if not entity_id or hass.states.get(entity_id) is None:
            raise AiError("entità AI Task non trovata")
        try:
            response = await hass.services.async_call(
                "ai_task",
                "generate_data",
                {
                    "entity_id": entity_id,
                    "task_name": "Irrigazione AI",
                    "instructions": prompt,
                    "structure": build_structure(zone_count),
                },
                blocking=True,
                return_response=True,
            )
        except Exception as err:  # noqa: BLE001
            raise AiError(f"AI Task: {err}") from err
        data = (response or {}).get("data")
        if isinstance(data, str):
            return parse_json_text(data)
        if not isinstance(data, dict):
            raise AiError("AI Task non ha restituito dati strutturati")
        return data
    return parse_json_text(await _query_text(hass, cfg, prompt))


async def async_validate(hass: HomeAssistant, cfg: dict[str, Any]) -> None:
    """Verifica la configurazione con una richiesta minima."""
    if cfg.get(CONF_AI_PROVIDER) == AI_TASK:
        entity_id = cfg.get(CONF_AI_TASK_ENTITY)
        if not entity_id or hass.states.get(entity_id) is None:
            raise AiError("entità AI Task non trovata")
        return
    text = await _query_text(
        hass, cfg, 'This is a connection test. Reply only with the JSON object {"ok": true}.'
    )
    parse_json_text(text)


# ----------------------------------------------------------------------
# Lettura dell'esito
# ----------------------------------------------------------------------


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "si", "sì", "1")
    return bool(value)


def _as_float(value: Any) -> float:
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) and number > 0 else 0.0


def parse_result(
    data: dict[str, Any], zones: list[Any], provider: str
) -> AiResult:
    """Converte la risposta in litri e minuti per zona.

    `zones` è la lista di ZoneConfig nello stesso ordine usato nel prompt.
    I minuti sono litri / portata, arrotondati per eccesso e limitati tra
    durata minima e massima della zona; 0 litri = zona non irrigata.
    """
    if "irrigate" not in data:
        raise AiError("risposta incompleta: manca 'irrigate'")
    irrigate = _as_bool(data.get("irrigate"))
    result = AiResult(
        irrigate=irrigate,
        reason=str(data.get("reason") or "").strip(),
        at=dt_util.utcnow(),
        provider=provider,
    )
    for index, zone in enumerate(zones, start=1):
        liters = _as_float(data.get(f"zone_{index}_liters")) if irrigate else 0.0
        minutes = 0
        if liters > 0 and zone.flow_rate > 0:
            minutes = clamp_minutes(
                # round() evita che 21.78 / 0.726 = 30.0000001 diventi 31
                math.ceil(round(liters / zone.flow_rate, 6)),
                zone.min_duration,
                zone.max_duration,
            )
        result.zones[zone.zone_id] = AiZoneResult(
            zone_id=zone.zone_id,
            name=zone.name,
            liters=round(liters, 1),
            minutes=minutes,
            reason=str(data.get(f"zone_{index}_reason") or "").strip(),
        )
    if irrigate and not any(z.minutes for z in result.zones.values()):
        result.irrigate = False
    return result
