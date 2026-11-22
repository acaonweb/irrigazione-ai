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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .ai import AiAuthError, AiConnectionError, AiError, async_validate
from .calc import clamp_minutes, formula_variables
from .const import (
    AI_API_PROVIDERS,
    AI_NONE,
    AI_OLLAMA,
    AI_ON_ERROR_OPTIONS,
    AI_PROVIDERS,
    AI_TASK,
    CONF_AI_API_KEY,
    CONF_AI_BASE_URL,
    CONF_AI_INSTRUCTIONS,
    CONF_AI_MODEL,
    CONF_AI_ON_ERROR,
    CONF_AI_PROVIDER,
    CONF_AI_TASK_ENTITY,
    CONF_CLOSE_ON_STARTUP,
    CONF_COEFFICIENT,
    CONF_EXPOSURE,
    CONF_FLOW_RATE,
    CONF_FORMULA,
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
    DEFAULT_AI_MODELS,
    DEFAULT_AI_ON_ERROR,
    DEFAULT_CLOSE_ON_STARTUP,
    DEFAULT_COEFFICIENT,
    DEFAULT_EXPOSURE,
    DEFAULT_FLOW_RATE,
    DEFAULT_FORMULA,
    DEFAULT_MAX_DURATION,
    DEFAULT_MIN_DURATION,
    DEFAULT_NAME,
    DEFAULT_OLLAMA_URL,
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
from .controller import ZoneConfig, _float_state
from .formula import FormulaError, render_formula

# ----------------------------------------------------------------------
# Schemi
# ----------------------------------------------------------------------


def _system_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Sensori dell'impianto."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_WEATHER, description={"suggested_value": defaults.get(CONF_WEATHER)}
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
            vol.Optional(
                CONF_FORMULA,
                description={"suggested_value": defaults.get(CONF_FORMULA)},
            ): selector.TemplateSelector(),
        }
    )


def _formula_schema(current: str | None) -> vol.Schema:
    """Editor della formula dell'impianto."""
    return vol.Schema(
        {
            vol.Required(
                CONF_FORMULA, default=current or DEFAULT_FORMULA
            ): selector.TemplateSelector(),
        }
    )


def _inputs(hass: HomeAssistant, system: dict[str, Any]) -> tuple[float | None, float | None, str | None]:
    """Temperatura, umidità e meteo attuali (come li legge il motore)."""
    weather_id = system.get(CONF_WEATHER)
    weather = hass.states.get(weather_id) if weather_id else None
    temperature = _float_state(hass, system.get(CONF_TEMPERATURE))
    humidity = _float_state(hass, system.get(CONF_HUMIDITY))
    if weather is not None:
        if temperature is None:
            try:
                temperature = float(weather.attributes.get("temperature"))
            except (TypeError, ValueError):
                temperature = None
        if humidity is None:
            try:
                humidity = float(weather.attributes.get("humidity"))
            except (TypeError, ValueError):
                humidity = None
    return temperature, humidity, weather.state if weather else None


def _zone_variables(hass: HomeAssistant, system: dict[str, Any], zone: ZoneConfig) -> dict[str, Any]:
    temperature, humidity, weather = _inputs(hass, system)
    return formula_variables(
        moisture=_float_state(hass, zone.moisture_sensor),
        temperature=temperature,
        humidity=humidity,
        weather=weather,
        coefficient=zone.coefficient,
        flow_rate=zone.flow_rate,
        soil_volume=zone.soil_volume,
        exposure=zone.exposure,
        min_duration=zone.min_duration,
        max_duration=zone.max_duration,
    )


def _check_formula(
    hass: HomeAssistant,
    formula: str,
    system: dict[str, Any],
    zones: list[dict[str, Any]],
    *,
    only_without_own: bool = False,
) -> list[tuple[str, int, float]]:
    """Calcola la formula per ogni zona. Solleva FormulaError se fallisce.

    Ritorna (nome zona, minuti limitati, valore grezzo).
    """
    results: list[tuple[str, int, float]] = []
    for data in zones:
        zone = ZoneConfig.from_subentry("preview", data)
        if only_without_own and zone.formula:
            continue
        value = render_formula(hass, formula, _zone_variables(hass, system, zone))
        results.append(
            (zone.name, clamp_minutes(value, zone.min_duration, zone.max_duration), value)
        )
    return results


