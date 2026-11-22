"""Wizard di configurazione per Irrigazione AI."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CLOSE_ON_STARTUP,
    CONF_COEFFICIENT,
    CONF_EXPOSURE,
    CONF_FLOW_RATE,
    CONF_HUMIDITY,
    CONF_MAX_DURATION,
    CONF_MIN_DURATION,
    CONF_MOISTURE,
    CONF_NOTIFY,
    CONF_RUN_MODE,
    CONF_SAFETY_MINUTES,
    CONF_SOIL_VOLUME,
    CONF_SUNSET_OFFSET,
    CONF_TEMPERATURE,
    CONF_TWICE_WEEKLY_DAYS,
    CONF_VALVE,
    CONF_WEATHER,
    CONF_WEEKLY_DAY,
    CONF_ZONE_NAME,
    DEFAULT_CLOSE_ON_STARTUP,
    DEFAULT_COEFFICIENT,
    DEFAULT_EXPOSURE,
    DEFAULT_FLOW_RATE,
    DEFAULT_MAX_DURATION,
    DEFAULT_MIN_DURATION,
    DEFAULT_NAME,
    DEFAULT_RUN_MODE,
    DEFAULT_SAFETY_MINUTES,
    DEFAULT_SOIL_VOLUME,
    DEFAULT_SUNSET_OFFSET,
    DEFAULT_TWICE_WEEKLY_DAYS,
    DEFAULT_WEEKLY_DAY,
    DOMAIN,
    EXPOSURES,
    RUN_MODE_PARALLEL,
    RUN_MODE_SEQUENTIAL,
    SUBENTRY_ZONE,
    WEEKDAYS,
)

# ----------------------------------------------------------------------
# Schemi
# ----------------------------------------------------------------------


def _system_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Sensori dell'impianto."""
    return vol.Schema(
        {
            vol.Required(
                CONF_WEATHER, default=defaults.get(CONF_WEATHER, vol.UNDEFINED)
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="weather")),
            vol.Optional(
                CONF_TEMPERATURE,
                description={"suggested_value": defaults.get(CONF_TEMPERATURE)},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Optional(
                CONF_HUMIDITY,
                description={"suggested_value": defaults.get(CONF_HUMIDITY)},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="humidity")
            ),
        }
    )


def _schedule_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Programmazione e comportamento."""
    return vol.Schema(
        {
            vol.Required(
                CONF_SUNSET_OFFSET,
                default=defaults.get(CONF_SUNSET_OFFSET, DEFAULT_SUNSET_OFFSET),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-180, max=240, step=1, unit_of_measurement="min",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_WEEKLY_DAY, default=defaults.get(CONF_WEEKLY_DAY, DEFAULT_WEEKLY_DAY)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=WEEKDAYS, translation_key="weekday")
            ),
            vol.Required(
                CONF_TWICE_WEEKLY_DAYS,
                default=defaults.get(CONF_TWICE_WEEKLY_DAYS, DEFAULT_TWICE_WEEKLY_DAYS),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=WEEKDAYS, multiple=True, translation_key="weekday"
                )
            ),
            vol.Required(
                CONF_RUN_MODE, default=defaults.get(CONF_RUN_MODE, DEFAULT_RUN_MODE)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[RUN_MODE_PARALLEL, RUN_MODE_SEQUENTIAL],
                    translation_key="run_mode",
                )
            ),
            vol.Required(
                CONF_SAFETY_MINUTES,
                default=defaults.get(CONF_SAFETY_MINUTES, DEFAULT_SAFETY_MINUTES),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=240, step=1, unit_of_measurement="min",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_CLOSE_ON_STARTUP,
                default=defaults.get(CONF_CLOSE_ON_STARTUP, DEFAULT_CLOSE_ON_STARTUP),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_NOTIFY, default=defaults.get(CONF_NOTIFY, [])
            ): selector.TextSelector(selector.TextSelectorConfig(multiple=True)),
        }
    )


def _zone_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Dati di una zona."""
    return vol.Schema(
        {
            vol.Required(
                CONF_ZONE_NAME, default=defaults.get(CONF_ZONE_NAME, vol.UNDEFINED)
            ): selector.TextSelector(),
            vol.Required(
                CONF_VALVE, default=defaults.get(CONF_VALVE, vol.UNDEFINED)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["switch", "valve"])
            ),
            vol.Optional(
                CONF_MOISTURE,
                description={"suggested_value": defaults.get(CONF_MOISTURE)},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="moisture")
            ),
            vol.Required(
                CONF_FLOW_RATE, default=defaults.get(CONF_FLOW_RATE, DEFAULT_FLOW_RATE)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.001, max=1000, step=0.001, unit_of_measurement="L/min",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_MIN_DURATION,
                default=defaults.get(CONF_MIN_DURATION, DEFAULT_MIN_DURATION),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=240, step=1, unit_of_measurement="min",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_MAX_DURATION,
                default=defaults.get(CONF_MAX_DURATION, DEFAULT_MAX_DURATION),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=240, step=1, unit_of_measurement="min",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_COEFFICIENT,
                default=defaults.get(CONF_COEFFICIENT, DEFAULT_COEFFICIENT),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.1, max=3, step=0.05, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_SOIL_VOLUME,
                default=defaults.get(CONF_SOIL_VOLUME, DEFAULT_SOIL_VOLUME),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=100000, step=1, unit_of_measurement="L",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_EXPOSURE, default=defaults.get(CONF_EXPOSURE, DEFAULT_EXPOSURE)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=EXPOSURES, translation_key="exposure")
            ),
        }
    )


