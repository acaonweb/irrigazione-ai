import json

zone_fields = {
 "en": {
  "name": ("Zone name", "e.g. Second floor, Attic, Vegetable garden"),
  "valve": ("Valve", "Switch or valve entity that opens the water for this zone"),
  "moisture_sensor": ("Soil moisture sensor", "Optional: without it the formula assumes 50%"),
  "flow_rate": ("Flow rate", "Liters per minute delivered by the drippers of this zone"),
  "min_duration": ("Minimum duration", "The calculated time never goes below this"),
  "max_duration": ("Maximum duration", "The calculated time never goes above this"),
  "coefficient": ("Coefficient", "1 = formula as is; 1.2 = 20% more water; 0.8 = 20% less"),
  "soil_volume": ("Soil volume", "Liters of substrate in this zone (used by the AI analysis)"),
  "exposure": ("Exposure", "Main orientation of the zone (used by the AI analysis)"),
  "plants": ("Plants", "What grows in this zone, in your words: e.g. rosemary and lavender, tomatoes, potted lemon tree. The AI uses it to size the water"),
  "schedule": ("When to water", "Every other day counts from the day you choose it. You can change it later from the card"),
  "days": ("Days (only with 'Chosen days')", "Ignored with the other choices"),
  "learning": ("Self-learning", "After each watering the zone checks how far its soil moisture rises and adjusts the next dose by itself. Needs a soil moisture sensor. You can also switch it on and off from the card"),
  "formula": ("Zone formula", "Optional: replaces the system formula for this zone only. Leave empty to use the system formula"),
 },
 "it": {
  "name": ("Nome della zona", "Per esempio Secondo piano, Sottotetto, Orto"),
  "valve": ("Valvola", "Entità switch o valve che apre l'acqua per questa zona"),
  "moisture_sensor": ("Sensore umidità del terriccio", "Facoltativo: senza, la formula considera il 50%"),
  "flow_rate": ("Portata", "Litri al minuto erogati dai gocciolatori di questa zona"),
  "min_duration": ("Durata minima", "Il tempo calcolato non scende mai sotto questo valore"),
  "max_duration": ("Durata massima", "Il tempo calcolato non supera mai questo valore"),
  "coefficient": ("Coefficiente", "1 = formula così com'è; 1,2 = 20% di acqua in più; 0,8 = 20% in meno"),
  "soil_volume": ("Volume del terriccio", "Litri di substrato in questa zona (usato dall'analisi AI)"),
  "exposure": ("Esposizione", "Orientamento principale della zona (usato dall'analisi AI)"),
  "plants": ("Piante", "Cosa cresce in questa zona, con parole tue: per esempio rosmarino e lavanda, pomodori, limone in vaso. L'AI lo usa per dosare l'acqua"),
  "schedule": ("Quando irrigare", "Un giorno sì e uno no parte dal giorno in cui lo scegli. Si cambia poi anche dalla card"),
  "days": ("Giorni (solo con 'Giorni scelti')", "Ignorati con le altre scelte"),
  "learning": ("Autoapprendimento", "Dopo ogni irrigazione la zona guarda fin dove sale l'umidità del terriccio e corregge da sola la dose successiva. Serve un sensore di umidità. Si accende e si spegne anche dalla card"),
  "formula": ("Formula della zona", "Facoltativa: sostituisce la formula dell'impianto solo per questa zona. Lascia vuoto per usare quella dell'impianto"),
 },
}
system_fields = {
 "en": {
  "weather_entity": ("Weather entity", "Optional: used by the formula, the rain block and the AI analysis. Without it (and without a rain sensor) the rain block stays inactive"),
  "temperature_sensor": ("Outdoor temperature sensor", "Optional: otherwise the weather entity temperature is used"),
  "humidity_sensor": ("Outdoor humidity sensor", "Optional: otherwise the weather entity humidity is used"),
  "rain_sensor": ("Rain sensor", "Optional: your own device that knows whether it is raining (binary sensor on = rain, or a rain rate/amount sensor > 0). When set it decides instead of the weather; if it stops answering the weather is used"),
  "wind_sensor": ("Wind sensor", "Optional: wind speed from your own weather station. Without it the weather entity wind is used, if it has one"),
 },
 "it": {
  "weather_entity": ("Entità meteo", "Facoltativa: usata dalla formula, dal blocco pioggia e dall'analisi AI. Senza meteo e senza sensore pioggia, il blocco pioggia resta inattivo"),
  "temperature_sensor": ("Sensore temperatura esterna", "Facoltativo: altrimenti si usa la temperatura dell'entità meteo"),
  "humidity_sensor": ("Sensore umidità esterna", "Facoltativo: altrimenti si usa l'umidità dell'entità meteo"),
  "rain_sensor": ("Sensore pioggia", "Facoltativo: un tuo dispositivo che sa se sta piovendo (sensore binario acceso = pioggia, oppure un sensore di intensità o quantità di pioggia > 0). Se c'è decide lui al posto del meteo; se smette di rispondere si usa il meteo"),
  "wind_sensor": ("Sensore vento", "Facoltativo: velocità del vento da una tua stazione meteo. Senza, si usa il vento dell'entità meteo, se lo fornisce"),
 },
}
schedule_fields = {
 "en": {
  "start_mode": ("Start time based on", "Sunset, sunrise or a fixed time of your choice"),
  "start_time": ("Fixed time", "Used only with 'Fixed time'"),
  "sunset_offset": ("Offset in minutes", "Only for sunrise and sunset: minutes after the event; negative = before (e.g. -30 = half an hour before sunrise)"),
  "run_mode": ("Zones", "In parallel all zones open together; in sequence one after the other (useful with low water pressure)"),
  "safety_minutes": ("Safety close", "A valve opened by hand closes automatically after these minutes (0 = never)"),
  "close_on_startup": ("Close valves on startup", "If Home Assistant restarts with a valve open and no cycle running, it closes it"),
  "live_devices": ("Live Activity devices", "Phones and tablets with the Home Assistant app: during watering they show a Live Activity (iPhone, Dynamic Island) or a Live Update (Android 16+) with each zone and its end time"),
  "live_url": ("Page to open on tap", "Optional: dashboard opened by tapping the Live Activity, e.g. /lovelace/irrigation"),
  "notify_services": ("Other notifications", "Notify actions for simple messages (start, end, skipped cycles, dry soil, errors), e.g. notify.pushover"),
  "time_format": ("Time format", "For the cards and the Live Activity. Automatic = the format of each user's profile (Live Activity: 12 h in the United States, 24 h elsewhere)"),
  "date_format": ("Date format", "For the cards. Automatic = the format of each user's profile"),
  "dry_threshold": ("Dry soil alarm", "If a zone's soil moisture stays below this for 5 minutes you get a notification (0 = off)"),
  "rain_forecast_hours": ("Rain expected within", "With the rain block on, the cycle is skipped if the hourly forecast shows rain within these hours (0 = only rain falling now). Skipped if the weather service has no hourly forecast"),
  "frost_temperature": ("Frost: don't water below", "Current temperature or the next 3 hours of forecast. Leave empty to turn the check off"),
  "wind_max": ("Strong wind: don't water above", "Wind from the wind sensor or the weather entity (0 = off). Skipped if no wind data is available"),
  "learn_target": ("Self-learning target", "Soil moisture a zone with self-learning should reach after watering"),
 },
 "it": {
  "start_mode": ("Orario di partenza riferito a", "Tramonto, alba oppure un orario fisso scelto da te"),
  "start_time": ("Orario fisso", "Usato solo con 'Orario fisso'"),
  "sunset_offset": ("Scostamento in minuti", "Solo per alba e tramonto: minuti dopo l'evento; negativo = prima (per esempio -30 = mezz'ora prima dell'alba)"),
  "run_mode": ("Zone", "In parallelo si aprono tutte insieme; in sequenza una dopo l'altra (utile se la pressione dell'acqua è bassa)"),
  "safety_minutes": ("Chiusura di sicurezza", "Una valvola aperta a mano si chiude da sola dopo questi minuti (0 = mai)"),
  "close_on_startup": ("Chiudi le valvole all'avvio", "Se Home Assistant si riavvia con una valvola aperta e nessun ciclo in corso, la chiude"),
  "live_devices": ("Dispositivi per la Live Activity", "Telefoni e tablet con l'app Home Assistant: durante l'irrigazione mostrano una Live Activity (iPhone, Dynamic Island) o un Live Update (Android 16+) con ogni zona e la sua ora di fine"),
  "live_url": ("Pagina da aprire al tocco", "Facoltativa: dashboard aperta toccando la Live Activity, per esempio /lovelace/irrigazione"),
  "notify_services": ("Altre notifiche", "Azioni di notifica per messaggi semplici (avvio, fine, cicli saltati, terriccio secco, errori), per esempio notify.pushover"),
  "time_format": ("Formato orario", "Per le card e la Live Activity. Automatico = il formato del profilo di ogni utente (Live Activity: 12 ore negli Stati Uniti, 24 altrove)"),
  "date_format": ("Formato data", "Per le card. Automatico = il formato del profilo di ogni utente"),
  "dry_threshold": ("Allarme terriccio secco", "Se l'umidità del terriccio di una zona resta sotto questo valore per 5 minuti arriva una notifica (0 = spento)"),
  "rain_forecast_hours": ("Pioggia prevista entro", "Con il blocco pioggia attivo, il ciclo si salta se le previsioni orarie danno pioggia entro queste ore (0 = solo pioggia in corso). Si salta il controllo se il meteo non ha previsioni orarie"),
  "frost_temperature": ("Gelo: non irrigare sotto", "Temperatura attuale o delle prossime 3 ore di previsione. Lascia vuoto per spegnere il controllo"),
  "wind_max": ("Vento forte: non irrigare sopra", "Vento dal sensore vento o dall'entità meteo (0 = spento). Si salta il controllo se manca il dato del vento"),
  "learn_target": ("Obiettivo dell'autoapprendimento", "Umidità del terriccio che una zona con autoapprendimento dovrebbe raggiungere dopo l'irrigazione"),
 },
}

