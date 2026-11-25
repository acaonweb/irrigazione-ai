"""Testi generati dall'integrazione (notifiche, Live Activity, calendario).

Seguono la lingua di sistema di Home Assistant (Impostazioni → Sistema →
Generale), perché nascono senza un utente davanti. Lingue senza traduzione:
inglese.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        # Cicli e blocchi
        "block_rain": "Watering skipped: rain",
        "block_rain_desc": "Weather: {weather}. Rain block on.",
        "block_rain_sensor_desc": "Rain sensor {sensor}: {state}. Rain block on.",
        "notify_rain": "Watering blocked: it is raining and the rain block is on.",
        "block_rain_forecast": "Watering skipped: rain expected",
        "block_rain_forecast_desc": "Rain expected around {at}, within the next {hours} h. Rain block on.",
        "notify_rain_forecast": "Watering skipped: rain is expected within the next {hours} hours (around {at}).",
        "block_frost": "Watering skipped: frost risk",
        "block_frost_desc": "Temperature {temperature} °C, below {threshold} °C.",
        "notify_frost": "Watering skipped: frost risk ({temperature} °C, threshold {threshold} °C).",
        "block_wind": "Watering skipped: strong wind",
        "block_wind_desc": "Wind {wind} km/h, above {threshold} km/h.",
        "notify_wind": "Watering skipped: strong wind ({wind} km/h, threshold {threshold} km/h).",
        "block_ai_error": "Watering skipped: AI analysis failed",
        "notify_ai_error_skip": "Watering cancelled: the AI analysis failed ({error}).",
        "notify_ai_error_disable": "AI analysis failed ({error}): AI analysis turned off, watering with the formula.",
        "notify_ai_error_formula": "AI analysis failed ({error}): watering with the formula.",
        "block_ai": "Watering skipped by the AI",
        "notify_ai_skip": "Watering skipped by the AI: {reason}",
        "cycle_schedule": "Scheduled watering",
        "cycle_service": "Watering (action)",
        "cycle_manual": "Manual watering",
        "note_ai": "AI: {reason}",
        "note_timer": "Manual timer: {minutes} min",
        "notify_started": "Watering started{origin}. {details}.",
        "notify_finished": "Watering finished.",
        "notify_stopped": "Watering stopped.",
        "notify_valve_stuck": "Warning: valve {valve} did not close.",
        "notify_safety": "{zone} closed automatically after {minutes} minutes (safety).",
        "notify_dry": "🌱 Dry soil: {zone} is at {moisture}% (threshold {threshold}%).",
        # Live Activity
        "live_running": "💧 Watering",
        "live_valve_open": "💧 Valve open",
        "live_zone_done": "{zone} done",
        "live_zone_ends": "{zone} · ends {time}",
        "live_zone_waiting": "{zone} · from {time}",
        "live_manual": "{zone} · opened by hand",
        "live_manual_close": " · closes {time}",
        "live_total": "Total {liters} L",
        "live_stopped": "⏹️ Watering stopped",
        "live_done": "☑️ Watering finished",
        "live_all_done": "All zones done",
        "live_finished": "Done",
        # Calendario e storico
        "cal_planned": "Planned watering",
        "cal_running": "Watering in progress",
        "cal_estimate": "{zone}: {minutes} min (estimate)",
        "cal_ai_decides": "The AI will decide the durations when the cycle starts.",
        "ev_manual": "Manual opening: {zone}",
        "ev_zone_line": "{zone}: {minutes} min, {liters} L",
        "ev_interrupted_line": "Stopped before the end.",
        "ev_interrupted": " (stopped)",
        "ev_total": "Total: {liters} L",
    },
    "it": {
        "block_rain": "Irrigazione saltata: pioggia",
        "block_rain_desc": "Meteo: {weather}. Blocco pioggia attivo.",
        "block_rain_sensor_desc": "Sensore pioggia {sensor}: {state}. Blocco pioggia attivo.",
        "notify_rain": "Irrigazione bloccata: sta piovendo e il blocco pioggia è attivo.",
        "block_rain_forecast": "Irrigazione saltata: pioggia prevista",
        "block_rain_forecast_desc": "Pioggia prevista verso le {at}, entro {hours} ore. Blocco pioggia attivo.",
        "notify_rain_forecast": "Irrigazione saltata: è prevista pioggia entro {hours} ore (verso le {at}).",
        "block_frost": "Irrigazione saltata: rischio gelo",
        "block_frost_desc": "Temperatura {temperature} °C, sotto {threshold} °C.",
        "notify_frost": "Irrigazione saltata: rischio gelo ({temperature} °C, soglia {threshold} °C).",
        "block_wind": "Irrigazione saltata: vento forte",
        "block_wind_desc": "Vento {wind} km/h, sopra {threshold} km/h.",
        "notify_wind": "Irrigazione saltata: vento forte ({wind} km/h, soglia {threshold} km/h).",
        "block_ai_error": "Irrigazione saltata: AI non riuscita",
        "notify_ai_error_skip": "Irrigazione annullata: l'analisi AI non è riuscita ({error}).",
        "notify_ai_error_disable": "Analisi AI non riuscita ({error}): analisi AI disattivata, irrigo con la formula.",
        "notify_ai_error_formula": "Analisi AI non riuscita ({error}): irrigo con la formula.",
        "block_ai": "Irrigazione saltata dall'AI",
        "notify_ai_skip": "Irrigazione saltata dall'AI: {reason}",
        "cycle_schedule": "Irrigazione programmata",
        "cycle_service": "Irrigazione (azione)",
        "cycle_manual": "Irrigazione manuale",
        "note_ai": "AI: {reason}",
        "note_timer": "Timer manuale: {minutes} min",
        "notify_started": "Irrigazione avviata{origin}. {details}.",
        "notify_finished": "Irrigazione terminata.",
        "notify_stopped": "Irrigazione interrotta.",
        "notify_valve_stuck": "Attenzione: la valvola {valve} non si è chiusa.",
        "notify_safety": "{zone} chiusa automaticamente dopo {minutes} minuti (sicurezza).",
        "notify_dry": "🌱 Terriccio secco: {zone} è al {moisture}% (soglia {threshold}%).",
        "live_running": "💧 Irrigazione in corso",
        "live_valve_open": "💧 Valvola aperta",
        "live_zone_done": "{zone} terminata",
        "live_zone_ends": "{zone} · fine {time}",
        "live_zone_waiting": "{zone} · dalle {time}",
        "live_manual": "{zone} · aperta a mano",
        "live_manual_close": " · chiusura {time}",
        "live_total": "Totale {liters} L",
        "live_stopped": "⏹️ Irrigazione interrotta",
        "live_done": "☑️ Irrigazione terminata",
        "live_all_done": "Tutte le zone completate",
        "live_finished": "Finita",
        "cal_planned": "Irrigazione prevista",
        "cal_running": "Irrigazione in corso",
        "cal_estimate": "{zone}: {minutes} min (stima)",
        "cal_ai_decides": "La durata la deciderà l'AI al momento dell'avvio.",
        "ev_manual": "Apertura manuale: {zone}",
        "ev_zone_line": "{zone}: {minutes} min, {liters} L",
        "ev_interrupted_line": "Interrotta prima della fine.",
        "ev_interrupted": " (interrotta)",
        "ev_total": "Totale: {liters} L",
    },
}


def language(hass: HomeAssistant) -> str:
    """Lingua di sistema ridotta al codice principale (it, en, ...)."""
    lang = (hass.config.language or "en").split("-")[0].lower()
    return lang if lang in MESSAGES else "en"


def liters_text(hass: HomeAssistant, value: float) -> str:
    """Litri con un decimale e il separatore della lingua."""
    text = f"{value:.1f}"
    return text.replace(".", ",") if language(hass) == "it" else text


def tr(hass: HomeAssistant, key: str, **kwargs: Any) -> str:
    """Testo tradotto nella lingua di sistema."""
    template = MESSAGES[language(hass)].get(key) or MESSAGES["en"][key]
    return template.format(**kwargs)
