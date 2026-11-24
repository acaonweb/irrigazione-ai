/*
 * Irrigazione AI — card Lovelace (registrate automaticamente dall'integrazione)
 *
 *   type: custom:irrigazione-ai-card          # controllo: generale, AI, pioggia, zone, timer, programmazione per zona
 *   type: custom:irrigazione-ai-charts-card   # grafici: consumi 7 giorni, umidità terriccio, esterno
 *   type: custom:irrigazione-ai-moisture-card # umidità terriccio di sensori a scelta
 *
 * Opzioni comuni: entity (sensore "Stato" dell'impianto, facoltativo), title.
 */

const CARD_VERSION = "0.13.0";

const TEXT = {
  it: {
    general: "Irrigazione Generale", active: "Irrigazione attiva", inactive: "Irrigazione inattiva",
    blocked: { rain: "Saltata per pioggia", ai: "Saltata dall'AI", ai_error: "AI non riuscita" },
    next: "prossima", ends: "fine", remaining: "Tempo rimanente", zone: "Zona",
    moisture: "Umidità", dry: "🔴 Secco", ok: "🟢 Ottimale", wet: "💧 Umido",
    planned: "Prevista", noSensor: "nessun sensore", unavailable: "non disponibile", battery: "Batteria", ai: "AI", rain: "Pioggia", setup: "Configura",
    aiTitle: "🤖 Decisione AI", analyze: "Analizza", durations: "Durate previste", aiDurations: "Durate AI",
    decision: { irrigate: "Irrigare", skip: "Saltare", error: "Errore", unknown: "Nessuna analisi" },
    off: "Off", daily: "7/7", min: "min", skip: "salta",
    schedule: "Programmazione", alternate: "1 sì 1 no", chosen: "Giorni", zoneOff: "spenta", noDays: "nessun giorno",
    altFrom: "un giorno sì e uno no dal", nextShort: "prossima",
    water7: "💧 Consumo acqua", soil: "Umidità terriccio", outdoor: "Esterno", temp: "Temperatura", hum: "Umidità",
    noData: "Nessun dato", noEntity: "Nessun impianto Irrigazione AI trovato.",
    today: "Oggi", month: "Mese", total: "Totale", log: "📒 Registro irrigazioni", noEvents: "Nessun evento negli ultimi 14 giorni",
    collecting: "Le colonne compaiono quando HA ha calcolato le statistiche (a fine ora)",
    days: { mon: "Lun", tue: "Mar", wed: "Mer", thu: "Gio", fri: "Ven", sat: "Sab", sun: "Dom" },
  },
  en: {
    general: "Irrigation", active: "Watering", inactive: "Idle",
    blocked: { rain: "Skipped for rain", ai: "Skipped by AI", ai_error: "AI failed" },
    next: "next", ends: "ends", remaining: "Time remaining", zone: "Zone",
    moisture: "Moisture", dry: "🔴 Dry", ok: "🟢 Good", wet: "💧 Wet",
    planned: "Planned", noSensor: "no sensor", unavailable: "unavailable", battery: "Battery", ai: "AI", rain: "Rain", setup: "Set up",
    aiTitle: "🤖 AI decision", analyze: "Analyze", durations: "Planned durations", aiDurations: "AI durations",
    decision: { irrigate: "Water", skip: "Skip", error: "Error", unknown: "No analysis yet" },
    off: "Off", daily: "7/7", min: "min", skip: "skip",
    schedule: "Schedule", alternate: "Every 2", chosen: "Days", zoneOff: "off", noDays: "no days",
    altFrom: "every other day from", nextShort: "next",
    water7: "💧 Water use", soil: "Soil moisture", outdoor: "Outdoor", temp: "Temperature", hum: "Humidity",
    noData: "No data", noEntity: "No Irrigazione AI system found.",
    today: "Today", month: "Month", total: "Total", log: "📒 Irrigation log", noEvents: "No events in the last 14 days",
    collecting: "Bars appear once HA has compiled the statistics (at the end of the hour)",
    days: { mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri", sat: "Sat", sun: "Sun" },
  },
};

const BASE_STYLE = `
  :host { display: block; --ia-blue: rgb(33,150,243); --ia-red: rgb(244,67,54);
          --ia-tile: var(--ha-card-background, var(--card-background-color, #fff)); }
  ha-card { display: block; padding: 12px; background: color-mix(in srgb, #03a9f4 14%, var(--ha-card-background, var(--card-background-color))); }
  .grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 8px; }
  .tile { background: var(--ia-tile); border-radius: 12px; padding: 10px 12px; box-sizing: border-box;
          border: 1px solid var(--divider-color, rgba(0,0,0,.08)); cursor: pointer; position: relative;
          transition: box-shadow .3s; min-width: 0; }
  .span12 { grid-column: span 12; } .span9 { grid-column: span 9; } .span6 { grid-column: span 6; } .span3 { grid-column: span 3; }
  .row { display: flex; align-items: center; gap: 10px; min-width: 0; }
  .shape { width: 40px; height: 40px; flex: none; border-radius: 50%; display: grid; place-items: center;
           background: color-mix(in srgb, var(--ia-c, #9e9e9e) 20%, transparent); color: var(--ia-c, #9e9e9e); }
  .txt { min-width: 0; flex: 1; }
  .primary { font-weight: 600; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .secondary { font-size: 12px; color: var(--secondary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .vertical { flex-direction: column; text-align: center; justify-content: center; height: 100%; }
  .vertical .txt { width: 100%; }
  .glow-blue { box-shadow: 0 0 15px 4px rgba(33,150,243,.6); }
  .glow-red { box-shadow: 0 0 12px 3px rgba(244,67,54,.7); }
  .spray .shape ha-icon { animation: spray 1.2s infinite ease-in-out; }
  @keyframes spray { 0%,50%,100% { transform: rotate(0); } 25% { transform: rotate(10deg); } 75% { transform: rotate(-10deg); } }
  .wrap .primary, .wrap .secondary { white-space: normal; overflow: visible; }
  .sec-title { grid-column: span 12; font-weight: 600; font-size: 13px; margin: 4px 2px 0; color: var(--primary-text-color); }
`;

const CONTROL_STYLE = `
  .yellow { height: 56px; border-radius: 16px; display: flex; align-items: center; justify-content: center; gap: 6px;
            background: rgba(35,35,35,.95); color: #fff; font-weight: 600; font-size: 13px; cursor: pointer; border: none; font-family: inherit; }
  .yellow.on { background: linear-gradient(135deg,#FFD54F,#FFA000); color: #3d2b00; }
  .yellow.setup { flex-direction: column; gap: 0; opacity: .75; }
  .yellow.setup small { font-weight: 400; font-size: 11px; opacity: .8; }
  .stack { display: flex; flex-direction: column; gap: 8px; }
  .btns { display: grid; gap: 8px; }
  .btn { border-radius: 12px; min-height: 48px; padding: 6px; cursor: pointer; display: flex; flex-direction: column;
         align-items: center; justify-content: center; gap: 2px; background: var(--ia-tile); color: var(--primary-text-color);
         font: inherit; font-size: 12px; border: 1px solid var(--divider-color, rgba(0,0,0,.08)); }
  .btn.on { background: rgba(0,150,255,.4); }
  .value { font-weight: 600; font-size: 15px; }
  .md { font-size: 13px; line-height: 1.4; }
  .md b { display: block; margin-bottom: 4px; font-size: 14px; }
  .mini { border: none; border-radius: 999px; padding: 5px 12px; background: var(--ia-blue); color: #fff; cursor: pointer;
          font: inherit; font-size: 12px; }
  .chips { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; font-size: 11px; }
  .chip { padding: 2px 8px; border-radius: 999px; background: var(--secondary-background-color); color: var(--secondary-text-color); }
  .chip.blue { background: rgba(33,150,243,.18); color: var(--ia-blue); font-weight: 600; }
  .sched { cursor: default; display: flex; flex-direction: column; gap: 8px; }
  .shead { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
  .shead .sname { font-weight: 600; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .shead .snext { font-size: 11px; color: var(--secondary-text-color); white-space: nowrap; }
  .modes { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
  .modes .btn { min-height: 36px; flex-direction: row; gap: 4px; font-size: 11px; padding: 4px; }
  .modes .btn ha-icon { --mdc-icon-size: 16px; }
  .wdays { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
  .wday { height: 30px; border-radius: 999px; border: 1px solid var(--divider-color, rgba(0,0,0,.12)); cursor: pointer;
          background: transparent; color: var(--primary-text-color); font: inherit; font-size: 11px; padding: 0; }
  .wday.on { background: var(--ia-blue); border-color: var(--ia-blue); color: #fff; font-weight: 600; }
  .wdays.dim .wday { opacity: .45; }
  .salt { font-size: 11px; color: var(--secondary-text-color); }
`;

const CHART_STYLE = `
  .chart { grid-column: span 12; }
  .ctitle { font-weight: 600; font-size: 14px; margin-bottom: 6px; }
  .legend { display: flex; gap: 12px; font-size: 11px; color: var(--secondary-text-color); margin-top: 4px; }
  .legend i { display: inline-block; width: 10px; height: 3px; border-radius: 2px; margin-right: 4px; vertical-align: middle; }
  svg { width: 100%; display: block; overflow: visible; }
  .axis { font-size: 10px; fill: var(--secondary-text-color); }
  .lbl { font-size: 10px; fill: var(--primary-text-color); font-weight: 600; }
  .empty { font-size: 12px; color: var(--secondary-text-color); padding: 20px 0; text-align: center; }
  .stats3 { grid-column: span 12; display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .stat { background: var(--ia-tile); border-radius: 12px; padding: 8px 12px; border: 1px solid var(--divider-color, rgba(0,0,0,.08)); }
  .stat .k { font-size: 11px; color: var(--secondary-text-color); }
  .stat .v { font-size: 16px; font-weight: 700; color: #0A84FF; }
  .ev { display: flex; gap: 10px; align-items: flex-start; padding: 8px 0; border-top: 1px solid var(--divider-color, rgba(0,0,0,.08)); }
  .ev:first-of-type { border-top: none; }
  .ev .ico { font-size: 18px; line-height: 22px; width: 22px; text-align: center; flex: none; }
  .ev .body { flex: 1; min-width: 0; }
  .ev .t1 { font-size: 13px; font-weight: 600; }
  .ev .t2 { font-size: 11px; color: var(--secondary-text-color); white-space: pre-line; }
  .ev .lit { font-size: 13px; font-weight: 700; color: #0A84FF; white-space: nowrap; }
  .ev.future { opacity: .75; }
`;

/* ------------------------------------------------------------------ */

class IrrigazioneAiBase extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._sig = null;
  }

  static getStubConfig(hass) {
    const id = Object.keys(hass.states).find(
      (e) => e.startsWith("sensor.") && hass.states[e].attributes && hass.states[e].attributes.card);
    return id ? { entity: id } : {};
  }

  _statusId() {
    if (this._config && this._config.entity) return this._config.entity;
    const h = this._hass;
    return Object.keys(h.states).find(
      (e) => e.startsWith("sensor.") && h.states[e].attributes && h.states[e].attributes.card);
  }

  _map() {
    const st = this._s(this._statusId());
    return st && st.attributes.card ? st.attributes.card : null;
  }

  _t() { return (this._hass.language || "en").startsWith("it") ? TEXT.it : TEXT.en; }
  _s(id) { return id ? this._hass.states[id] : undefined; }
  _num(id) { const s = this._s(id); const n = s ? parseFloat(s.state) : NaN; return isNaN(n) ? null : n; }
  _lang() { return this._hass.language || undefined; }
  _fmt(v, d = 1) { return v.toLocaleString(this._lang(), { maximumFractionDigits: d }); }

  // Formati scelti: opzione della card > opzione dell'integrazione > profilo utente
  _formats() {
    const map = this._map ? this._map() : null;
    const sys = (map && map.formats) || {};
    const loc = this._hass.locale || {};
    const pick = (card, integ, profile) => (card && card !== "auto" ? card : (integ && integ !== "auto" ? integ : profile));
    const time = pick(this._config && this._config.time_format, sys.time,
      loc.time_format === "12" ? "12" : loc.time_format === "24" ? "24" : null);
    const date = pick(this._config && this._config.date_format, sys.date,
      { DMY: "dmy", MDY: "mdy", YMD: "ymd" }[loc.date_format] || null);
    return { time, date };
  }

  _hm(d) {
    const { time } = this._formats();
    const opts = { hour: "2-digit", minute: "2-digit" };
    if (time === "12") { opts.hour12 = true; opts.hour = "numeric"; }
    if (time === "24") { opts.hour12 = false; opts.hourCycle = "h23"; }
    return d.toLocaleTimeString(this._lang(), opts);
  }

  _dm(d, year = false) {
    const { date } = this._formats();
    const dd = String(d.getDate()).padStart(2, "0"), mm = String(d.getMonth() + 1).padStart(2, "0");
    const yy = year ? d.getFullYear() : null;
    if (date === "mdy") return yy ? `${mm}/${dd}/${yy}` : `${mm}/${dd}`;
    if (date === "dmy") return yy ? `${dd}/${mm}/${yy}` : `${dd}/${mm}`;
    if (date === "ymd") return yy ? `${yy}-${mm}-${dd}` : `${mm}-${dd}`;
    return d.toLocaleDateString(this._lang(), year ? { day: "2-digit", month: "2-digit", year: "numeric" } : { day: "2-digit", month: "2-digit" });
  }

  _wd(d) { return d.toLocaleDateString(this._lang(), { weekday: "short" }); }

  _time(iso, withDay) {
    if (!iso || iso === "unknown" || iso === "unavailable") return "";
    const d = new Date(iso);
    if (isNaN(d)) return "";
    return withDay ? `${this._wd(d)} ${this._hm(d)}` : this._hm(d);
  }

  _call(domain, service, data) { this._hass.callService(domain, service, data); }

  _signature(ids) {
    return ids.filter(Boolean).map((e) => {
      const s = this._hass.states[e];
      return s ? s.state + s.last_updated : "-";
    }).join("|") + (this._hass.language || "");
  }

  _allIds(map) {
    const ids = [this._statusId()];
    Object.values(map.system).forEach((e) => e && ids.push(e));
    map.zones.forEach((z) => Object.values(z).forEach((e) => typeof e === "string" && e.includes(".") && ids.push(e)));
    [map.temperature, map.humidity].forEach((e) => e && ids.push(e));
    return ids;
  }

  _battery(valve) {
    const ents = this._hass.entities;
    const ent = ents && ents[valve];
    if (!ent || !ent.device_id) return null;
    const id = Object.keys(ents).find((e) => {
      const st = this._hass.states[e];
      return ents[e].device_id === ent.device_id && e.startsWith("sensor.")
        && st && st.attributes.device_class === "battery";
    });
    return id || null;
  }

  _empty(msg) {
    this.shadowRoot.innerHTML = `<style>${BASE_STYLE}</style><ha-card><div class="secondary" style="padding:8px">${msg}</div></ha-card>`;
  }
}

