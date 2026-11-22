"""Test dell'analisi AI."""

from __future__ import annotations

import json

import pytest
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.data_entry_flow import FlowResultType

from custom_components.irrigazione_ai.ai import AiError, parse_json_text, parse_result
from custom_components.irrigazione_ai.const import DOMAIN
from custom_components.irrigazione_ai.controller import ZoneConfig

from .conftest import VALVE_1, VALVE_2, WEATHER, install_fake_valves, make_entry

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
AI_OPTIONS = {
    "ai_provider": "openai",
    "ai_api_key": "sk-test",
    "ai_model": "gpt-4.1-mini",
    "ai_on_error": "skip",
}


def _openai_reply(payload: dict) -> dict:
    return {"choices": [{"message": {"content": json.dumps(payload)}}]}


async def _setup(hass: HomeAssistant, calls, **ai):
    entry = make_entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={**entry.options, **AI_OPTIONS, **ai})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.irrigazione_ai_analysis"}, blocking=True
    )
    install_fake_valves(hass, calls)
    return entry


def _zone(zone_id: str, flow: float = 0.726, mn: int = 15, mx: int = 120) -> ZoneConfig:
    return ZoneConfig(
        zone_id=zone_id, name=zone_id, valve=f"switch.{zone_id}", moisture_sensor=None,
        flow_rate=flow, min_duration=mn, max_duration=mx, coefficient=1.0,
        soil_volume=100, exposure="north",
    )


def test_parse_json_text() -> None:
    """JSON anche dentro un blocco di codice."""
    assert parse_json_text('```json\n{"irrigate": true}\n```') == {"irrigate": True}
    with pytest.raises(AiError):
        parse_json_text("non lo so")


def test_parse_result_liters_to_minutes() -> None:
    """Litri / portata, arrotondati per eccesso e limitati."""
    zones = [_zone("a"), _zone("b"), _zone("c", mn=1)]
    result = parse_result(
        {
            "irrigate": True,
            "reason": "caldo",
            "zone_1_liters": 21.78,  # 30 min
            "zone_2_liters": 0,  # niente
            "zone_3_liters": "0,5",  # 1 min (minimo 1)
        },
        zones,
        "openai",
    )
    assert result.irrigate
    assert result.zones["a"].minutes == 30
    assert result.zones["b"].minutes == 0
    assert result.zones["c"].minutes == 1

    none = parse_result({"irrigate": "true", "zone_1_liters": 0}, [_zone("a")], "x")
    assert not none.irrigate  # nessuna zona da irrigare
    with pytest.raises(AiError):
        parse_result({"reason": "?"}, zones, "x")


async def test_ai_decides_durations(hass: HomeAssistant, valves, aioclient_mock) -> None:
    """L'AI decide i litri: si apre solo la zona con litri > 0."""
    aioclient_mock.post(
        OPENAI_URL,
        json=_openai_reply(
            {"irrigate": True, "reason": "Caldo e secco", "zone_1_liters": 21.78,
             "zone_1_reason": "terriccio secco", "zone_2_liters": 0, "zone_2_reason": "umido"}
        ),
    )
    entry = await _setup(hass, valves)
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)

    opened = {c.data["entity_id"] for c in valves if c.service == "turn_on"}
    assert opened == {VALVE_1}
    controller = entry.runtime_data
    assert controller.ai_last_used
    assert hass.states.get("sensor.irrigazione_ai_decision").state == "irrigate"
    assert hass.states.get("sensor.secondo_piano_ai_duration").state == "30"
    # Il prompt contiene i dati delle zone
    sent = aioclient_mock.mock_calls[-1][2]
    prompt = sent["messages"][0]["content"]
    assert "Secondo piano" in prompt and '"zone_2_liters"' in prompt
    assert sent["model"] == "gpt-4.1-mini"
    assert aioclient_mock.mock_calls[-1][3]["Authorization"] == "Bearer sk-test"


