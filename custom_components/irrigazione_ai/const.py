"""Costanti per Irrigazione AI."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "irrigazione_ai"

# Tipo di subentry per le zone
SUBENTRY_ZONE: Final = "zone"

# --- Configurazione impianto (data/options) ---
CONF_WEATHER: Final = "weather_entity"
CONF_TEMPERATURE: Final = "temperature_sensor"
CONF_HUMIDITY: Final = "humidity_sensor"
CONF_START_MODE: Final = "start_mode"
CONF_START_TIME: Final = "start_time"
# Il nome della chiave resta "sunset_offset" per compatibilità: ora vale per alba e tramonto
CONF_SUNSET_OFFSET: Final = "sunset_offset"

START_MODE_SUNRISE: Final = "sunrise"
START_MODE_SUNSET: Final = "sunset"
START_MODE_TIME: Final = "time"
START_MODES: Final = [START_MODE_SUNSET, START_MODE_SUNRISE, START_MODE_TIME]
CONF_RUN_MODE: Final = "run_mode"
CONF_SAFETY_MINUTES: Final = "safety_minutes"
CONF_CLOSE_ON_STARTUP: Final = "close_on_startup"
CONF_WEEKLY_DAY: Final = "weekly_day"
CONF_TWICE_WEEKLY_DAYS: Final = "twice_weekly_days"
CONF_NOTIFY: Final = "notify_services"
CONF_FORMULA: Final = "formula"

RUN_MODE_PARALLEL: Final = "parallel"
RUN_MODE_SEQUENTIAL: Final = "sequential"

# --- Configurazione zona (subentry data) ---
CONF_ZONE_NAME: Final = "name"
CONF_VALVE: Final = "valve"
CONF_MOISTURE: Final = "moisture_sensor"
CONF_FLOW_RATE: Final = "flow_rate"
CONF_MIN_DURATION: Final = "min_duration"
CONF_MAX_DURATION: Final = "max_duration"
CONF_COEFFICIENT: Final = "coefficient"
CONF_SOIL_VOLUME: Final = "soil_volume"
CONF_EXPOSURE: Final = "exposure"

EXPOSURES: Final = ["north", "south", "east", "west"]

# Pagine dove ottenere le credenziali di ogni servizio AI
AI_KEY_URLS: Final = {
    "openai": "https://platform.openai.com/api-keys",
    "anthropic": "https://platform.claude.com/settings/keys",
    "gemini": "https://aistudio.google.com/apikey",
    "ollama": "https://ollama.com/download",
    "ai_task": "https://www.home-assistant.io/integrations/ai_task/",
}

# --- Default ---
DEFAULT_NAME: Final = "Irrigazione"
DEFAULT_SUNSET_OFFSET: Final = 5
DEFAULT_START_MODE: Final = START_MODE_SUNSET
DEFAULT_START_TIME: Final = "21:00:00"
DEFAULT_RUN_MODE: Final = RUN_MODE_PARALLEL
DEFAULT_SAFETY_MINUTES: Final = 60
DEFAULT_CLOSE_ON_STARTUP: Final = True
DEFAULT_WEEKLY_DAY: Final = "sun"
DEFAULT_TWICE_WEEKLY_DAYS: Final = ["thu", "sun"]
DEFAULT_FLOW_RATE: Final = 0.726
DEFAULT_MIN_DURATION: Final = 15
DEFAULT_MAX_DURATION: Final = 120
DEFAULT_COEFFICIENT: Final = 1.0
DEFAULT_SOIL_VOLUME: Final = 100
DEFAULT_EXPOSURE: Final = "north"

# Formula predefinita (Jinja). Variabili: moisture, temperature, humidity,
# weather, weather_factor, coefficient, flow_rate, soil_volume, exposure,
# min_duration, max_duration. Il risultato viene sempre limitato tra
# min_duration e max_duration.
DEFAULT_FORMULA: Final = (
    "{{ (20 + 20 * (100 - moisture) / moisture + 20 * temperature / 25)"
    " * 0.9 * weather_factor * coefficient }}"
)

WEEKDAYS: Final = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# --- Frequenza (select) ---
FREQ_OFF: Final = "off"
FREQ_WEEKLY: Final = "weekly"
FREQ_TWICE_WEEKLY: Final = "twice_weekly"
FREQ_DAILY: Final = "daily"
FREQUENCIES: Final = [FREQ_OFF, FREQ_WEEKLY, FREQ_TWICE_WEEKLY, FREQ_DAILY]
DEFAULT_FREQUENCY: Final = FREQ_TWICE_WEEKLY

# Programmazione per zona
CONF_ZONE_SCHEDULE: Final = "schedule"
CONF_PLANTS: Final = "plants"
CONF_ZONE_DAYS: Final = "days"
CONF_ZONE_ANCHOR: Final = "alternate_anchor"
SCHEDULE_OFF: Final = "off"
SCHEDULE_ALTERNATE: Final = "alternate"
SCHEDULE_DAYS: Final = "days"
SCHEDULE_DAILY: Final = "daily"
SCHEDULES: Final = [SCHEDULE_OFF, SCHEDULE_ALTERNATE, SCHEDULE_DAYS, SCHEDULE_DAILY]
DEFAULT_SCHEDULE: Final = SCHEDULE_DAYS
DEFAULT_ZONE_DAYS: Final = ["thu", "sun"]
SERVICE_SET_SCHEDULE: Final = "set_schedule"
ATTR_MODE: Final = "mode"
ATTR_DAYS: Final = "days"
SCHEDULE_KEYS: Final = (CONF_ZONE_SCHEDULE, CONF_ZONE_DAYS, CONF_ZONE_ANCHOR)

# --- Timer manuale (select) ---
MANUAL_TIMER_OPTIONS: Final = ["off", "15", "30", "60"]

# --- Origine di un ciclo ---
SOURCE_SCHEDULE: Final = "schedule"
SOURCE_MANUAL: Final = "manual"
SOURCE_SERVICE: Final = "service"

# --- Stato impianto ---
STATUS_IDLE: Final = "idle"
STATUS_RUNNING: Final = "running"
STATUS_BLOCKED: Final = "blocked"
STATUSES: Final = [STATUS_IDLE, STATUS_RUNNING, STATUS_BLOCKED]

# Stati meteo considerati "pioggia" per il blocco
RAIN_STATES: Final = frozenset(
    {"rainy", "pouring", "lightning-rainy", "snowy-rainy", "lightning", "hail"}
)

# Servizi
SERVICE_START: Final = "start"
SERVICE_STOP: Final = "stop"
ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
ATTR_DURATION: Final = "duration"
ATTR_FORCE: Final = "force"

# Tentativi di chiusura valvola
CLOSE_RETRIES: Final = 3
CLOSE_RETRY_DELAY: Final = 2.0
# Attesa dopo l'avvio di HA prima di chiudere valvole rimaste aperte
STARTUP_CLOSE_DELAY: Final = 30.0

# --- Analisi AI ---
CONF_AI_PROVIDER: Final = "ai_provider"
CONF_AI_TASK_ENTITY: Final = "ai_task_entity"
CONF_AI_API_KEY: Final = "ai_api_key"
CONF_AI_MODEL: Final = "ai_model"
CONF_AI_BASE_URL: Final = "ai_base_url"
CONF_AI_ON_ERROR: Final = "ai_on_error"
CONF_AI_INSTRUCTIONS: Final = "ai_instructions"
CONF_AI_PROMPT: Final = "ai_prompt"

AI_NONE: Final = "none"
AI_TASK: Final = "ai_task"
AI_OPENAI: Final = "openai"
AI_ANTHROPIC: Final = "anthropic"
AI_GEMINI: Final = "gemini"
AI_OLLAMA: Final = "ollama"
AI_PROVIDERS: Final = [AI_NONE, AI_TASK, AI_OPENAI, AI_ANTHROPIC, AI_GEMINI, AI_OLLAMA]
AI_API_PROVIDERS: Final = [AI_OPENAI, AI_ANTHROPIC, AI_GEMINI]

DEFAULT_AI_MODELS: Final = {
    AI_OPENAI: "gpt-4.1-mini",
    AI_ANTHROPIC: "claude-haiku-5-5",
    AI_GEMINI: "gemini-2.5-flash",
    AI_OLLAMA: "llama3.1",
}
DEFAULT_OLLAMA_URL: Final = "http://localhost:11434"

AI_ON_ERROR_SKIP: Final = "skip"
AI_ON_ERROR_FORMULA: Final = "formula"
AI_ON_ERROR_DISABLE: Final = "formula_disable"
AI_ON_ERROR_OPTIONS: Final = [AI_ON_ERROR_FORMULA, AI_ON_ERROR_DISABLE, AI_ON_ERROR_SKIP]
DEFAULT_AI_ON_ERROR: Final = AI_ON_ERROR_FORMULA

AI_TIMEOUT: Final = 90
AI_RAIN_HOURS: Final = 12
AI_FORECAST_HOURS: Final = 12

# Esito dell'analisi
AI_RESULT_IRRIGATE: Final = "irrigate"
AI_RESULT_SKIP: Final = "skip"
AI_RESULT_ERROR: Final = "error"
AI_RESULTS: Final = [AI_RESULT_IRRIGATE, AI_RESULT_SKIP, AI_RESULT_ERROR]

SERVICE_ANALYZE: Final = "analyze"
SOURCE_AI: Final = "ai"

# --- Notifiche / Live Activity ---
CONF_LIVE_DEVICES: Final = "live_devices"
CONF_LIVE_URL: Final = "live_url"
LIVE_CLEAR_DELAY: Final = 300
ZONE_NUMBERS: Final = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