/* ------------------------------------------------------------------ */

class IrrigazioneAiCard extends IrrigazioneAiBase {
  getCardSize() { return 9; }

  set hass(hass) {
    this._hass = hass;
    const map = this._map();
    if (!map) { if (this._sig !== "none") { this._sig = "none"; this._empty(this._t().noEntity); } return; }
    this._dryAt = map.dry_threshold ?? 25;
    const batteries = map.zones.map((z) => this._battery(z.valve));
    const sig = this._signature([...this._allIds(map), ...batteries]);
    if (sig === this._sig) return;
    this._sig = sig;
    this._render(map, batteries);
  }

  // Due per riga; se il numero è dispari l'ultima occupa tutta la larghezza
  _span(i, count) {
    return count % 2 === 1 && i === count - 1 ? "span12" : "span6";
  }

  _zoneTile(z, i, t, battery, count) {
    const valve = this._s(z.valve);
    const on = valve && ["on", "open", "opening"].includes(valve.state);
    const m = this._num(z.moisture);
    const dryAt = this._dryAt ?? 25;
    const planned = this._num(z.duration);
    const ai = this._num(z.ai);
    const water = this._num(z.water_today);
    const end = this._s(z.end);
    // Stesse informazioni per ogni zona: umidità (o il motivo per cui manca) e durata prevista
    const secondary = m !== null
      ? `${t.moisture} ${Math.round(m)}% · ${m < dryAt ? t.dry : m <= 50 ? t.ok : t.wet}`
      : `${t.moisture}: ${z.moisture ? t.unavailable : t.noSensor}`;
    const glow = on ? "glow-blue" : (m !== null && m < dryAt ? "glow-red" : "");
    const chips = [];
    if (on && end && this._time(end.state)) chips.push(`<span class="chip blue">${t.ends} ${this._time(end.state)}</span>`);
    chips.push(`<span class="chip">⏱ ${planned === null ? "–" : planned + " " + t.min}</span>`);
    if (ai !== null) chips.push(`<span class="chip">🤖 ${ai === 0 ? t.skip : ai + " " + t.min}</span>`);
    if (water) chips.push(`<span class="chip">💧 ${this._fmt(water)} L</span>`);
    const bat = battery ? this._num(battery) : null;
    if (bat !== null) chips.push(`<span class="chip">${bat > 80 ? "🟢" : bat > 40 ? "🟡" : "🔴"} ${t.battery} ${Math.round(bat)}%</span>`);
    return `
      <div class="tile ${this._span(i, count)} ${glow} ${on ? "spray" : ""}" data-valve="${z.valve}" data-on="${on ? 1 : 0}">
        <div class="row">
          <div class="shape" style="--ia-c:${on ? "var(--ia-blue)" : "#9e9e9e"}"><ha-icon icon="mdi:sprinkler"></ha-icon></div>
          <div class="txt wrap"><div class="primary">${t.zone} ${i + 1} – ${z.name}</div><div class="secondary">${secondary}</div></div>
        </div>
        ${chips.length ? `<div class="chips">${chips.join("")}</div>` : ""}
      </div>`;
  }