async def test_ai_skip(hass: HomeAssistant, valves, aioclient_mock) -> None:
    """L'AI dice di non irrigare: ciclo bloccato."""
    aioclient_mock.post(
        OPENAI_URL, json=_openai_reply({"irrigate": False, "reason": "Ha piovuto"})
    )
    entry = await _setup(hass, valves)
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    await hass.async_block_till_done()
    assert not [c for c in valves if c.service == "turn_on"]
    assert entry.runtime_data.last_block == "ai"
    assert hass.states.get("sensor.irrigazione_ai_decision").state == "skip"
    assert (
        hass.states.get("sensor.irrigazione_ai_decision").attributes["reason"] == "Ha piovuto"
    )


async def test_ai_error_skip(hass: HomeAssistant, valves, aioclient_mock) -> None:
    """Errore AI con 'salta il ciclo'."""
    aioclient_mock.post(OPENAI_URL, status=500, text="boom")
    entry = await _setup(hass, valves, ai_on_error="skip")
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    await hass.async_block_till_done()
    assert not [c for c in valves if c.service == "turn_on"]
    assert entry.runtime_data.last_block == "ai_error"
    assert hass.states.get("sensor.irrigazione_ai_decision").state == "error"
    assert hass.states.get("switch.irrigazione_ai_analysis").state == "on"


async def test_ai_error_formula(hass: HomeAssistant, valves, aioclient_mock) -> None:
    """Errore AI con 'irriga con la formula' (predefinito): l'AI resta accesa."""
    aioclient_mock.post(OPENAI_URL, status=500, text="boom")
    entry = await _setup(hass, valves, ai_on_error="formula")
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert {c.data["entity_id"] for c in valves if c.service == "turn_on"} == {VALVE_1, VALVE_2}
    assert not entry.runtime_data.ai_last_used
    assert hass.states.get("switch.irrigazione_ai_analysis").state == "on"