def fields(d):
    data = {k: v[0] for k, v in d.items()}
    desc = {k: v[1] for k, v in d.items() if v[1]}
    return data, desc

def merge(*ds):
    out = {}
    for d in ds: out.update(d)
    return out

T = {
 "en": {
  "user_title": "New irrigation system",
  "user_desc": "Give the system a name and choose the weather and outdoor sensors. You will add the zones in the next step.",
  "name": "Name",
  "zone_title": "Zone {count}",
  "zone_desc": "Configure one zone: one valve with its drippers.",
  "menu_title": "Zones",
  "menu_desc": "Zones configured so far: {zones}.",
  "menu_zone": "Add another zone",
  "menu_schedule": "Continue to scheduling",
  "sched_title": "Scheduling",
  "sched_desc": "When and how to water. You can change everything later from the integration options.",
  "opt_title": "Irrigation system settings",
  "already": "A system with this name already exists.",
  "err_name": "Enter a name.",
  "err_valve": "This valve is already used by another zone.",
  "err_minmax": "The minimum duration is greater than the maximum.",
  "sub_entry_type": "Zone",
  "sub_add": "Add zone",
  "sub_user_title": "New zone",
  "sub_reconf_title": "Edit zone",
  "sub_reconf_ok": "Zone updated.",
  "weekday": {"mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday", "fri": "Friday", "sat": "Saturday", "sun": "Sunday"},
  "run_mode": {"parallel": "In parallel", "sequential": "In sequence"},
  "start_mode": {"sunset": "Sunset", "sunrise": "Sunrise", "time": "Fixed time"},
  "exposure": {"north": "North", "south": "South", "east": "East", "west": "West"},
  "entities": {
   "binary_sensor": {"zone_dry": "Dry soil"},
   "switch": {"irrigation": "Irrigation", "rain_block": "Rain block", "ai_analysis": "AI analysis", "zone_learning": "Self-learning"},
   "select": {"zone_schedule": ("Schedule", {"off": "Off", "alternate": "Every other day", "days": "Chosen days", "daily": "Every day"}),
              "manual_timer": ("Manual timer", {"off": "Off (formula)", "15": "15 min", "30": "30 min", "60": "60 min"})},
   "button": {"start": "Start now", "stop": "Stop", "analyze": "Analyze now"},
   "sensor": {"status": ("Status", {"idle": "Idle", "running": "Running", "blocked": "Blocked"}),
              "remaining": "Time remaining", "next_run": "Next run", "last_block": "Last block",
              "last_run": "Last run", "zone_duration": "Planned duration", "zone_end": "Expected end",
              "ai_decision": ("AI decision", {"irrigate": "Water", "skip": "Skip", "error": "Error"}),
              "zone_ai_duration": "AI duration",
              "water_today": "Water today", "water_month": "Water this month", "water_total": "Water total",
              "zone_water_today": "Water today", "zone_water_total": "Water total",
              "zone_learned_factor": "Learned factor"},
   "calendar": {"calendar": "Irrigation log"},
  },
  "svc": {
   "start": ("Start irrigation", "Starts a cycle on all zones.",
             {"config_entry_id": ("System", "Leave empty for all systems."),
              "duration": ("Duration", "Same minutes for every zone; empty = formula or manual timer."),
              "force": ("Ignore weather blocks", "Start even if it is raining or rain, frost or strong wind is expected.")}),
   "stop": ("Stop irrigation", "Stops the running cycle and closes the valves.",
            {"config_entry_id": ("System", "Leave empty for all systems.")}),
   "analyze": ("Analyze with AI", "Asks the AI whether and how much to water, without watering. Returns the result.",
            {"config_entry_id": ("System", "Leave empty for all systems.")}),
   "set_schedule": ("Set zone schedule", "Changes when a zone is watered. Target: the zone's Schedule entity.",
            {"mode": ("Mode", "off, alternate (every other day, starting today), days, daily."),
             "days": ("Days", "Weekdays (mon…sun). Alone, they also set the mode to 'Chosen days'; an empty list turns the zone off.")}),
   "reset_learning": ("Reset self-learning", "Brings a zone's learned factor back to 1. Target: the zone's Self-learning switch.", {}),
  },
  "exc_entry": "Irrigation system not found or not loaded.",
  "exc_schedule": "Give a mode or the days.",
  "schedule": {"off": "Off", "alternate": "Every other day", "days": "Chosen days", "daily": "Every day"},
  "time_format": {"auto": "Automatic", "24": "24 hours (15:30)", "12": "12 hours (3:30 PM)"},
  "date_format": {"auto": "Automatic", "dmy": "Day/month (24/11)", "mdy": "Month/day (11/24)", "ymd": "Year-month-day (2026-11-24)"},
  "formula_title": "Duration formula",
  "formula_desc": "Write a Jinja template that returns the minutes of watering. Available variables: `moisture` soil moisture % (min 10, 50 if no sensor), `temperature` outdoor °C (20 if missing), `humidity` outdoor %, `weather` weather state (sunny, rainy...), `raining` (true/false, from the rain sensor or the weather), `weather_factor` (sunny 1.1, partlycloudy 0.8, cloudy 0.5, rain 0.2), `coefficient`, `flow_rate` L/min, `soil_volume` L, `exposure` (north, south, east, west), `min_duration`, `max_duration`, `plants` (text). You can also read any entity with `states('sensor.xxx')`. The result is always kept between the zone minimum and maximum.",
  "formula_field": "Formula",
  "formula_field_desc": "The default is the classic formula: change it as you like",
  "preview_title": "Formula preview",
  "preview_desc": "With the current values the formula gives:\n\n{preview}\n\nZones with their own formula are not shown.",
  "preview_finish": "Looks good, continue",
  "preview_edit": "Edit the formula",
  "err_formula": "The formula does not work: {error}",
  "ai_title": "AI analysis",
  "ai_desc": "Optional: an AI model can decide whether to water and how many liters each zone needs, using current weather, rain of the last 12 hours and the forecast. You can use an AI Task entity already set up in Home Assistant or your own API key. You can turn the analysis on and off later with the 'AI analysis' switch.\n\nWhere to get the API key: [OpenAI]({openai_url}) · [Anthropic Claude]({anthropic_url}) · [Google Gemini]({gemini_url}) · [Ollama]({ollama_url}) (free, local) · [AI Task]({ai_task_url})",
  "ai_provider": "AI service",
  "providers": {"none": "No AI (formula only)", "ai_task": "AI Task entity of Home Assistant", "openai": "OpenAI (API key)", "anthropic": "Anthropic Claude (API key)", "gemini": "Google Gemini (API key)", "ollama": "Ollama (local)"},
  "on_error": {"formula": "Water with the formula", "formula_disable": "Water with the formula and turn off the AI analysis", "skip": "Skip the cycle"},
  "aid_title": "AI service settings",
  "aid_desc": "🔑 Where to get the API key (or how to set up the service): [{key_label}]({key_url})\n\nA small test request is sent to check the settings before saving.",
  "aid_fields": {"ai_task_entity": "AI Task entity", "ai_api_key": "API key", "ai_base_url": "Ollama address", "ai_model": "Model", "ai_on_error": "If the analysis fails", "ai_instructions": "Notes for the AI", "ai_prompt": "AI prompt"},
  "aid_fields_desc": {"ai_task_entity": "Created by an AI integration (OpenAI, Anthropic, Google, Ollama...) in Home Assistant", "ai_api_key": "Stored in the Home Assistant configuration", "ai_base_url": "e.g. http://192.168.1.10:11434", "ai_model": "Model name as the service calls it", "ai_on_error": "What to do if the AI does not answer or answers badly. You always get a notification", "ai_instructions": "Optional: plants, pots, local climate... e.g. 'tomatoes in 40 L pots, windy terrace'", "ai_prompt": "Jinja template with the instructions for the AI. Variables: data_json (all the data), zones, weather_now, rain_last_hours, forecast_next_hours, notes, language. The answer format is always added at the end. Empty it to go back to the default prompt"},
  "err_auth": "The API key was rejected ({error}). Check that it was copied whole, that it is still active and that the project can use the chosen model.",
  "err_conn": "Cannot reach the service: {error}",
  "err_ai": "The test request failed: {error}",
  "err_prompt": "The prompt does not work: {error}",

 },
 "it": {
  "user_title": "Nuovo impianto di irrigazione",
  "user_desc": "Dai un nome all'impianto e scegli il meteo e i sensori esterni. Le zone le aggiungi al passo successivo.",
  "name": "Nome",
  "zone_title": "Zona {count}",
  "zone_desc": "Configura una zona: una valvola con i suoi gocciolatori.",
  "menu_title": "Zone",
  "menu_desc": "Zone configurate finora: {zones}.",
  "menu_zone": "Aggiungi un'altra zona",
  "menu_schedule": "Passa alla programmazione",
  "sched_title": "Programmazione",
  "sched_desc": "Quando e come irrigare. Puoi cambiare tutto anche dopo, dalle opzioni dell'integrazione.",
  "opt_title": "Impostazioni dell'impianto",
  "already": "Esiste già un impianto con questo nome.",
  "err_name": "Inserisci un nome.",
  "err_valve": "Questa valvola è già usata da un'altra zona.",
  "err_minmax": "La durata minima è maggiore della massima.",
  "sub_entry_type": "Zona",
  "sub_add": "Aggiungi zona",
  "sub_user_title": "Nuova zona",
  "sub_reconf_title": "Modifica zona",
  "sub_reconf_ok": "Zona aggiornata.",
  "weekday": {"mon": "Lunedì", "tue": "Martedì", "wed": "Mercoledì", "thu": "Giovedì", "fri": "Venerdì", "sat": "Sabato", "sun": "Domenica"},
  "run_mode": {"parallel": "In parallelo", "sequential": "In sequenza"},
  "start_mode": {"sunset": "Tramonto", "sunrise": "Alba", "time": "Orario fisso"},
  "exposure": {"north": "Nord", "south": "Sud", "east": "Est", "west": "Ovest"},
  "entities": {
   "binary_sensor": {"zone_dry": "Terriccio secco"},
   "switch": {"irrigation": "Irrigazione", "rain_block": "Blocco pioggia", "ai_analysis": "Analisi AI", "zone_learning": "Autoapprendimento"},
   "select": {"zone_schedule": ("Programmazione", {"off": "Spenta", "alternate": "Un giorno sì e uno no", "days": "Giorni scelti", "daily": "Tutti i giorni"}),
              "manual_timer": ("Timer manuale", {"off": "Off (formula)", "15": "15 min", "30": "30 min", "60": "60 min"})},
   "button": {"start": "Avvia ora", "stop": "Ferma", "analyze": "Analizza ora"},
   "sensor": {"status": ("Stato", {"idle": "Ferma", "running": "In corso", "blocked": "Bloccata"}),
              "remaining": "Tempo rimanente", "next_run": "Prossima irrigazione", "last_block": "Ultimo blocco",
              "last_run": "Ultima irrigazione", "zone_duration": "Durata prevista", "zone_end": "Fine prevista",
              "ai_decision": ("Decisione AI", {"irrigate": "Irrigare", "skip": "Saltare", "error": "Errore"}),
              "zone_ai_duration": "Durata AI",
              "water_today": "Acqua oggi", "water_month": "Acqua questo mese", "water_total": "Acqua totale",
              "zone_water_today": "Acqua oggi", "zone_water_total": "Acqua totale",
              "zone_learned_factor": "Fattore appreso"},
   "calendar": {"calendar": "Registro irrigazioni"},
  },
  "svc": {
   "start": ("Avvia irrigazione", "Avvia un ciclo su tutte le zone.",
             {"config_entry_id": ("Impianto", "Lascia vuoto per tutti gli impianti."),
              "duration": ("Durata", "Stessi minuti per ogni zona; vuoto = formula o timer manuale."),
              "force": ("Ignora i blocchi meteo", "Avvia anche se piove o sono previsti pioggia, gelo o vento forte.")}),
   "stop": ("Ferma irrigazione", "Interrompe il ciclo in corso e chiude le valvole.",
            {"config_entry_id": ("Impianto", "Lascia vuoto per tutti gli impianti.")}),
   "analyze": ("Analizza con AI", "Chiede all'AI se e quanto irrigare, senza irrigare. Restituisce l'esito.",
            {"config_entry_id": ("Impianto", "Lascia vuoto per tutti gli impianti.")}),
   "set_schedule": ("Programma la zona", "Cambia quando viene irrigata una zona. Destinazione: l'entità Programmazione della zona.",
            {"mode": ("Modalità", "off, alternate (un giorno sì e uno no, da oggi), days, daily."),
             "days": ("Giorni", "Giorni della settimana (mon…sun). Da soli impostano anche 'Giorni scelti'; una lista vuota spegne la zona.")}),
   "reset_learning": ("Azzera l'autoapprendimento", "Riporta a 1 il fattore appreso di una zona. Destinazione: l'interruttore Autoapprendimento della zona.", {}),
  },
  "exc_entry": "Impianto non trovato o non caricato.",
  "exc_schedule": "Indica la modalità o i giorni.",
  "schedule": {"off": "Spenta", "alternate": "Un giorno sì e uno no", "days": "Giorni scelti", "daily": "Tutti i giorni"},
  "time_format": {"auto": "Automatico", "24": "24 ore (15:30)", "12": "12 ore (3:30 PM)"},
  "date_format": {"auto": "Automatico", "dmy": "Giorno/mese (24/11)", "mdy": "Mese/giorno (11/24)", "ymd": "Anno-mese-giorno (2026-11-24)"},
  "formula_title": "Formula della durata",
  "formula_desc": "Scrivi un template Jinja che restituisce i minuti di irrigazione. Variabili disponibili: `moisture` umidità del terriccio % (minimo 10, 50 senza sensore), `temperature` °C esterni (20 se manca), `humidity` umidità esterna %, `weather` stato meteo (sunny, rainy...), `raining` (true/false, dal sensore pioggia o dal meteo), `weather_factor` (sereno 1,1, poco nuvoloso 0,8, nuvoloso 0,5, pioggia 0,2), `coefficient`, `flow_rate` L/min, `soil_volume` L, `exposure` (north, south, east, west), `min_duration`, `max_duration`, `plants` (testo). Puoi leggere anche qualsiasi entità con `states('sensor.xxx')`. Il risultato resta sempre tra minimo e massimo della zona.",
  "formula_field": "Formula",
  "formula_field_desc": "Quella predefinita è la formula classica: modificala come preferisci",
  "preview_title": "Anteprima della formula",
  "preview_desc": "Con i valori attuali la formula dà:\n\n{preview}\n\nLe zone con una formula propria non sono mostrate.",
  "preview_finish": "Va bene, continua",
  "preview_edit": "Modifica la formula",
  "err_formula": "La formula non funziona: {error}",
  "ai_title": "Analisi AI",
  "ai_desc": "Facoltativa: un modello AI decide se irrigare e quanti litri dare a ogni zona, in base a meteo attuale, pioggia delle ultime 12 ore e previsioni. Puoi usare un'entità AI Task già configurata in Home Assistant oppure una tua API key. L'analisi si accende e spegne poi con l'interruttore 'Analisi AI'.\n\nDove ottenere la API key: [OpenAI]({openai_url}) · [Anthropic Claude]({anthropic_url}) · [Google Gemini]({gemini_url}) · [Ollama]({ollama_url}) (gratis, in locale) · [AI Task]({ai_task_url})",
  "ai_provider": "Servizio AI",
  "providers": {"none": "Nessuna AI (solo formula)", "ai_task": "Entità AI Task di Home Assistant", "openai": "OpenAI (API key)", "anthropic": "Anthropic Claude (API key)", "gemini": "Google Gemini (API key)", "ollama": "Ollama (in locale)"},
  "on_error": {"formula": "Irriga con la formula", "formula_disable": "Irriga con la formula e spegni l'analisi AI", "skip": "Salta il ciclo"},
  "aid_title": "Impostazioni del servizio AI",
  "aid_desc": "🔑 Dove ottenere la API key (o come preparare il servizio): [{key_label}]({key_url})\n\nPrima di salvare viene inviata una piccola richiesta di prova per verificare i dati.",
  "aid_fields": {"ai_task_entity": "Entità AI Task", "ai_api_key": "API key", "ai_base_url": "Indirizzo di Ollama", "ai_model": "Modello", "ai_on_error": "Se l'analisi non riesce", "ai_instructions": "Note per l'AI", "ai_prompt": "Prompt dell'AI"},
  "aid_fields_desc": {"ai_task_entity": "Creata da un'integrazione AI (OpenAI, Anthropic, Google, Ollama...) in Home Assistant", "ai_api_key": "Salvata nella configurazione di Home Assistant", "ai_base_url": "Per esempio http://192.168.1.10:11434", "ai_model": "Nome del modello come lo chiama il servizio", "ai_on_error": "Cosa fare se l'AI non risponde o risponde male. In ogni caso arriva una notifica", "ai_instructions": "Facoltative: piante, vasi, clima della zona... per esempio 'pomodori in vasi da 40 L, terrazzo ventoso'", "ai_prompt": "Template Jinja con le istruzioni per l'AI. Variabili: data_json (tutti i dati), zones, weather_now, rain_last_hours, forecast_next_hours, notes, language. Il formato della risposta viene sempre aggiunto in fondo. Svuotalo per tornare al prompt predefinito"},
  "err_auth": "La API key è stata rifiutata ({error}). Controlla che sia copiata per intero, che sia ancora attiva e che il progetto possa usare il modello scelto.",
  "err_conn": "Servizio non raggiungibile: {error}",
  "err_ai": "La richiesta di prova non è riuscita: {error}",
  "err_prompt": "Il prompt non funziona: {error}",

 },
}