  _render(map, batteries) {
    const t = this._t();
    const sys = map.system;
    const status = this._s(this._statusId());
    const running = status.state === "running";
    const block = this._s(sys.last_block);
    const remaining = this._num(sys.remaining);

    let secondary;
    if (running) {
      secondary = t.active + (remaining !== null ? ` · ${remaining} ${t.min}` : "");
    } else if (status.state === "blocked" && block) {
      secondary = t.blocked[block.attributes.reason] || t.inactive;
    } else {
      const next = this._s(sys.next_run);
      const when = next ? this._time(next.state, true) : "";
      secondary = t.inactive + (when ? ` · ${t.next} ${when}` : "");
    }

    const aiSw = map.ai ? this._s(sys.ai_analysis) : null;
    const rain = this._s(sys.rain_block);
    const aiOn = !!(aiSw && aiSw.state === "on");

    const timer = this._s(sys.manual_timer);
    const timerIcons = { off: "mdi:timer-check", 15: "mdi:fast-forward-15", 30: "mdi:fast-forward-30", 60: "mdi:fast-forward-60" };
    const timerBtns = timer ? timer.attributes.options.map((o) => `
      <button class="btn ${o === timer.state ? "on" : ""}" data-select="${sys.manual_timer}" data-option="${o}">
        <ha-icon icon="${timerIcons[o] || "mdi:timer"}"></ha-icon></button>`).join("") : "";

    const dname = (d) => t.days[d] || d;
    const WEEK = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
    const modeBtns = [
      ["off", t.off, "mdi:power"], ["alternate", t.alternate, "mdi:swap-horizontal"],
      ["days", t.chosen, "mdi:calendar-week"], ["daily", t.daily, "mdi:calendar"],
    ];
    const schedTiles = map.zones.map((z, i) => {
      const st = this._s(z.schedule);
      if (!st) return "";
      const mode = st.state;
      const days = st.attributes.days || [];
      const nextIso = st.attributes.next_run;
      let info = nextIso ? `${t.nextShort} ${this._time(nextIso, true)}` : (mode === "off" ? t.zoneOff : t.noDays);
      const modes = modeBtns.map(([m, label, icon]) => `
        <button class="btn ${m === mode ? "on" : ""}" data-sched="${z.schedule}" data-mode="${m}">
          <ha-icon icon="${icon}"></ha-icon><span>${label}</span></button>`).join("");
      let dayRow;
      if (mode === "alternate") {
        const from = st.attributes.alternate_from
          ? this._dm(new Date(st.attributes.alternate_from + "T12:00:00")) : "";
        dayRow = `<div class="salt">↔ ${t.altFrom} ${from}</div>`;
      } else {
        const active = mode === "daily" ? WEEK : (mode === "days" ? days : []);
        dayRow = `<div class="wdays ${mode === "days" ? "" : "dim"}">${WEEK.map((d) => `
          <button class="wday ${active.includes(d) ? "on" : ""}" data-sched="${z.schedule}" data-day="${d}"
            data-mode-now="${mode}" data-days="${active.join(",")}">${dname(d)}</button>`).join("")}</div>`;
      }
      return `<div class="tile span12 sched">
        <div class="shead"><span class="sname">${t.zone} ${i + 1} – ${z.name}</span><span class="snext">${info}</span></div>
        <div class="modes">${modes}</div>${dayRow}</div>`;
    }).join("");

    const durTiles = map.zones.map((z, i) => {
      const id = aiOn ? z.ai : z.duration;
      const v = this._num(id);
      const label = v === null ? "–" : (aiOn && v === 0 ? t.skip : `${v} ${t.min}`);
      return `<div class="tile ${this._span(i, map.zones.length)}" data-more="${id}"><div class="row">
        <div class="shape" style="--ia-c:${aiOn ? "#ffa000" : "var(--ia-blue)"}"><ha-icon icon="mdi:${aiOn ? "robot" : "sprinkler"}"></ha-icon></div>
        <div class="txt"><div class="secondary">${t.zone} ${i + 1} – ${z.name}</div><div class="value">${label}</div></div></div></div>`;
    }).join("");

    let aiBox = "";
    if (aiOn) {
      const d = this._s(sys.ai_decision);
      const state = d ? d.state : "unknown";
      const reason = d ? (d.attributes.reason || d.attributes.error || "") : "";
      aiBox = `<div class="tile span12" style="cursor:default"><div class="row" style="align-items:flex-start">
        <div class="md txt"><b>${t.aiTitle}: ${t.decision[state] || t.decision.unknown}</b>${reason}</div>
        <button class="mini" data-press="${sys.analyze}">${t.analyze}</button></div></div>`;
    }

    const remainingTile = running ? `<div class="tile span12" data-more="${sys.remaining}"><div class="row">
      <div class="shape" style="--ia-c:var(--ia-blue)"><ha-icon icon="mdi:timer-sand"></ha-icon></div>
      <div class="txt"><div class="secondary">${t.remaining}</div><div class="value">${remaining === null ? "–" : remaining + " " + t.min}</div></div></div></div>` : "";

    const aiReady = aiSw && aiSw.state !== "unavailable";
    const aiButton = aiReady
      ? `<button class="yellow ${aiOn ? "on" : ""}" data-toggle="${sys.ai_analysis}"><ha-icon icon="mdi:robot"></ha-icon>${t.ai}</button>`
      : `<button class="yellow setup" data-setup="1"><span><ha-icon icon="mdi:robot"></ha-icon> ${t.ai}</span><small>${t.setup}</small></button>`;
    const showSide = true;
    this.shadowRoot.innerHTML = `
      <style>${BASE_STYLE}${CONTROL_STYLE}</style>
      <ha-card><div class="grid">
        <div class="tile ${showSide ? "span9" : "span12"} ${running ? "glow-blue" : ""}" data-toggle="${sys.irrigation}" style="min-height:120px">
          <div class="row vertical">
            <div class="shape" style="--ia-c:${running ? "var(--ia-blue)" : "#9e9e9e"}"><ha-icon icon="mdi:water-pump"></ha-icon></div>
            <div class="txt"><div class="primary">${this._config.title || t.general}</div><div class="secondary">${secondary}</div></div>
          </div>
        </div>
        ${showSide ? `<div class="span3 stack">
          ${aiButton}
          ${rain ? `<button class="yellow ${rain.state === "on" ? "on" : ""}" data-toggle="${sys.rain_block}"><ha-icon icon="mdi:weather-rainy"></ha-icon>${t.rain}</button>` : ""}
        </div>` : ""}
        ${map.zones.map((z, i) => this._zoneTile(z, i, t, batteries[i], map.zones.length)).join("")}
        ${timer ? `<div class="btns span12" style="grid-template-columns:repeat(${timer.attributes.options.length},1fr)">${timerBtns}</div>` : ""}
        ${schedTiles ? `<div class="sec-title">📅 ${t.schedule}</div>${schedTiles}` : ""}
        <div class="sec-title">${aiOn ? t.aiDurations : t.durations}</div>
        ${durTiles}
        ${aiBox}
        ${remainingTile}
      </div></ha-card>`;

    const root = this.shadowRoot;
    root.querySelectorAll("[data-toggle]").forEach((el) => el.addEventListener("click", (ev) => {
      ev.stopPropagation(); this._call("switch", "toggle", { entity_id: el.dataset.toggle });
    }));
    root.querySelectorAll("[data-setup]").forEach((el) => el.addEventListener("click", () => {
      history.pushState(null, "", "/config/integrations/integration/irrigazione_ai");
      window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
    }));
    root.querySelectorAll("[data-select]").forEach((el) => el.addEventListener("click", () =>
      this._call("select", "select_option", { entity_id: el.dataset.select, option: el.dataset.option })));
    root.querySelectorAll("[data-mode]").forEach((el) => el.addEventListener("click", () =>
      this._call("select", "select_option", { entity_id: el.dataset.sched, option: el.dataset.mode })));
    root.querySelectorAll("[data-day]").forEach((el) => el.addEventListener("click", () => {
      const cur = el.dataset.days ? el.dataset.days.split(",") : [];
      const d = el.dataset.day;
      const days = cur.includes(d) ? cur.filter((x) => x !== d) : [...cur, d];
      this._call("irrigazione_ai", "set_schedule", { entity_id: el.dataset.sched, days });
    }));
    root.querySelectorAll("[data-press]").forEach((el) => el.addEventListener("click", (ev) => {
      ev.stopPropagation(); this._call("button", "press", { entity_id: el.dataset.press });
    }));
    root.querySelectorAll("[data-valve]").forEach((el) => el.addEventListener("click", () => {
      const valve = el.dataset.valve;
      const on = el.dataset.on === "1";
      if (valve.startsWith("valve.")) this._call("valve", on ? "close_valve" : "open_valve", { entity_id: valve });
      else this._call("homeassistant", on ? "turn_off" : "turn_on", { entity_id: valve });
    }));
    root.querySelectorAll("[data-more]").forEach((el) => el.addEventListener("click", () => {
      const ev = new Event("hass-more-info", { bubbles: true, composed: true });
      ev.detail = { entityId: el.dataset.more };
      this.dispatchEvent(ev);
    }));
  }
}

