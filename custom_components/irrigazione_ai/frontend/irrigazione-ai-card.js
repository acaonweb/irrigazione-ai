/*
 * Irrigazione AI — card Lovelace
 * Registrata automaticamente dall'integrazione. Uso:
 *   type: custom:irrigazione-ai-card
 *   entity: sensor.irrigazione_stato   # sensore Stato dell'impianto (facoltativo)
 */

const CARD_VERSION = "0.5.0";

const TEXT = {
  it: {
    idle: "Ferma", running: "In corso", blocked: "Bloccata",
    start: "Avvia", stop: "Ferma", next: "Prossima", remaining: "Rimanente",
    today: "Oggi", month: "Mese", planned: "Prevista", ai: "AI", ends: "fine",
    moisture: "Terriccio", noSensor: "senza sensore", analyze: "Analizza",
    decision: { irrigate: "L'AI irrigherebbe", skip: "L'AI salterebbe", error: "Errore AI" },
    frequency: "Frequenza", timer: "Timer", rain: "Blocco pioggia", aiSwitch: "Analisi AI",
    freq: { off: "Spenta", weekly: "1 volta/sett.", twice_weekly: "2 volte/sett.", daily: "Ogni giorno" },
    timerOff: "Formula", lastBlock: "Ultimo blocco", noEntity: "Nessun impianto Irrigazione AI trovato.",
    open: "Aperta", closed: "Chiusa", min: "min", skip: "salta",
  },
  en: {
    idle: "Idle", running: "Running", blocked: "Blocked",
    start: "Start", stop: "Stop", next: "Next", remaining: "Remaining",
    today: "Today", month: "Month", planned: "Planned", ai: "AI", ends: "ends",
    moisture: "Soil", noSensor: "no sensor", analyze: "Analyze",
    decision: { irrigate: "AI would water", skip: "AI would skip", error: "AI error" },
    frequency: "Frequency", timer: "Timer", rain: "Rain block", aiSwitch: "AI analysis",
    freq: { off: "Off", weekly: "Once a week", twice_weekly: "Twice a week", daily: "Every day" },
    timerOff: "Formula", lastBlock: "Last block", noEntity: "No Irrigazione AI system found.",
    open: "Open", closed: "Closed", min: "min", skip: "skip",
  },
};

