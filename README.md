# Irrigazione AI

Integrazione per Home Assistant che gestisce un impianto di irrigazione multi-zona: durata calcolata per ogni zona da meteo e umidità del terriccio, programmazione al tramonto, blocco pioggia e chiusura di sicurezza delle valvole. Tutto si configura con una procedura guidata, senza scrivere automazioni.

*English summary below.*

> **Stato:** fase 1 (motore e wizard). Analisi AI con LLM, storico/consumi, notifiche avanzate e card arriveranno nelle prossime versioni.

## Installazione

1. In Home Assistant apri **Impostazioni → Marketplace** (su versioni precedenti alla 2026.11: **HACS**).
2. **Aggiungi da link** → `https://github.com/acaonweb/irrigazione-ai`, categoria *Integrazione*.
3. Installa **Irrigazione AI** e riavvia Home Assistant.
4. **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Irrigazione AI.**

## Configurazione guidata

1. **Impianto:** nome, entità meteo, sensori facoltativi di temperatura e umidità esterna.
2. **Zone:** una per valvola (`switch` o `valve`), con sensore di umidità del terriccio, portata in L/min, durata minima e massima, coefficiente, volume del terriccio ed esposizione. Le zone si aggiungono e modificano anche dopo, dalla pagina dell'integrazione (**Aggiungi zona**).
3. **Programmazione:** minuti dopo il tramonto, giorni per le frequenze settimanali, zone in parallelo o in sequenza, chiusura di sicurezza, chiusura delle valvole al riavvio, azioni di notifica.
4. **Formula:** editor della formula della durata, con anteprima dei minuti per ogni zona.

## Entità

| Entità | A cosa serve |
| --- | --- |
| Interruttore *Irrigazione* | Acceso = ciclo in corso. Accenderlo avvia, spegnerlo ferma e chiude le valvole |
| Interruttore *Blocco pioggia* | Se attivo, il ciclo non parte quando il meteo indica pioggia |
| Selettore *Frequenza* | Spenta, una volta a settimana, due volte a settimana, tutti i giorni |
| Selettore *Timer manuale* | 15/30/60 minuti per tutte le zone al posto della formula |
| Pulsanti *Avvia ora* / *Ferma* | Comandi immediati |
| Sensori *Stato*, *Tempo rimanente*, *Prossima irrigazione*, *Ultima irrigazione*, *Ultimo blocco* | Stato dell'impianto |
| Per zona: *Durata prevista*, *Fine prevista* | Minuti calcolati ora (con litri, formula usata ed eventuale errore negli attributi) e ora di fine durante il ciclo |

## Servizi

- `irrigazione_ai.start` — avvia un ciclo. Campi facoltativi: `config_entry_id`, `duration` (minuti uguali per tutte le zone), `force` (ignora il blocco pioggia).
- `irrigazione_ai.stop` — ferma il ciclo e chiude le valvole.

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

## Sicurezza

- Una valvola aperta a mano (fuori da un ciclo) si chiude dopo i minuti di sicurezza impostati.
- Se Home Assistant si riavvia con una valvola aperta e nessun ciclo attivo, la chiude 30 secondi dopo l'avvio.
- Ogni chiusura viene ritentata fino a 3 volte; se fallisce arriva una notifica.

---

## English

Multi-zone irrigation for Home Assistant: per-zone durations from a user-editable Jinja formula (weather, soil moisture, any entity), sunset scheduling, rain block, safety close for valves, all set up through a config flow. Install from the Marketplace (or HACS) with **Add from link**, then add the *Irrigazione AI* integration. The UI is available in Italian and English.

## Licenza

MIT