/* ------------------------------------------------------------------ */

class IrrigazioneAiChartsCard extends IrrigazioneAiBase {
  getCardSize() { return 8; }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    const map = this._map();
    if (!map) { if (this._sig !== "none") { this._sig = "none"; this._empty(this._t().noEntity); } return; }
    const now = Date.now();
    const sig = this._signature([map.system.water_today, map.system.water_month, map.system.water_total,
      map.system.last_run, map.system.last_block, this._statusId()]);
    if (first || !this._loaded || now - this._loaded > 10 * 60 * 1000 || (this._sig && sig !== this._sig)) {
      this._loaded = now;
      this._sig = sig;
      this._load(map);
    } else if (!this._sig) {
      this._sig = sig;
    }
  }

  async _load(map) {
    const hass = this._hass;
    const end = new Date();
    const data = { water: [], soil: {}, outdoor: {} };
    try {
      if (map.system.water_total) {
        const start = new Date(end); start.setHours(0, 0, 0, 0); start.setDate(start.getDate() - 6);
        const stats = await hass.callWS({
          type: "recorder/statistics_during_period", start_time: start.toISOString(), end_time: end.toISOString(),
          statistic_ids: [map.system.water_total], period: "day", types: ["change"],
        });
        const rows = stats[map.system.water_total] || [];
        for (let i = 0; i < 7; i++) {
          const day = new Date(start); day.setDate(start.getDate() + i);
          const row = rows.find((r) => new Date(r.start).toDateString() === day.toDateString());
          data.water.push({ day, value: row && row.change ? Math.max(0, row.change) : 0 });
        }
      }
    } catch (e) { /* statistiche non disponibili */ }
    try {
      const ids = map.zones.map((z) => z.moisture).filter(Boolean);
      const outIds = [map.temperature, map.humidity].filter(Boolean);
      if (ids.length) {
        const h = await hass.callWS({
          type: "history/history_during_period", start_time: new Date(end - 5 * 86400e3).toISOString(),
          end_time: end.toISOString(), entity_ids: ids, minimal_response: true, no_attributes: true,
        });
        ids.forEach((id) => { data.soil[id] = this._points(h[id]); });
      }
      if (outIds.length) {
        const h = await hass.callWS({
          type: "history/history_during_period", start_time: new Date(end - 86400e3).toISOString(),
          end_time: end.toISOString(), entity_ids: outIds, minimal_response: true, no_attributes: true,
        });
        outIds.forEach((id) => { data.outdoor[id] = this._points(h[id]); });
      }
    } catch (e) { /* storico non disponibile */ }
    try {
      const cal = map.system.calendar;
      if (cal && this._config.show_log !== false) {
        const start = new Date(end - 14 * 86400e3).toISOString();
        const stop = new Date(end.getTime() + 8 * 86400e3).toISOString();
        data.events = await hass.callApi("GET", `calendars/${cal}?start=${encodeURIComponent(start)}&end=${encodeURIComponent(stop)}`);
      }
    } catch (e) { /* calendario non disponibile */ }
    this._data = data;
    this._render(map);
  }

  _log(events, t) {
    const now = Date.now();
    const parse = (x) => Date.parse((x && (x.dateTime || x.date)) || x);
    const past = (events || []).filter((e) => parse(e.start) <= now && !/prevista|planned|in corso|in progress|running/i.test(e.summary))
      .sort((a, b) => parse(b.start) - parse(a.start)).slice(0, this._config.log_items || 8);
    const next = (events || []).filter((e) => parse(e.start) > now).sort((a, b) => parse(a.start) - parse(b.start))[0];
    const fmt = (ms) => { const d = new Date(ms); return `${this._wd(d)} ${this._dm(d)} ${this._hm(d)}`; };
    const liters = (desc) => {
      if (!desc) return null;
      const tot = desc.match(/(?:Totale|Total):\s*([\d.,]+)\s*L/);
      if (tot) return parseFloat(tot[1].replace(",", "."));
      const all = [...desc.matchAll(/([\d]+[.,]?[\d]*)\s*L\b/g)].map((m) => parseFloat(m[1].replace(",", ".")));
      return all.length ? all.reduce((a, b) => a + b, 0) : null;
    };
    const icon = (e) => /saltata|skipped|pioggia|rain/i.test(e.summary) ? "🚫" : /manuale|manual/i.test(e.summary) ? "✋" : /interrotta|stopped/i.test(e.summary) ? "⏹️" : "💧";
    const row = (e, future) => {
      const s = parse(e.start), en = parse(e.end);
      const mins = Math.max(0, Math.round((en - s) / 60000));
      const l = future ? null : liters(e.description);
      const detail = (e.description || "").split("\n").filter((x) => !/^(Totale|Total):/.test(x)).join("\n");
      return `<div class="ev ${future ? "future" : ""}"><div class="ico">${future ? "📅" : icon(e)}</div>
        <div class="body"><div class="t1">${e.summary}</div><div class="t2">${fmt(s)}${mins > 1 ? ` · ${mins} ${t.min || "min"}` : ""}${detail ? "\n" + detail : ""}</div></div>
        ${l !== null && l > 0 ? `<div class="lit">${this._fmt(l)} L</div>` : ""}</div>`;
    };
    const body = (next ? row(next, true) : "") + (past.length ? past.map((e) => row(e, false)).join("") : `<div class="empty">${t.noEvents}</div>`);
    return `<div class="tile chart" style="cursor:default"><div class="ctitle">${t.log}</div>${body}</div>`;
  }

  _points(rows) {
    return (rows || []).map((r) => ({
      t: r.lu !== undefined ? r.lu * 1000 : Date.parse(r.last_changed || r.last_updated),
      v: parseFloat(r.s !== undefined ? r.s : r.state),
    })).filter((p) => !isNaN(p.v) && !isNaN(p.t));
  }

  _bars(rows, t) {
    if (!rows.length) return `<div class="empty">${t.noData}</div>`;
    const W = 320, H = 150, top = 18, bottom = 18, max = Math.max(1, ...rows.map((r) => r.value));
    const bw = W / rows.length;
    return `<svg viewBox="0 0 ${W} ${H}">${rows.map((r, i) => {
      const h = (H - top - bottom) * (r.value / max);
      const w = bw * 0.5, x = i * bw + bw * 0.25, y = H - bottom - h, rad = Math.min(6, h, w / 2);
      const day = r.day.toLocaleDateString(this._lang(), { weekday: "short" });
      const bar = h > 0
        ? `<path d="M${x},${H - bottom} V${y + rad} q0,-${rad} ${rad},-${rad} h${w - 2 * rad} q${rad},0 ${rad},${rad} V${H - bottom} Z" fill="#0A84FF"/>
           <text class="lbl" x="${x + w / 2}" y="${y - 4}" text-anchor="middle">${this._fmt(r.value)} L</text>` : "";
      return `${bar}<text class="axis" x="${x + w / 2}" y="${H - 4}" text-anchor="middle">${day}</text>`;
    }).join("")}</svg>`;
  }

  _area(points, opts) {
    if (points.length < 1) return `<div class="empty">${opts.empty}</div>`;
    const W = 320, H = 120, pad = 4, t0 = opts.start, t1 = opts.end;
    const vals = points.map((p) => p.v);
    const min = opts.min !== undefined ? opts.min : Math.min(...vals) - 1;
    const max = opts.max !== undefined ? opts.max : Math.max(...vals) + 1;
    const span = max - min || 1;
    const x = (tt) => pad + (W - 2 * pad) * Math.max(0, Math.min(1, (tt - t0) / (t1 - t0)));
    const y = (v) => H - pad - (H - 2 * pad) * Math.max(0, Math.min(1, (v - min) / span));
    let d = `M${x(points[0].t)},${y(points[0].v)}`;
    for (let i = 1; i < points.length; i++) d += ` H${x(points[i].t)} V${y(points[i].v)}`;
    d += ` H${x(t1)}`;
    const area = `${d} V${H - pad} H${x(points[0].t)} Z`;
    const id = `g${Math.random().toString(36).slice(2, 8)}`;
    let paint = opts.color, defs = "";
    if (opts.thresholds) {
      // fasce colorate: dall'alto (valori alti) al basso
      const sorted = [...opts.thresholds].sort((a, b) => b[0] - a[0]);
      let prev = 0;
      const stops = sorted.map(([v, c]) => {
        const off = Math.max(0, Math.min(1, (max - v) / span));
        const s = `<stop offset="${prev}" stop-color="${c}"/><stop offset="${off}" stop-color="${c}"/>`;
        prev = off;
        return s;
      }).join("");
      defs = `<defs><linearGradient id="${id}" x1="0" y1="${pad}" x2="0" y2="${H - pad}" gradientUnits="userSpaceOnUse">${stops}</linearGradient></defs>`;
      paint = `url(#${id})`;
    }
    const grid = (opts.yLabels || []).map((v) => `<line x1="${pad}" x2="${W - pad}" y1="${y(v)}" y2="${y(v)}" stroke="var(--divider-color)" stroke-dasharray="3 3"/>
      <text class="axis" x="${W - 2}" y="${y(v) - 2}" text-anchor="end">${v}${opts.unit || ""}</text>`).join("");
    return `<svg viewBox="0 0 ${W} ${H}">${defs}${grid}
      <path d="${area}" fill="${paint}" opacity="${opts.fillOpacity !== undefined ? opts.fillOpacity : 0.25}"/>
      <path d="${d}" fill="none" stroke="${paint}" stroke-width="2" ${opts.dashed ? 'stroke-dasharray="4 3"' : ""}/></svg>`;
  }

  _render(map) {
    const t = this._t();
    const d = this._data || { water: [], soil: {}, outdoor: {} };
    const now = Date.now();
    const soil = map.zones.filter((z) => z.moisture).map((z) => {
      const cur = this._num(z.moisture);
      return `<div class="tile chart" style="cursor:default">
        <div class="ctitle">${t.soil} – ${z.name}${cur !== null ? ` · ${Math.round(cur)}%` : ""}</div>
        ${this._area(d.soil[z.moisture] || [], {
          start: now - 5 * 86400e3, end: now, min: 0, max: 100, empty: t.noData, unit: "%", yLabels: [25, 50],
          thresholds: [[0, "#f44336"], [25, "#4caf50"], [50, "#2196f3"]],
        })}</div>`;
    }).join("");
    let outdoor = "";
    if (map.temperature || map.humidity) {
      const tv = this._num(map.temperature), hv = this._num(map.humidity);
      const temp = map.temperature ? this._area(d.outdoor[map.temperature] || [], { start: now - 86400e3, end: now, color: "#ff9800", empty: t.noData }) : "";
      const hum = map.humidity ? this._area(d.outdoor[map.humidity] || [], { start: now - 86400e3, end: now, color: "#03a9f4", empty: "", min: 0, max: 100, fillOpacity: 0, dashed: true }) : "";
      outdoor = `<div class="tile chart" style="cursor:default">
        <div class="ctitle">${t.outdoor}${tv !== null ? ` · ${this._fmt(tv)} °C` : ""}${hv !== null ? ` · ${Math.round(hv)}%` : ""}</div>
        <div style="position:relative">${temp || hum}${temp && hum ? `<div style="position:absolute;inset:0">${hum}</div>` : ""}</div>
        <div class="legend">${map.temperature ? `<span><i style="background:#ff9800"></i>${t.temp}</span>` : ""}${map.humidity ? `<span><i style="background:repeating-linear-gradient(90deg,#03a9f4 0 4px,transparent 4px 7px)"></i>${t.hum} (0–100%)</span>` : ""}</div>
      </div>`;
    }
    const total = d.water.reduce((a, r) => a + r.value, 0);
    const lit = (id) => { const v = this._num(id); return v === null ? "–" : `${this._fmt(v)} L`; };
    const stats = `<div class="stats3">
      <div class="stat"><div class="k">${t.today}</div><div class="v">${lit(map.system.water_today)}</div></div>
      <div class="stat"><div class="k">${t.month}</div><div class="v">${lit(map.system.water_month)}</div></div>
      <div class="stat"><div class="k">${t.total}</div><div class="v">${lit(map.system.water_total)}</div></div></div>`;
    const bars = total ? this._bars(d.water, t) : `<div class="empty">${t.collecting}</div>`;
    const log = this._config.show_log === false ? "" : this._log(d.events, t);
    this.shadowRoot.innerHTML = `
      <style>${BASE_STYLE}${CHART_STYLE}</style>
      <ha-card><div class="grid">
        ${stats}
        <div class="tile chart" style="cursor:default">
          <div class="ctitle">${this._config.title || t.water7}${total ? ` · ${this._fmt(total)} L` : ""}</div>
          ${bars}</div>
        ${log}
        ${outdoor}
        ${soil}
      </div></ha-card>`;
  }
}