const STYLE = `
  :host { --ia-accent: #26a69a; --ia-water: #1e88e5; --ia-warn: #ef6c00; --ia-dry: #e53935; }
  ha-card { padding: 16px; overflow: hidden; }
  .head { display: flex; align-items: center; gap: 12px; }
  .logo { width: 44px; height: 44px; border-radius: 14px; display: grid; place-items: center;
          background: color-mix(in srgb, var(--ia-accent) 18%, transparent); color: var(--ia-accent); }
  .logo.running { background: color-mix(in srgb, var(--ia-water) 22%, transparent); color: var(--ia-water);
                  animation: pulse 1.8s ease-in-out infinite; }
  .title { flex: 1; min-width: 0; }
  .title .name { font-size: 1.15em; font-weight: 600; }
  .pill { display: inline-block; margin-top: 2px; padding: 1px 10px; border-radius: 999px; font-size: .8em;
          background: var(--secondary-background-color); color: var(--secondary-text-color); }
  .pill.running { background: var(--ia-water); color: #fff; }
  .pill.blocked { background: var(--ia-warn); color: #fff; }
  .go { border: none; cursor: pointer; width: 52px; height: 52px; border-radius: 50%; display: grid;
        place-items: center; color: #fff; background: var(--ia-accent); box-shadow: 0 4px 14px rgba(0,0,0,.18);
        transition: transform .15s; }
  .go:active { transform: scale(.94); }
  .go.stop { background: var(--ia-dry); }
  .stats { display: flex; gap: 8px; margin: 14px 0 4px; flex-wrap: wrap; }
  .stat { flex: 1; min-width: 90px; padding: 8px 10px; border-radius: 12px; background: var(--secondary-background-color); }
  .stat .k { font-size: .75em; color: var(--secondary-text-color); }
  .stat .v { font-size: 1.05em; font-weight: 600; }
  .ai { display: flex; gap: 10px; align-items: flex-start; margin-top: 10px; padding: 10px 12px; border-radius: 12px;
        background: color-mix(in srgb, var(--ia-accent) 10%, transparent); }
  .ai .txt { flex: 1; font-size: .9em; }
  .ai .txt b { display: block; }
  .ai button { border: none; border-radius: 999px; padding: 6px 12px; cursor: pointer;
               background: var(--ia-accent); color: #fff; font: inherit; font-size: .85em; }
  .zones { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; margin-top: 14px; }
  .zone { position: relative; padding: 12px; border-radius: 16px; cursor: pointer; overflow: hidden;
          border: 1px solid var(--divider-color); transition: border-color .2s, box-shadow .2s; }
  .zone.on { border-color: var(--ia-water); box-shadow: 0 0 0 1px var(--ia-water), 0 6px 20px rgba(30,136,229,.25); }
  .zone .top { display: flex; align-items: center; gap: 8px; }
  .zone .top ha-icon { color: var(--secondary-text-color); }
  .zone.on .top ha-icon { color: var(--ia-water); animation: sway 1.2s ease-in-out infinite; }
  .zone .zn { font-weight: 600; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .bar { height: 6px; border-radius: 3px; background: var(--divider-color); margin: 10px 0 4px; overflow: hidden; }
  .bar > i { display: block; height: 100%; border-radius: 3px; transition: width .6s; }
  .meta { font-size: .78em; color: var(--secondary-text-color); display: flex; justify-content: space-between; gap: 6px; }
  .nums { display: flex; gap: 10px; margin-top: 8px; font-size: .85em; }
  .nums span b { font-weight: 600; }
  .end { margin-top: 6px; font-size: .8em; color: var(--ia-water); font-weight: 600; }
  .drops { position: absolute; inset: 0; pointer-events: none; }
  .drops i { position: absolute; top: -10px; width: 4px; height: 9px; border-radius: 50% 50% 50% 50% / 60% 60% 40% 40%;
             background: var(--ia-water); opacity: .35; animation: fall 1.6s linear infinite; }
  .controls { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
  .chip { display: flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 999px; cursor: pointer;
          border: 1px solid var(--divider-color); font-size: .85em; background: none; color: inherit; font: inherit; }
  .chip.on { background: color-mix(in srgb, var(--ia-accent) 16%, transparent); border-color: var(--ia-accent); }
  .chip select { border: none; background: none; color: inherit; font: inherit; cursor: pointer; }
  .warn { padding: 16px; color: var(--secondary-text-color); }
  @keyframes pulse { 0%,100% { transform: scale(1); } 50% { transform: scale(1.07); } }
  @keyframes sway { 0%,100% { transform: rotate(0); } 25% { transform: rotate(10deg); } 75% { transform: rotate(-10deg); } }
  @keyframes fall { to { transform: translateY(190px); } }
`;

class IrrigazioneAiCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._sig = null;
  }

  static getStubConfig(hass) {
    const id = Object.keys(hass.states).find(
      (e) => e.startsWith("sensor.") && hass.states[e].attributes && hass.states[e].attributes.card
    );
    return id ? { entity: id } : {};
  }

  getCardSize() { return 6; }

  set hass(hass) {
    this._hass = hass;
    const status = this._statusEntity();
    const card = status && hass.states[status] ? hass.states[status].attributes.card : null;
    const ids = [status];
    if (card) {
      Object.values(card.system).forEach((e) => e && ids.push(e));
      card.zones.forEach((z) => Object.values(z).forEach((e) => typeof e === "string" && e.includes(".") && ids.push(e)));
    }
    const sig = ids.map((e) => (hass.states[e] ? hass.states[e].last_updated + hass.states[e].state : "-")).join("|")
      + (hass.language || "");
    if (sig === this._sig) return;
    this._sig = sig;
    this._render();
  }

  _statusEntity() {
    if (this._config && this._config.entity) return this._config.entity;
    const h = this._hass;
    return Object.keys(h.states).find(
      (e) => e.startsWith("sensor.") && h.states[e].attributes && h.states[e].attributes.card
    );
  }

  _t() { return (this._hass.language || "en").startsWith("it") ? TEXT.it : TEXT.en; }
  _s(id) { return id ? this._hass.states[id] : undefined; }
  _num(id) { const s = this._s(id); const n = s ? parseFloat(s.state) : NaN; return isNaN(n) ? null : n; }

  _time(iso, withDay) {
    if (!iso || iso === "unknown" || iso === "unavailable") return "–";
    const d = new Date(iso);
    if (isNaN(d)) return "–";
    const opts = withDay ? { weekday: "short", hour: "2-digit", minute: "2-digit" } : { hour: "2-digit", minute: "2-digit" };
    return d.toLocaleString(this._hass.language || undefined, opts);
  }

  _liters(v) { return v === null ? "–" : `${v.toLocaleString(this._hass.language || undefined, { maximumFractionDigits: 1 })} L`; }

  _moistureColor(v) {
    if (v === null) return "var(--divider-color)";
    if (v < 25) return "var(--ia-dry)";
    if (v <= 50) return "#43a047";
    return "var(--ia-water)";
  }

  _call(domain, service, data) { this._hass.callService(domain, service, data); }

  _render() {
    const root = this.shadowRoot;
    const t = this._t();
    const statusId = this._statusEntity();
    const status = this._s(statusId);
    if (!status || !status.attributes.card) {
      root.innerHTML = `<style>${STYLE}</style><ha-card><div class="warn">${t.noEntity}</div></ha-card>`;
      return;
    }
    const map = status.attributes.card;
    const sys = map.system;
    const state = status.state;
    const running = state === "running";
    const name = this._config.title
      || (this._s(sys.irrigation) && this._s(sys.irrigation).attributes.friendly_name)
      || "Irrigazione";

    const remaining = this._num(sys.remaining);
    const today = this._num(sys.water_today);
    const month = this._num(sys.water_month);
    const next = this._s(sys.next_run);

    const zonesHtml = map.zones.map((z, i) => {
      const valve = this._s(z.valve);
      const on = valve && ["on", "open", "opening"].includes(valve.state);
      const moist = this._num(z.moisture);
      const planned = this._num(z.duration);
      const ai = map.ai ? this._num(z.ai) : null;
      const water = this._num(z.water_today);
      const end = this._s(z.end);
      const drops = on
        ? `<div class="drops">${[8, 26, 44, 62, 80].map((x, k) => `<i style="left:${x}%;animation-delay:${k * 0.3}s"></i>`).join("")}</div>`
        : "";
      return `
        <div class="zone ${on ? "on" : ""}" data-valve="${z.valve}" title="${on ? t.open : t.closed}">
          ${drops}
          <div class="top"><ha-icon icon="mdi:sprinkler-variant"></ha-icon><div class="zn">${i + 1}. ${z.name}</div></div>
          <div class="bar"><i style="width:${moist === null ? 0 : Math.min(100, moist)}%;background:${this._moistureColor(moist)}"></i></div>
          <div class="meta"><span>${t.moisture}</span><span>${moist === null ? t.noSensor : Math.round(moist) + "%"}</span></div>
          <div class="nums">
            <span>${t.planned} <b>${planned === null ? "–" : planned + " " + t.min}</b></span>
            ${ai !== null ? `<span>${t.ai} <b>${ai === 0 ? t.skip : ai + " " + t.min}</b></span>` : ""}
          </div>
          <div class="nums"><span>${t.today} <b>${this._liters(water)}</b></span></div>
          ${on && end && end.state !== "unknown" && end.state !== "unavailable" ? `<div class="end">${t.ends} ${this._time(end.state)}</div>` : ""}
        </div>`;
    }).join("");

    let aiHtml = "";
    const decision = map.ai ? this._s(sys.ai_decision) : null;
    if (decision) {
      const label = t.decision[decision.state] || "–";
      const reason = decision.attributes.reason || decision.attributes.error || "";
      aiHtml = `
        <div class="ai">
          <ha-icon icon="mdi:robot-outline"></ha-icon>
          <div class="txt"><b>${decision.state === "unknown" ? t.aiSwitch : label}</b>${reason}</div>
          <button data-press="${sys.analyze}">${t.analyze}</button>
        </div>`;
    }

    const freq = this._s(sys.frequency);
    const timer = this._s(sys.manual_timer);
    const rain = this._s(sys.rain_block);
    const aiSw = map.ai ? this._s(sys.ai_analysis) : null;
    const freqOpts = freq ? freq.attributes.options.map(
      (o) => `<option value="${o}" ${o === freq.state ? "selected" : ""}>${t.freq[o] || o}</option>`).join("") : "";
    const timerOpts = timer ? timer.attributes.options.map(
      (o) => `<option value="${o}" ${o === timer.state ? "selected" : ""}>${o === "off" ? t.timerOff : o + " " + t.min}</option>`).join("") : "";

    root.innerHTML = `
      <style>${STYLE}</style>
      <ha-card>
        <div class="head">
          <div class="logo ${running ? "running" : ""}"><ha-icon icon="mdi:${running ? "sprinkler-variant" : "water-outline"}"></ha-icon></div>
          <div class="title"><div class="name">${name}</div><span class="pill ${state}">${t[state] || state}</span></div>
          <button class="go ${running ? "stop" : ""}" data-toggle="${sys.irrigation}" title="${running ? t.stop : t.start}">
            <ha-icon icon="mdi:${running ? "stop" : "play"}"></ha-icon>
          </button>
        </div>
        <div class="stats">
          ${running
            ? `<div class="stat"><div class="k">${t.remaining}</div><div class="v">${remaining === null ? "–" : remaining + " " + t.min}</div></div>`
            : `<div class="stat"><div class="k">${t.next}</div><div class="v">${next ? this._time(next.state, true) : "–"}</div></div>`}
          <div class="stat"><div class="k">${t.today}</div><div class="v">${this._liters(today)}</div></div>
          <div class="stat"><div class="k">${t.month}</div><div class="v">${this._liters(month)}</div></div>
        </div>
        ${aiHtml}
        <div class="zones">${zonesHtml}</div>
        <div class="controls">
          ${freq ? `<label class="chip"><ha-icon icon="mdi:calendar-week"></ha-icon><select data-select="${sys.frequency}">${freqOpts}</select></label>` : ""}
          ${timer ? `<label class="chip ${timer.state !== "off" ? "on" : ""}"><ha-icon icon="mdi:timer-outline"></ha-icon><select data-select="${sys.manual_timer}">${timerOpts}</select></label>` : ""}
          ${rain ? `<button class="chip ${rain.state === "on" ? "on" : ""}" data-toggle="${sys.rain_block}"><ha-icon icon="mdi:weather-rainy"></ha-icon>${t.rain}</button>` : ""}
          ${aiSw && aiSw.state !== "unavailable" ? `<button class="chip ${aiSw.state === "on" ? "on" : ""}" data-toggle="${sys.ai_analysis}"><ha-icon icon="mdi:robot-outline"></ha-icon>${t.aiSwitch}</button>` : ""}
        </div>
      </ha-card>`;

    root.querySelectorAll("[data-toggle]").forEach((el) =>
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        this._call("switch", "toggle", { entity_id: el.dataset.toggle });
      }));
    root.querySelectorAll("[data-press]").forEach((el) =>
      el.addEventListener("click", () => this._call("button", "press", { entity_id: el.dataset.press })));
    root.querySelectorAll("[data-select]").forEach((el) =>
      el.addEventListener("change", () =>
        this._call("select", "select_option", { entity_id: el.dataset.select, option: el.value })));
    root.querySelectorAll(".zone").forEach((el) =>
      el.addEventListener("click", () => {
        const valve = el.dataset.valve;
        const domain = valve.split(".")[0];
        const on = el.classList.contains("on");
        if (domain === "valve") this._call("valve", on ? "close_valve" : "open_valve", { entity_id: valve });
        else this._call("homeassistant", on ? "turn_off" : "turn_on", { entity_id: valve });
      }));
  }
}

customElements.define("irrigazione-ai-card", IrrigazioneAiCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "irrigazione-ai-card",
  name: "Irrigazione AI",
  description: "Stato, zone, consumi e comandi dell'impianto Irrigazione AI.",
  preview: true,
});
console.info(`%c IRRIGAZIONE-AI-CARD %c ${CARD_VERSION} `, "background:#26a69a;color:#fff", "");