def _clean_zone(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalizza i numeri (il selettore restituisce float)."""
    data = dict(user_input)
    data[CONF_ZONE_NAME] = data[CONF_ZONE_NAME].strip()
    for key in (CONF_MIN_DURATION, CONF_MAX_DURATION):
        data[key] = int(data[key])
    data[CONF_SOIL_VOLUME] = float(data[CONF_SOIL_VOLUME])
    return data


def _validate_zone(
    user_input: dict[str, Any], used_valves: set[str]
) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not user_input[CONF_ZONE_NAME].strip():
        errors[CONF_ZONE_NAME] = "name_required"
    if user_input[CONF_VALVE] in used_valves:
        errors[CONF_VALVE] = "valve_in_use"
    if int(user_input[CONF_MIN_DURATION]) > int(user_input[CONF_MAX_DURATION]):
        errors[CONF_MAX_DURATION] = "min_greater_than_max"
    return errors


def _clean_schedule(user_input: dict[str, Any]) -> dict[str, Any]:
    data = dict(user_input)
    data[CONF_SUNSET_OFFSET] = int(data[CONF_SUNSET_OFFSET])
    data[CONF_SAFETY_MINUTES] = int(data[CONF_SAFETY_MINUTES])
    data[CONF_NOTIFY] = [s.strip() for s in data.get(CONF_NOTIFY, []) if s.strip()]
    return data


# ----------------------------------------------------------------------
# Flusso principale
# ----------------------------------------------------------------------


class IrrigazioneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Wizard: impianto -> zone -> programmazione."""

    VERSION = 1

    def __init__(self) -> None:
        """Inizializza il wizard."""
        self._name: str = DEFAULT_NAME
        self._system: dict[str, Any] = {}
        self._zones: list[dict[str, Any]] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Opzioni modificabili dopo la creazione."""
        return IrrigazioneOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Le zone sono subentry."""
        return {SUBENTRY_ZONE: ZoneSubentryFlow}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Passo 1: impianto."""
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input.pop(CONF_NAME).strip() or DEFAULT_NAME
            self._async_abort_entries_match({CONF_NAME: name})
            self._name = name
            self._system = user_input
            return await self.async_step_zone()

        schema = vol.Schema(
            {vol.Required(CONF_NAME, default=DEFAULT_NAME): selector.TextSelector()}
        ).extend(_system_schema({}).schema)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Passo 2: una zona."""
        errors: dict[str, str] = {}
        if user_input is not None:
            used = {z[CONF_VALVE] for z in self._zones}
            errors = _validate_zone(user_input, used)
            if not errors:
                self._zones.append(_clean_zone(user_input))
                return await self.async_step_zone_menu()
        return self.async_show_form(
            step_id="zone",
            data_schema=self.add_suggested_values_to_schema(
                _zone_schema({}), user_input or {}
            ),
            errors=errors,
            description_placeholders={"count": str(len(self._zones) + 1)},
        )

    async def async_step_zone_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Altra zona o programmazione?"""
        return self.async_show_menu(
            step_id="zone_menu",
            menu_options=["zone", "schedule"],
            description_placeholders={
                "zones": ", ".join(z[CONF_ZONE_NAME] for z in self._zones)
            },
        )

    async def async_step_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Passo 3: programmazione, poi crea l'impianto."""
        if user_input is not None:
            options = {**self._system, **_clean_schedule(user_input)}
            return self.async_create_entry(
                title=self._name,
                data={CONF_NAME: self._name},
                options=options,
                subentries=[
                    {
                        "subentry_type": SUBENTRY_ZONE,
                        "data": zone,
                        "title": zone[CONF_ZONE_NAME],
                        "unique_id": zone[CONF_VALVE],
                    }
                    for zone in self._zones
                ],
            )
        return self.async_show_form(step_id="schedule", data_schema=_schedule_schema({}))


# ----------------------------------------------------------------------
# Opzioni (impianto + programmazione)
# ----------------------------------------------------------------------


class IrrigazioneOptionsFlow(OptionsFlow):
    """Modifica sensori e programmazione."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Un unico modulo con tutte le impostazioni dell'impianto."""
        if user_input is not None:
            return self.async_create_entry(data=_clean_schedule(user_input))
        current = dict(self.config_entry.options)
        schema = _system_schema(current).extend(_schedule_schema(current).schema)
        return self.async_show_form(step_id="init", data_schema=schema)


# ----------------------------------------------------------------------
# Zone (subentry)
# ----------------------------------------------------------------------


class ZoneSubentryFlow(ConfigSubentryFlow):
    """Aggiunge o modifica una zona."""

    def _used_valves(self, exclude: str | None = None) -> set[str]:
        entry = self._get_entry()
        return {
            sub.data[CONF_VALVE]
            for sub_id, sub in entry.subentries.items()
            if sub.subentry_type == SUBENTRY_ZONE and sub_id != exclude
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Nuova zona."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_zone(user_input, self._used_valves())
            if not errors:
                data = _clean_zone(user_input)
                return self.async_create_entry(
                    title=data[CONF_ZONE_NAME], data=data, unique_id=data[CONF_VALVE]
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _zone_schema({}), user_input or {}
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Modifica una zona esistente."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_zone(user_input, self._used_valves(subentry.subentry_id))
            if not errors:
                data = _clean_zone(user_input)
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    title=data[CONF_ZONE_NAME],
                    data=data,
                    unique_id=data[CONF_VALVE],
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_zone_schema(user_input or dict(subentry.data)),
            errors=errors,
        )