async def test_ai_error_formula_disable(hass: HomeAssistant, valves, aioclient_mock) -> None:
    """Errore AI con 'formula e spegni l'AI'."""
    aioclient_mock.post(OPENAI_URL, status=500, text="boom")
    await _setup(hass, valves, ai_on_error="formula_disable")
    await hass.services.async_call(DOMAIN, "start", {}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert {c.data["entity_id"] for c in valves if c.service == "turn_on"} == {VALVE_1, VALVE_2}
    assert hass.states.get("switch.irrigazione_ai_analysis").state == "off"


async def test_manual_duration_bypasses_ai(hass: HomeAssistant, valves, aioclient_mock) -> None:
    """Con una durata esplicita l'AI non viene interpellata."""
    entry = await _setup(hass, valves)
    await hass.services.async_call(DOMAIN, "start", {"duration": 5}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert aioclient_mock.call_count == 0
    assert not entry.runtime_data.ai_last_used


async def test_ai_task_and_analyze_service(hass: HomeAssistant, valves) -> None:
    """Provider AI Task e servizio analyze con risposta."""
    hass.states.async_set("ai_task.openai", "unknown")
    received: list[ServiceCall] = []

    async def _generate(call: ServiceCall):
        received.append(call)
        return {"data": {"irrigate": True, "reason": "ok", "zone_1_liters": 7.26,
                         "zone_1_reason": "a", "zone_2_liters": 14.52, "zone_2_reason": "b"}}

    hass.services.async_register(
        "ai_task", "generate_data", _generate, supports_response=SupportsResponse.ONLY
    )
    await _setup(hass, valves, ai_provider="ai_task", ai_task_entity="ai_task.openai")
    response = await hass.services.async_call(
        DOMAIN, "analyze", {}, blocking=True, return_response=True
    )
    zones = response["Irrigazione"]["zones"]
    assert zones["Secondo piano"]["minutes"] == 15  # 10 min -> minimo 15
    assert zones["Sottotetto"]["minutes"] == 20
    structure = received[0].data["structure"]
    assert set(structure) >= {"irrigate", "reason", "zone_1_liters", "zone_2_liters"}
    # analyze non irriga
    assert not [c for c in valves if c.service == "turn_on"]


async def test_ai_wizard_step(hass: HomeAssistant, valves, aioclient_mock) -> None:
    """Passo AI nelle opzioni: chiave rifiutata, poi valida."""
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"weather_entity": WEATHER, "sunset_offset": 5, "weekly_day": "sun",
                            "twice_weekly_days": ["thu", "sun"], "run_mode": "parallel",
                            "safety_minutes": 60, "close_on_startup": True, "notify_services": []},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"formula": "{{ 20 }}"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "ai"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"ai_provider": "openai"}
    )
    assert result["step_id"] == "ai_details"

    aioclient_mock.post(OPENAI_URL, status=401, text="bad key")
    details = {"ai_api_key": "sk-wrong", "ai_model": "gpt-4.1-mini", "ai_on_error": "formula"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], details)
    assert result["errors"] == {"base": "invalid_auth"}

    aioclient_mock.clear_requests()
    aioclient_mock.post(OPENAI_URL, json=_openai_reply({"ok": True}))
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], details | {"ai_api_key": "sk-good"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["ai_provider"] == "openai"
    assert entry.options["ai_api_key"] == "sk-good"
    assert hass.states.get("switch.irrigazione_ai_analysis").state == "off"


async def test_custom_prompt(hass: HomeAssistant, valves, aioclient_mock) -> None:
    """Prompt personalizzato: usato, con il formato della risposta aggiunto in fondo."""
    aioclient_mock.post(
        OPENAI_URL, json=_openai_reply({"irrigate": False, "reason": "ok"})
    )
    await _setup(
        hass, valves,
        ai_prompt="Sei un giardiniere. Zone: {{ zones | length }}. Dati: {{ data_json }}",
    )
    await hass.services.async_call(DOMAIN, "analyze", {}, blocking=True, return_response=True)
    prompt = aioclient_mock.mock_calls[-1][2]["messages"][0]["content"]
    assert prompt.startswith("Sei un giardiniere. Zone: 2. Dati: {")
    assert '"zone_2_liters"' in prompt
    assert "Write every reason in English" in prompt


async def test_prompt_without_data_gets_data(hass: HomeAssistant, valves, aioclient_mock) -> None:
    """Un prompt che non usa i dati li riceve comunque in fondo."""
    aioclient_mock.post(OPENAI_URL, json=_openai_reply({"irrigate": False, "reason": "ok"}))
    await _setup(hass, valves, ai_prompt="Decidi tu.")
    await hass.services.async_call(DOMAIN, "analyze", {}, blocking=True, return_response=True)
    prompt = aioclient_mock.mock_calls[-1][2]["messages"][0]["content"]
    assert prompt.startswith("Decidi tu.\n\nData (JSON):\n{")


async def test_prompt_editor_in_options(hass: HomeAssistant, valves, aioclient_mock) -> None:
    """Prompt non valido rifiutato; prompt uguale al predefinito non salvato."""
    from custom_components.irrigazione_ai.ai import DEFAULT_AI_PROMPT

    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    aioclient_mock.post(OPENAI_URL, json=_openai_reply({"ok": True}))

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"weather_entity": WEATHER, "sunset_offset": 5, "weekly_day": "sun",
                            "twice_weekly_days": ["thu", "sun"], "run_mode": "parallel",
                            "safety_minutes": 60, "close_on_startup": True, "notify_services": []},
    )
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"formula": "{{ 20 }}"})
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "ai"})
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"ai_provider": "openai"})
    base = {"ai_api_key": "sk", "ai_model": "gpt-4.1-mini", "ai_on_error": "formula"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], base | {"ai_prompt": "{{ data.zones[0].inesistente * 2 }}"}
    )
    assert result["errors"] == {"ai_prompt": "prompt_invalid"}
    assert aioclient_mock.call_count == 0  # nessuna chiamata con un prompt rotto

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], base | {"ai_prompt": DEFAULT_AI_PROMPT}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert "ai_prompt" not in entry.options
