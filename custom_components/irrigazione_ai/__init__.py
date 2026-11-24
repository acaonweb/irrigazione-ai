"""Irrigazione AI: irrigazione multi-zona per Home Assistant."""

from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .ai import AiError
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DURATION,
    ATTR_FORCE,
    DOMAIN,
    SERVICE_ANALYZE,
    SERVICE_START,
    SERVICE_STOP,
    SOURCE_SERVICE,
)
from .controller import IrrigationController

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)
CARD_URL = f"/{DOMAIN}/irrigazione-ai-card.js"
CARD_PATH = Path(__file__).parent / "frontend" / "irrigazione-ai-card.js"
CARD_VERSION = "0.9.4"


async def _async_register_card(hass: HomeAssistant) -> None:
    """Rende disponibile la card Lovelace senza aggiungere risorse a mano."""
    if getattr(hass, "http", None) is None:
        return
    try:
        from homeassistant.components.frontend import add_extra_js_url  # noqa: PLC0415
        from homeassistant.components.http import StaticPathConfig  # noqa: PLC0415

        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, str(CARD_PATH), False)]
        )
        add_extra_js_url(hass, f"{CARD_URL}?v={CARD_VERSION}")
    except Exception:  # noqa: BLE001 - la card è un extra, l'integrazione funziona comunque
        _LOGGER.warning("Impossibile registrare la card Lovelace", exc_info=True)

type IrrigazioneConfigEntry = ConfigEntry[IrrigationController]

START_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_DURATION): vol.All(vol.Coerce(int), vol.Range(min=1, max=240)),
        vol.Optional(ATTR_FORCE, default=False): cv.boolean,
    }
)
STOP_SCHEMA = vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string})


def _controllers(hass: HomeAssistant, call: ServiceCall) -> list[IrrigationController]:
    """Controller interessati dalla chiamata (tutti se non specificato)."""
    entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if entry_id:
        entries = [e for e in entries if e.entry_id == entry_id]
        if not entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_found",
            )
    return [e.runtime_data for e in entries if e.state is ConfigEntryState.LOADED]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Registra i servizi."""

    async def _start(call: ServiceCall) -> None:
        for controller in _controllers(hass, call):
            await controller.async_start(
                SOURCE_SERVICE,
                duration=call.data.get(ATTR_DURATION),
                force=call.data[ATTR_FORCE],
            )

    async def _stop(call: ServiceCall) -> None:
        for controller in _controllers(hass, call):
            await controller.async_stop()

    async def _analyze(call: ServiceCall) -> ServiceResponse:
        results = {}
        for controller in _controllers(hass, call):
            if not controller.ai_configured:
                continue
            try:
                result = await controller.async_analyze()
            except AiError as err:
                raise HomeAssistantError(f"Analisi AI non riuscita: {err}") from err
            results[controller.entry.title] = {
                "irrigate": result.irrigate,
                "reason": result.reason,
                "zones": {
                    z.name: {"liters": z.liters, "minutes": z.minutes, "reason": z.reason}
                    for z in result.zones.values()
                },
            }
        return results

    await _async_register_card(hass)
    hass.services.async_register(DOMAIN, SERVICE_START, _start, schema=START_SCHEMA)
    hass.services.async_register(
        DOMAIN,
        SERVICE_ANALYZE,
        _analyze,
        schema=STOP_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(DOMAIN, SERVICE_STOP, _stop, schema=STOP_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: IrrigazioneConfigEntry) -> bool:
    """Configura un impianto."""
    controller = IrrigationController(hass, entry)
    entry.runtime_data = controller
    # Lo storico va caricato prima delle entità, che leggono i litri salvati
    await controller.history.async_load()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await controller.async_setup()
    # Ora che tutte le entità esistono, aggiorna (es. la mappa per la card)
    controller.async_update_listeners()
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: IrrigazioneConfigEntry) -> None:
    """Ricarica quando cambiano opzioni o zone.

    Se sta irrigando, la ricarica aspetta la fine del ciclo: ricaricare
    adesso fermerebbe l'irrigazione a metà.
    """
    controller = entry.runtime_data
    if controller.running:
        controller.reload_pending = True
        _LOGGER.info(
            "Configurazione cambiata durante un ciclo: verrà applicata a fine irrigazione"
        )
        controller.async_update_listeners()
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: IrrigazioneConfigEntry) -> bool:
    """Scarica un impianto."""
    await entry.runtime_data.async_shutdown()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: IrrigazioneConfigEntry) -> None:
    """Rimozione dell'impianto: cancella storico e consumi salvati."""
    from homeassistant.helpers.storage import Store  # noqa: PLC0415

    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}").async_remove()
