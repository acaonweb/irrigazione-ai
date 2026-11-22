"""Formula personalizzata (template Jinja di Home Assistant)."""

from __future__ import annotations

import math
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.template import Template


class FormulaError(Exception):
    """La formula non è valida o non restituisce un numero."""


def render_formula(hass: HomeAssistant, formula: str, variables: dict[str, Any]) -> float:
    """Calcola la formula e restituisce i minuti (non ancora limitati)."""
    template = Template(formula, hass)
    try:
        result = template.async_render(variables, parse_result=False)
    except TemplateError as err:
        raise FormulaError(str(err)) from err
    except Exception as err:  # noqa: BLE001 - errori Jinja non incapsulati
        raise FormulaError(str(err)) from err
    text = str(result).strip().replace(",", ".")
    try:
        value = float(text)
    except ValueError as err:
        shown = text if len(text) <= 60 else text[:57] + "..."
        raise FormulaError(f"il risultato non è un numero: '{shown}'") from err
    if not math.isfinite(value):
        raise FormulaError("il risultato non è un numero finito")
    return value
