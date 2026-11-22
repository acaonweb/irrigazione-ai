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

## Entità

| Entità | A cosa serve |
| --- | --- |
| Interruttore *Irrigazione* | Acceso = ciclo in corso. Accenderlo avvia, spegnerlo ferma e chiude le valvole |
| Interruttore *Blocco pioggia* | Se attivo, il ciclo non parte quando il meteo indica pioggia |
| Selettore *Frequenza* | Spenta, una volta a settimana, due volte a settimana, tutti i giorni |
| Selettore *Timer manuale* | 15/30/60 minuti per tutte le zone al posto della formula |
| Pulsanti *Avvia ora* / *Ferma* | Comandi immediati |
| Sensori *Stato*, *Tempo rimanente*, *Prossima irrigazione*, *Ultima irrigazione*, *Ultimo blocco* | Stato dell'impianto |
| Per zona: *Durata prevista*, *Fine prevista* | Minuti calcolati ora (con litri negli attributi) e ora di fine durante il ciclo |

## Servizi

- `irrigazione_ai.start` — avvia un ciclo. Campi facoltativi: `config_entry_id`, `duration` (minuti uguali per tutte le zone), `force` (ignora il blocco pioggia).
- `irrigazione_ai.stop` — ferma il ciclo e chiude le valvole.

## Formula

Per ogni zona: `t = (20 + 20·(100−u)/u + 20·T/25) · 0,9 · fattore_meteo · coefficiente`, con `u` umidità del terriccio (minimo 10%) e `T` temperatura esterna, limitata tra durata minima e massima. Fattori meteo: sereno 1,1; poco nuvoloso 0,8; nuvoloso 0,5; pioggia 0,2.

## Sicurezza

- Una valvola aperta a mano (fuori da un ciclo) si chiude dopo i minuti di sicurezza impostati.
- Se Home Assistant si riavvia con una valvola aperta e nessun ciclo attivo, la chiude 30 secondi dopo l'avvio.
- Ogni chiusura viene ritentata fino a 3 volte; se fallisce arriva una notifica.

---

## English

Multi-zone irrigation for Home Assistant: per-zone durations from weather and soil moisture, sunset scheduling, rain block, safety close for valves, all set up through a config flow. Install from the Marketplace (or HACS) with **Add from link**, then add the *Irrigazione AI* integration. The UI is available in Italian and English.

## Licenza

MIT
