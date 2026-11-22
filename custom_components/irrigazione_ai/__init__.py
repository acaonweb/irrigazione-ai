"""Irrigazione AI: irrigazione multi-zona per Home Assistant."""

from __future__ import annotations

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
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

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
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await controller.async_setup()
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: IrrigazioneConfigEntry) -> None:
    """Ricarica quando cambiano opzioni o zone."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: IrrigazioneConfigEntry) -> bool:
    """Scarica un impianto."""
    await entry.runtime_data.async_shutdown()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
