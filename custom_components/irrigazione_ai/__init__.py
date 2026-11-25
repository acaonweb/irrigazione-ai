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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.restore_state import async_get as async_get_restore_data
from homeassistant.helpers.typing import ConfigType

from .ai import AiError
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DURATION,
    ATTR_FORCE,
    CONF_TWICE_WEEKLY_DAYS,
    CONF_WEEKLY_DAY,
    CONF_ZONE_DAYS,
    CONF_ZONE_SCHEDULE,
    DEFAULT_FREQUENCY,
    DEFAULT_TWICE_WEEKLY_DAYS,
    DEFAULT_WEEKLY_DAY,
    DOMAIN,
    FREQ_DAILY,
    FREQ_OFF,
    FREQ_TWICE_WEEKLY,
    FREQ_WEEKLY,
    FREQUENCIES,
    SCHEDULE_DAILY,
    SCHEDULE_DAYS,
    SCHEDULE_OFF,
    SERVICE_ANALYZE,
    SERVICE_START,
    SERVICE_STOP,
    SOURCE_SERVICE,
)
from .controller import IrrigationController, structure_key

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
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
CARD_VERSION = "0.16.0"


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
    try:
        await _async_migrate_schedule(hass, entry)
    except Exception:  # noqa: BLE001 - la migrazione non deve mai bloccare l'avvio
        _LOGGER.exception("Migrazione della programmazione non riuscita")
    controller = IrrigationController(hass, entry)
    entry.runtime_data = controller
    # Lo storico va caricato prima delle entità, che leggono i litri salvati
    await controller.history.async_load()
    await controller.learning.async_load()
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
    if structure_key(entry) == controller.structure:
        # Cambiata solo la programmazione delle zone: nessuna ricarica
        controller.refresh_zones()
        return
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
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.learning").async_remove()


async def _async_last_state(hass: HomeAssistant, entity_id: str) -> str | None:
    """Ultimo stato noto di un'entità che non esiste più (prima di registrarla di nuovo).

    Prima la cache di ripristino (se l'API interna la espone), poi lo storico
    del recorder.
    """
    try:
        last_states = getattr(async_get_restore_data(hass), "last_states", None)
        stored = last_states.get(entity_id) if isinstance(last_states, dict) else None
        if stored is not None:
            return stored.state.state
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Cache di ripristino non leggibile", exc_info=True)
    if "recorder" not in hass.config.components:
        return None
    from homeassistant.components.recorder import get_instance  # noqa: PLC0415
    from homeassistant.components.recorder.history import (  # noqa: PLC0415
        get_last_state_changes,
    )

    changes = await get_instance(hass).async_add_executor_job(
        get_last_state_changes, hass, 20, entity_id
    )
    for state in reversed(changes.get(entity_id, [])):
        if state.state in FREQUENCIES:
            return state.state
    return None


async def _async_migrate_schedule(
    hass: HomeAssistant, entry: IrrigazioneConfigEntry
) -> None:
    """Da 0.9: la frequenza dell'impianto diventa la programmazione di ogni zona.

    Le zone ereditano i giorni in uso, così il comportamento non cambia.
    """
    zones = [
        sub for sub in entry.subentries.values() if CONF_ZONE_SCHEDULE not in sub.data
    ]
    reg = er.async_get(hass)
    old_id = reg.async_get_entity_id("select", DOMAIN, f"{entry.entry_id}_frequency")
    if not zones and old_id is None:
        return
    frequency = DEFAULT_FREQUENCY
    if old_id is not None:
        last = await _async_last_state(hass, old_id)
        if last in FREQUENCIES:
            frequency = last
    cfg = {**entry.data, **entry.options}
    weekly = cfg.get(CONF_WEEKLY_DAY, DEFAULT_WEEKLY_DAY)
    twice = list(cfg.get(CONF_TWICE_WEEKLY_DAYS, DEFAULT_TWICE_WEEKLY_DAYS))
    schedule, days = {
        FREQ_OFF: (SCHEDULE_OFF, twice),
        FREQ_DAILY: (SCHEDULE_DAILY, twice),
        FREQ_WEEKLY: (SCHEDULE_DAYS, [weekly]),
        FREQ_TWICE_WEEKLY: (SCHEDULE_DAYS, twice),
    }.get(frequency, (SCHEDULE_DAYS, twice))
    for sub in zones:
        hass.config_entries.async_update_subentry(
            entry,
            sub,
            data={**sub.data, CONF_ZONE_SCHEDULE: schedule, CONF_ZONE_DAYS: days},
        )
    if zones:
        _LOGGER.info(
            "Programmazione migrata alle zone: %s %s (frequenza %s)",
            schedule,
            days,
            frequency,
        )
    if old_id is not None:
        reg.async_remove(old_id)
