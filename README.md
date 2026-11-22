# Irrigazione AI

Integrazione per Home Assistant che gestisce un impianto di irrigazione multi-zona: durata calcolata per ogni zona da meteo e umidità del terriccio, programmazione al tramonto, blocco pioggia e chiusura di sicurezza delle valvole. Tutto si configura con una procedura guidata, senza scrivere automazioni.

*English summary below.*

> **Stato:** motore, wizard, formula personalizzata e analisi AI. Storico/consumi, notifiche avanzate e card arriveranno nelle prossime versioni.

## Installazione

1. In Home Assistant apri **Impostazioni → Marketplace** (su versioni precedenti alla 2026.11: **HACS**).
2. **Aggiungi da link** → `https://github.com/acaonweb/irrigazione-ai`, categoria *Integrazione*.
3. Installa **Irrigazione AI** e riavvia Home Assistant.
4. **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Irrigazione AI.**

## Configurazione guidata

1. **Impianto:** nome; entità meteo e sensori di temperatura e umidità esterna, tutti facoltativi (senza meteo il blocco pioggia resta inattivo).
2. **Zone:** una per valvola (`switch` o `valve`), con sensore di umidità del terriccio, portata in L/min, durata minima e massima, coefficiente, volume del terriccio ed esposizione. Le zone si aggiungono e modificano anche dopo, dalla pagina dell'integrazione (**Aggiungi zona**).
3. **Programmazione:** minuti dopo il tramonto, giorni per le frequenze settimanali, zone in parallelo o in sequenza, chiusura di sicurezza, chiusura delle valvole al riavvio, azioni di notifica.
4. **Formula:** editor della formula della durata, con anteprima dei minuti per ogni zona.
5. **Analisi AI** (facoltativa): servizio AI da usare, verificato con una richiesta di prova.

## Entità

| Entità | A cosa serve |
| --- | --- |
| Interruttore *Irrigazione* | Acceso = ciclo in corso. Accenderlo avvia, spegnerlo ferma e chiude le valvole |
| Interruttore *Blocco pioggia* | Se attivo, il ciclo non parte quando il meteo indica pioggia |
| Selettore *Frequenza* | Spenta, una volta a settimana, due volte a settimana, tutti i giorni |
| Selettore *Timer manuale* | 15/30/60 minuti per tutte le zone al posto della formula |
| Pulsanti *Avvia ora* / *Ferma* | Comandi immediati |
| Interruttore *Analisi AI* | Se acceso, a ogni ciclo l'AI decide se irrigare e quanto |
| Pulsante *Analizza ora* | Chiede subito una valutazione all'AI, senza irrigare |
| Sensore *Decisione AI* | Irrigare / Saltare / Errore, con motivo e litri per zona negli attributi |
| Sensori *Stato*, *Tempo rimanente*, *Prossima irrigazione*, *Ultima irrigazione*, *Ultimo blocco* | Stato dell'impianto |
| Per zona: *Durata prevista*, *Fine prevista*, *Durata AI* | Minuti calcolati ora (con litri, formula usata ed eventuale errore negli attributi) e ora di fine durante il ciclo |

## Servizi

- `irrigazione_ai.start` — avvia un ciclo. Campi facoltativi: `config_entry_id`, `duration` (minuti uguali per tutte le zone), `force` (ignora il blocco pioggia).
- `irrigazione_ai.stop` — ferma il ciclo e chiude le valvole.
- `irrigazione_ai.analyze` — chiede all'AI una valutazione senza irrigare e restituisce l'esito (decisione, motivo, litri e minuti per zona).

## Formula personalizzata

La durata di ogni zona si calcola con una **formula scritta come template Jinja**, lo stesso linguaggio dei sensori template di Home Assistant. Si modifica nel wizard e nelle opzioni dell'impianto. Ogni zona può averne una propria, che sostituisce quella dell'impianto. Prima di salvare, il wizard mostra quanti minuti darebbe a ogni zona con i valori attuali.

Formula predefinita:

```jinja
{{ (20 + 20 * (100 - moisture) / moisture + 20 * temperature / 25) * 0.9 * weather_factor * coefficient }}
```