def build(lang):
    t = T[lang]
    zd, zdesc = fields(zone_fields[lang])
    sd, sdesc = fields(system_fields[lang])
    pd, pdesc = fields(schedule_fields[lang])
    ent = {}
    for plat, items in t["entities"].items():
        ent[plat] = {}
        for k, v in items.items():
            if isinstance(v, tuple):
                ent[plat][k] = {"name": v[0], "state": v[1]}
            else:
                ent[plat][k] = {"name": v}
    svcs = {}
    for k, (n, d, f) in t["svc"].items():
        svcs[k] = {"name": n, "description": d,
                   "fields": {fk: {"name": fv[0], "description": fv[1]} for fk, fv in f.items()}}
    zone_step = {"data": zd, "data_description": zdesc}
    formula_steps = {
        "formula": {"title": t["formula_title"], "description": t["formula_desc"],
                    "data": {"formula": t["formula_field"]},
                    "data_description": {"formula": t["formula_field_desc"]}},
        "formula_preview": {"title": t["preview_title"], "description": t["preview_desc"],
                            "menu_options": {"ai": t["preview_finish"], "formula": t["preview_edit"]}},
        "ai": {"title": t["ai_title"], "description": t["ai_desc"],
               "data": {"ai_provider": t["ai_provider"]}},
        "ai_details": {"title": t["aid_title"], "description": t["aid_desc"],
                       "data": t["aid_fields"], "data_description": t["aid_fields_desc"]},
    }
    ai_errors = {"invalid_auth": t["err_auth"], "cannot_connect": t["err_conn"], "ai_failed": t["err_ai"], "prompt_invalid": t["err_prompt"]}
    return {
     "config": {
      "step": {
       "user": {"title": t["user_title"], "description": t["user_desc"],
                "data": merge({"name": t["name"]}, sd), "data_description": sdesc},
       "zone": merge({"title": t["zone_title"], "description": t["zone_desc"]}, zone_step),
       "zone_menu": {"title": t["menu_title"], "description": t["menu_desc"],
                     "menu_options": {"zone": t["menu_zone"], "schedule": t["menu_schedule"]}},
       "schedule": {"title": t["sched_title"], "description": t["sched_desc"], "data": pd, "data_description": pdesc},
       **formula_steps,
      },
      "error": {"name_required": t["err_name"], "valve_in_use": t["err_valve"], "min_greater_than_max": t["err_minmax"], "formula_invalid": t["err_formula"], **ai_errors},
      "abort": {"already_configured": t["already"]},
     },
     "options": {
      "step": {"init": {"title": t["opt_title"], "data": merge(sd, pd), "data_description": merge(sdesc, pdesc)}, **formula_steps},
      "error": {"formula_invalid": t["err_formula"], **ai_errors},
     },
     "config_subentries": {
      "zone": {
       "entry_type": t["sub_entry_type"],
       "initiate_flow": {"user": t["sub_add"]},
       "step": {
        "user": merge({"title": t["sub_user_title"]}, zone_step),
        "reconfigure": merge({"title": t["sub_reconf_title"]}, zone_step),
       },
       "error": {"name_required": t["err_name"], "valve_in_use": t["err_valve"], "min_greater_than_max": t["err_minmax"], "formula_invalid": t["err_formula"]},
       "abort": {"reconfigure_successful": t["sub_reconf_ok"]},
      }
     },
     "selector": {
      "weekday": {"options": t["weekday"]},
      "schedule": {"options": t["schedule"]},
      "time_format": {"options": t["time_format"]},
      "date_format": {"options": t["date_format"]},
      "run_mode": {"options": t["run_mode"]},
      "start_mode": {"options": t["start_mode"]},
      "exposure": {"options": t["exposure"]},
      "ai_provider": {"options": t["providers"]},
      "ai_on_error": {"options": t["on_error"]},
     },
     "entity": ent,
     "services": svcs,
     "exceptions": {"entry_not_found": {"message": t["exc_entry"]}, "schedule_empty": {"message": t["exc_schedule"]}},
    }

en = build("en"); it = build("it")
json.dump(en, open("strings.json","w"), indent=2, ensure_ascii=False)
json.dump(en, open("translations/en.json","w"), indent=2, ensure_ascii=False)
json.dump(it, open("translations/it.json","w"), indent=2, ensure_ascii=False)
for f in ("strings.json","translations/en.json","translations/it.json"):
    open(f,"a").write("\n")
print("ok")