def _preview_text(results: list[tuple[str, int, float]]) -> str:
    """Anteprima in markdown."""
    if not results:
        return "-"
    lines = []
    for name, minutes, raw in results:
        extra = "" if round(raw) == minutes else f" (formula: {raw:.1f})"
        lines.append(f"- **{name}**: {minutes} min{extra}")
    return "\n".join(lines)


def _clean_zone(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalizza i numeri (il selettore restituisce float)."""
    data = dict(user_input)
    data[CONF_ZONE_NAME] = data[CONF_ZONE_NAME].strip()
    for key in (CONF_MIN_DURATION, CONF_MAX_DURATION):
        data[key] = int(data[key])
    data[CONF_SOIL_VOLUME] = float(data[CONF_SOIL_VOLUME])
    formula = (data.get(CONF_FORMULA) or "").strip()
    if formula:
        data[CONF_FORMULA] = formula
    else:
        data.pop(CONF_FORMULA, None)
    return data


def _validate_zone(
    user_input: dict[str, Any],
    used_valves: set[str],
    hass: HomeAssistant | None = None,
    system: dict[str, Any] | None = None,
    placeholders: dict[str, str] | None = None,
) -> dict[str, str]:
    errors: dict[str, str] = {}
    formula = (user_input.get(CONF_FORMULA) or "").strip()
    if formula and hass is not None:
        try:
            _check_formula(hass, formula, system or {}, [_clean_zone(user_input)])
        except FormulaError as err:
            errors[CONF_FORMULA] = "formula_invalid"
            if placeholders is not None:
                placeholders["error"] = str(err)
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


AI_KEYS = (
    CONF_AI_PROVIDER,
    CONF_AI_TASK_ENTITY,
    CONF_AI_API_KEY,
    CONF_AI_MODEL,
    CONF_AI_BASE_URL,
    CONF_AI_ON_ERROR,
    CONF_AI_INSTRUCTIONS,
)


def _ai_provider_schema(current: str | None) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_AI_PROVIDER, default=current or AI_NONE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=AI_PROVIDERS,
                    translation_key="ai_provider",
                    mode=selector.SelectSelectorMode.LIST,
                )
            )
        }
    )


def _ai_details_schema(provider: str, defaults: dict[str, Any]) -> vol.Schema:
    fields: dict[Any, Any] = {}
    if provider == AI_TASK:
        fields[
            vol.Required(
                CONF_AI_TASK_ENTITY, default=defaults.get(CONF_AI_TASK_ENTITY, vol.UNDEFINED)
            )
        ] = selector.EntitySelector(selector.EntitySelectorConfig(domain="ai_task"))
    else:
        if provider in AI_API_PROVIDERS:
            fields[
                vol.Required(
                    CONF_AI_API_KEY, default=defaults.get(CONF_AI_API_KEY, vol.UNDEFINED)
                )
            ] = selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            )
        if provider == AI_OLLAMA:
            fields[
                vol.Required(
                    CONF_AI_BASE_URL, default=defaults.get(CONF_AI_BASE_URL, DEFAULT_OLLAMA_URL)
                )
            ] = selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
            )
        model_default = defaults.get(CONF_AI_MODEL)
        if not model_default or defaults.get(CONF_AI_PROVIDER) != provider:
            model_default = DEFAULT_AI_MODELS.get(provider, "")
        fields[vol.Required(CONF_AI_MODEL, default=model_default)] = selector.TextSelector()
    fields[
        vol.Required(
            CONF_AI_ON_ERROR, default=defaults.get(CONF_AI_ON_ERROR, DEFAULT_AI_ON_ERROR)
        )
    ] = selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=AI_ON_ERROR_OPTIONS, translation_key="ai_on_error"
        )
    )
    fields[
        vol.Optional(
            CONF_AI_INSTRUCTIONS,
            description={"suggested_value": defaults.get(CONF_AI_INSTRUCTIONS)},
        )
    ] = selector.TextSelector(selector.TextSelectorConfig(multiline=True))
    return vol.Schema(fields)


class _AiStepsMixin:
    """Passi AI condivisi da wizard e opzioni.

    Chi la usa definisce `_ai` (dict di lavoro), `_ai_defaults()` e
    `async_step_finish()`.
    """

    _ai: dict[str, Any]

    def _ai_defaults(self) -> dict[str, Any]:
        return {}

    async def async_step_ai(self, user_input: dict[str, Any] | None = None):
        """Scelta del provider AI."""
        if user_input is not None:
            provider = user_input[CONF_AI_PROVIDER]
            self._ai = {CONF_AI_PROVIDER: provider}
            if provider == AI_NONE:
                return await self.async_step_finish()
            return await self.async_step_ai_details()
        current = self._ai.get(CONF_AI_PROVIDER) or self._ai_defaults().get(CONF_AI_PROVIDER)
        return self.async_show_form(step_id="ai", data_schema=_ai_provider_schema(current))

    async def async_step_ai_details(self, user_input: dict[str, Any] | None = None):
        """Dati del provider, verificati con una richiesta di prova."""
        provider = self._ai[CONF_AI_PROVIDER]
        errors: dict[str, str] = {}
        placeholders = {"error": "", "provider": provider}
        if user_input is not None:
            candidate = {CONF_AI_PROVIDER: provider, **user_input}
            try:
                await async_validate(self.hass, candidate)
            except AiAuthError:
                errors["base"] = "invalid_auth"
            except AiConnectionError as err:
                errors["base"] = "cannot_connect"
                placeholders["error"] = str(err)
            except AiError as err:
                errors["base"] = "ai_failed"
                placeholders["error"] = str(err)
            else:
                self._ai = candidate
                return await self.async_step_finish()
        defaults = {**self._ai_defaults(), **(user_input or {})}
        return self.async_show_form(
            step_id="ai_details",
            data_schema=_ai_details_schema(provider, defaults),
            errors=errors,
            description_placeholders=placeholders,
        )


# ----------------------------------------------------------------------
# Flusso principale
# ----------------------------------------------------------------------


class IrrigazioneConfigFlow(_AiStepsMixin, ConfigFlow, domain=DOMAIN):
    """Wizard: impianto -> zone -> programmazione -> formula."""

    VERSION = 1

    def __init__(self) -> None:
        """Inizializza il wizard."""
        self._name: str = DEFAULT_NAME
        self._system: dict[str, Any] = {}
        self._zones: list[dict[str, Any]] = []
        self._schedule: dict[str, Any] = {}
        self._formula: str = DEFAULT_FORMULA
        self._preview: str = ""
        self._ai: dict[str, Any] = {}

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
        if user_input is not None:
            name = user_input.pop(CONF_NAME).strip() or DEFAULT_NAME
            self._async_abort_entries_match({CONF_NAME: name})
            self._name = name
            self._system = user_input
            return await self.async_step_zone()

        schema = vol.Schema(
            {vol.Required(CONF_NAME, default=DEFAULT_NAME): selector.TextSelector()}
        ).extend(_system_schema({}).schema)
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Passo 2: una zona."""
        errors: dict[str, str] = {}
        placeholders = {"count": str(len(self._zones) + 1), "error": ""}
        if user_input is not None:
            used = {z[CONF_VALVE] for z in self._zones}
            errors = _validate_zone(user_input, used, self.hass, self._system, placeholders)
            if not errors:
                self._zones.append(_clean_zone(user_input))
                return await self.async_step_zone_menu()
        return self.async_show_form(
            step_id="zone",
            data_schema=self.add_suggested_values_to_schema(
                _zone_schema({}), user_input or {}
            ),
            errors=errors,
            description_placeholders=placeholders,
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
        """Passo 3: programmazione."""
        if user_input is not None:
            self._schedule = _clean_schedule(user_input)
            return await self.async_step_formula()
        return self.async_show_form(step_id="schedule", data_schema=_schedule_schema({}))

    async def async_step_formula(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Passo 4: formula della durata."""
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        if user_input is not None:
            formula = user_input[CONF_FORMULA].strip() or DEFAULT_FORMULA
            try:
                results = _check_formula(
                    self.hass, formula, self._system, self._zones, only_without_own=True
                )
            except FormulaError as err:
                errors[CONF_FORMULA] = "formula_invalid"
                placeholders["error"] = str(err)
            else:
                self._formula = formula
                self._preview = _preview_text(results)
                return await self.async_step_formula_preview()
        return self.async_show_form(
            step_id="formula",
            data_schema=_formula_schema(
                user_input[CONF_FORMULA] if user_input else self._formula
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_formula_preview(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Anteprima: conferma o torna all'editor."""
        return self.async_show_menu(
            step_id="formula_preview",
            menu_options=["ai", "formula"],
            description_placeholders={"preview": self._preview},
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Crea l'impianto con le zone."""
        options = {
            **self._system,
            **self._schedule,
            CONF_FORMULA: self._formula,
            **self._ai,
        }
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


# ----------------------------------------------------------------------
# Opzioni (impianto + programmazione + formula)
# ----------------------------------------------------------------------


class IrrigazioneOptionsFlow(_AiStepsMixin, OptionsFlow):
    """Modifica sensori, programmazione e formula."""

    def __init__(self) -> None:
        """Inizializza."""
        self._options: dict[str, Any] = {}
        self._preview: str = ""
        self._ai: dict[str, Any] = {}

    def _ai_defaults(self) -> dict[str, Any]:
        return {k: v for k, v in self.config_entry.options.items() if k in AI_KEYS}

    def _zones(self) -> list[dict[str, Any]]:
        return [
            dict(sub.data)
            for sub in self.config_entry.subentries.values()
            if sub.subentry_type == SUBENTRY_ZONE
        ]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Sensori e programmazione."""
        if user_input is not None:
            self._options = _clean_schedule(user_input)
            return await self.async_step_formula()
        current = dict(self.config_entry.options)
        schema = _system_schema(current).extend(_schedule_schema(current).schema)
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_formula(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Editor della formula."""
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        if user_input is not None:
            formula = user_input[CONF_FORMULA].strip() or DEFAULT_FORMULA
            try:
                results = _check_formula(
                    self.hass, formula, self._options, self._zones(), only_without_own=True
                )
            except FormulaError as err:
                errors[CONF_FORMULA] = "formula_invalid"
                placeholders["error"] = str(err)
            else:
                self._options[CONF_FORMULA] = formula
                self._preview = _preview_text(results)
                return await self.async_step_formula_preview()
        current = (
            user_input[CONF_FORMULA]
            if user_input
            else self._options.get(CONF_FORMULA)
            or self.config_entry.options.get(CONF_FORMULA)
        )
        return self.async_show_form(
            step_id="formula",
            data_schema=_formula_schema(current),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_formula_preview(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Anteprima: salva o torna all'editor."""
        return self.async_show_menu(
            step_id="formula_preview",
            menu_options=["ai", "formula"],
            description_placeholders={"preview": self._preview},
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Salva."""
        options = {k: v for k, v in self._options.items() if k not in AI_KEYS}
        return self.async_create_entry(data={**options, **self._ai})


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
        placeholders = {"error": ""}
        if user_input is not None:
            errors = _validate_zone(
                user_input,
                self._used_valves(),
                self.hass,
                dict(self._get_entry().options),
                placeholders,
            )
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
            description_placeholders=placeholders,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Modifica una zona esistente."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        if user_input is not None:
            errors = _validate_zone(
                user_input,
                self._used_valves(subentry.subentry_id),
                self.hass,
                dict(self._get_entry().options),
                placeholders,
            )
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
            description_placeholders=placeholders,
        )