/* ------------------------------------------------------------------ */

/*
 * Umidità del terriccio di sensori a scelta (anche fuori dalle zone), con lo
 * stesso grafico della card dei grafici:
 *   type: custom:irrigazione-ai-moisture-card
 *   entities:
 *     - entity: sensor.rosmarino_umidita
 *       name: Rosmarino
 *   hours: 120        # facoltativo, ore mostrate (default 5 giorni)
 *   threshold: 25     # facoltativo, soglia "secco" (default quella dell'impianto, o 25)
 */
class IrrigazioneAiMoistureCard extends IrrigazioneAiChartsCard {
  static getStubConfig(hass) {
    const id = Object.keys(hass.states).find((e) => e.startsWith("sensor.")
      && hass.states[e].attributes.device_class === "moisture");
    return { entities: id ? [id] : [] };
  }

  setConfig(config) {
    if (!config || !Array.isArray(config.entities) || !config.entities.length) {
      throw new Error("entities: indica almeno un sensore di umidità del terriccio");
    }
    super.setConfig(config);
    this._items = config.entities.map((e) => (typeof e === "string" ? { entity: e } : e)).filter((e) => e.entity);
  }

  getCardSize() { return 3 * this._items.length; }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    const now = Date.now();
    const sig = this._signature(this._items.map((e) => e.entity));
    if (first || !this._loaded || now - this._loaded > 10 * 60 * 1000) {
      this._loaded = now;
      this._sig = sig;
      this._loadSoil();
    } else if (sig !== this._sig) {
      this._sig = sig;
      this._draw();
    }
  }

  _hours() { return Number(this._config.hours) > 0 ? Number(this._config.hours) : 120; }

  async _loadSoil() {
    const ids = this._items.map((e) => e.entity);
    const end = new Date();
    try {
      const h = await this._hass.callWS({
        type: "history/history_during_period", start_time: new Date(end - this._hours() * 3600e3).toISOString(),
        end_time: end.toISOString(), entity_ids: ids, minimal_response: true, no_attributes: true,
      });
      this._soil = Object.fromEntries(ids.map((id) => [id, this._points(h[id])]));
    } catch (e) { this._soil = {}; }
    this._draw();
  }

  _draw() {
    const t = this._t();
    const map = this._map();
    const dryAt = Number(this._config.threshold) > 0 ? Number(this._config.threshold)
      : (map && map.dry_threshold > 0 ? map.dry_threshold : 25);
    const now = Date.now();
    const charts = this._items.map((it) => {
      const st = this._s(it.entity);
      const name = it.name || (st && st.attributes.friendly_name) || it.entity;
      const cur = this._num(it.entity);
      return `<div class="tile chart" data-more="${it.entity}">
        <div class="ctitle">${this._config.prefix === false ? "" : `${t.soil} – `}${name}${cur !== null ? ` · ${Math.round(cur)}%` : ""}</div>
        ${this._area((this._soil || {})[it.entity] || [], {
          start: now - this._hours() * 3600e3, end: now, min: 0, max: 100, empty: t.noData, unit: "%",
          yLabels: [dryAt, 50], thresholds: [[0, "#f44336"], [dryAt, "#4caf50"], [50, "#2196f3"]],
        })}</div>`;
    }).join("");
    this.shadowRoot.innerHTML = `
      <style>${BASE_STYLE}${CHART_STYLE}</style>
      <ha-card><div class="grid">
        ${this._config.title ? `<div class="sec-title">${this._config.title}</div>` : ""}
        ${charts}
      </div></ha-card>`;
    this.shadowRoot.querySelectorAll("[data-more]").forEach((el) => el.addEventListener("click", () => {
      const ev = new Event("hass-more-info", { bubbles: true, composed: true });
      ev.detail = { entityId: el.dataset.more };
      this.dispatchEvent(ev);
    }));
  }
}

customElements.define("irrigazione-ai-card", IrrigazioneAiCard);
customElements.define("irrigazione-ai-charts-card", IrrigazioneAiChartsCard);
customElements.define("irrigazione-ai-moisture-card", IrrigazioneAiMoistureCard);
window.customCards = window.customCards || [];
window.customCards.push(
  { type: "irrigazione-ai-card", name: "Irrigazione AI", description: "Comandi dell'impianto: generale, AI, pioggia, zone, timer, programmazione per zona, durate.", preview: true },
  { type: "irrigazione-ai-moisture-card", name: "Irrigazione AI – Umidità terriccio", description: "Grafico dell'umidità del terriccio di sensori a scelta, con le fasce secco, ottimale e umido.", preview: true },
  { type: "irrigazione-ai-charts-card", name: "Irrigazione AI – Grafici e registro", description: "Litri di oggi, del mese e totali, consumo degli ultimi 7 giorni, registro delle irrigazioni, umidità del terriccio e meteo esterno.", preview: true },
);
console.info(`%c IRRIGAZIONE-AI-CARD %c ${CARD_VERSION} `, "background:#26a69a;color:#fff", "");
