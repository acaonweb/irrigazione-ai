"""Testi tradotti nella lingua di sistema."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from custom_components.irrigazione_ai.messages import MESSAGES, liters_text, tr


def test_same_keys() -> None:
    """Ogni lingua ha tutte le chiavi dell'inglese."""
    for lang, texts in MESSAGES.items():
        assert set(texts) == set(MESSAGES["en"]), lang


async def test_italian_and_fallback(hass: HomeAssistant) -> None:
    """Italiano con la virgola; lingue senza traduzione in inglese."""
    hass.config.language = "it"
    assert tr(hass, "notify_finished") == "Irrigazione terminata."
    assert tr(hass, "ev_total", liters=liters_text(hass, 7.26)) == "Totale: 7,3 L"
    hass.config.language = "de"
    assert tr(hass, "notify_finished") == "Watering finished."
    hass.config.language = "en-GB"
    assert liters_text(hass, 7.26) == "7.3"