| Variabile | Significato |
| --- | --- |
| `moisture` | Umidità del terriccio della zona in % (minimo 10; 50 se manca il sensore) |
| `moisture_raw` | Umidità del terriccio così com'è (`none` se manca) |
| `temperature` | Temperatura esterna in °C (20 se manca) |
| `humidity` | Umidità esterna in % (`none` se manca) |
| `weather` | Stato dell'entità meteo (`sunny`, `cloudy`, `rainy`…) |
| `weather_factor` | Sereno 1,1 · poco nuvoloso 0,8 · nuvoloso 0,5 · nebbia 0,6 · pioggia 0,2 · altro 1 |
| `coefficient` | Coefficiente della zona |
| `flow_rate` | Portata della zona in L/min |
| `soil_volume` | Volume del terriccio in L |
| `exposure` | `north`, `south`, `east`, `west` |
| `min_duration`, `max_duration` | Limiti della zona in minuti |

Si può leggere anche qualsiasi entità con `states('sensor.xxx')`. Il risultato viene **sempre** limitato tra durata minima e massima della zona. Se la formula smette di funzionare (per esempio perché un sensore che legge diventa non disponibile), l'integrazione usa la formula predefinita: l'errore compare nell'attributo `formula_error` del sensore *Durata prevista* della zona.

Esempi:

```jinja
{# Litri da dare in base al volume del terriccio, convertiti in minuti #}
{{ soil_volume * (60 - moisture) / 100 / flow_rate }}

{# Più acqua con l'esposizione a sud #}
{{ (40 - moisture / 2) * (1.3 if exposure == 'south' else 1) * weather_factor }}

{# Tempo fisso deciso da un helper #}
{{ states('input_number.minuti_irrigazione') | float(20) }}
```

## Analisi AI

Con l'interruttore *Analisi AI* acceso, prima di ogni ciclo l'integrazione chiede a un modello AI **se irrigare** e **quanti litri** dare a ogni zona. I litri diventano minuti con la portata della zona (arrotondati per eccesso e limitati tra minimo e massimo). Una zona con 0 litri non viene aperta.

**Servizi supportati**
- **Entità AI Task** di Home Assistant: usa un'integrazione AI già configurata (OpenAI, Anthropic, Google, Ollama…), senza chiavi nell'integrazione.
- **API key propria**: OpenAI, Anthropic Claude, Google Gemini.
- **Ollama** in locale, indicando l'indirizzo.

**Cosa riceve l'AI:** data e ora, posizione approssimata (1 decimale), meteo attuale, ore di pioggia nelle ultime 12 ore (dallo storico dell'entità meteo), previsioni orarie delle prossime 12 ore e, per ogni zona: umidità del terriccio, volume, esposizione, portata, limiti e minuti della formula. Nelle opzioni puoi aggiungere note libere (piante, vasi, clima…).

**Regole date all'AI:** stima dell'evapotraspirazione; si sottrae la pioggia caduta e prevista; niente irrigazione se ha piovuto per oltre metà delle ultime ore o è attesa pioggia significativa; 0 litri sopra il 70% di umidità del terriccio; irrigazione minima di mantenimento tra 50% e 65%; esposizione a sud aumenta il fabbisogno, a nord lo riduce.

**Se l'AI non risponde** puoi scegliere se saltare il ciclo o usare la formula. Con il timer manuale, o con una durata passata a `irrigazione_ai.start`, l'AI non viene interpellata.

## Sicurezza

- Una valvola aperta a mano (fuori da un ciclo) si chiude dopo i minuti di sicurezza impostati.
- Se Home Assistant si riavvia con una valvola aperta e nessun ciclo attivo, la chiude 30 secondi dopo l'avvio.
- Ogni chiusura viene ritentata fino a 3 volte; se fallisce arriva una notifica.

---

## English

Multi-zone irrigation for Home Assistant: per-zone durations from a user-editable Jinja formula (weather, soil moisture, any entity), sunset scheduling, rain block, optional AI analysis (Home Assistant AI Task, OpenAI, Anthropic, Gemini or Ollama) deciding liters per zone, safety close for valves, all set up through a config flow. Install from the Marketplace (or HACS) with **Add from link**, then add the *Irrigazione AI* integration. The UI is available in Italian and English.

## Licenza

MIT
