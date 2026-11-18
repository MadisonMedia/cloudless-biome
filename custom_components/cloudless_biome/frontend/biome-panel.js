// The Biome page in the sidebar: set up profiles and devices on a timeline you can drag, see what runs now,
// measurements and energy, notes, the biome's settings and the log.

const version = new URL(import.meta.url).search;
const load = (file) => import(new URL(`./${file}${version}`, import.meta.url).href);
const [shared, model, insightsModule] = await Promise.all([load("biome-shared.js"), load("biome-model.js"), load("biome-insights.js")]);
const { KINDS, actualText, esc, fmtDate, fmtWhen, icon, isDark, kindOf, logText, problemText, statusText, tr } = shared;
const { DAY, SNAP, clock, clone, daySpan, dayTimes, guessKind, hours, limitOf, naturalOf, pct, pieces, settingOf, signed, snap, toMin, windowsOf } = model;
const { INSIGHTS_STYLE, Insights } = insightsModule;

const SETTINGS = "/config/integrations/integration/cloudless_biome";
const MENU_ICON = '<svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M3 6h18v2H3zm0 5h18v2H3zm0 5h18v2H3z"/></svg>';
const DRAG_ICON =
  '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="9" cy="6" r="1.6"/><circle cx="15" cy="6" r="1.6"/><circle cx="9" cy="12" r="1.6"/><circle cx="15" cy="12" r="1.6"/><circle cx="9" cy="18" r="1.6"/><circle cx="15" cy="18" r="1.6"/></svg>';
const MONTHS = {
  en: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
  de: ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"],
};

const STYLE = `
:host { display: block; min-height: 100%; background: var(--primary-background-color, #eef1f5); color: var(--bio-ink); font: 400 15px/1.45 var(--ha-font-family-body, system-ui, sans-serif);
  --bio-ink: var(--primary-text-color, #172119); --bio-muted: var(--secondary-text-color, #55625a); --bio-surface: var(--card-background-color, #fff); --bio-line: var(--divider-color, #d5ddd7);
  --bio-accent: #2f8a57; --bio-accent-ink: #fff; --bio-accent-soft: color-mix(in srgb, var(--bio-accent) 14%, transparent);
  --bio-sun: #f2b632; --bio-day: color-mix(in srgb, #f5c84c 22%, transparent); --bio-night: color-mix(in srgb, var(--bio-ink) 7%, var(--bio-surface));
  --bio-warn: #8a5300; --bio-warn-soft: #fbeed6; --bio-info: #1d5b8f; --bio-info-soft: #e1eefa; }
:host([dark]) { --bio-accent: #5cc58a; --bio-accent-ink: #0d2116; --bio-warn: #f0bd6a; --bio-warn-soft: #3a2b12; --bio-info: #8fc3f0; --bio-info-soft: #14283b;
  --bio-day: color-mix(in srgb, #f5c84c 14%, transparent); }
* { box-sizing: border-box; }
[hidden] { display: none !important; }
h1, h2, h3, p { margin: 0; }
button, select, input, textarea { font: inherit; color: inherit; }
button { cursor: pointer; }
a { color: var(--bio-accent); }
:focus-visible { outline: 2px solid var(--bio-accent); outline-offset: 2px; }
.shell { max-width: 1180px; margin: 0 auto; padding-block: 14px 110px; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); display: grid; gap: 14px; }
.top { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; }
.menu { border: 0; background: transparent; width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center; padding: 0; }
.mark { display: flex; align-items: center; gap: 8px; font-size: 22px; font-weight: 750; letter-spacing: -.01em; }
.mark ha-icon { color: var(--bio-accent); }
.tabs { display: inline-flex; flex-wrap: wrap; gap: 2px; padding: 3px; background: var(--bio-night); border-radius: 10px; }
.tabs button { border: 0; background: transparent; padding: 5px 12px; border-radius: 8px; color: var(--bio-muted); font-weight: 500; display: inline-flex; align-items: center; gap: 6px; }
.tabs button[aria-selected="true"] { background: var(--bio-surface); color: var(--bio-ink); font-weight: 600; box-shadow: 0 1px 2px rgba(0,0,0,.08); }
.tabs .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--bio-accent); }
.spacer { flex: 1; }
.link { display: inline-flex; align-items: center; gap: 6px; text-decoration: none; font-weight: 550; padding: 6px 10px; border-radius: 8px; font-size: 14px; }
.link:hover { background: var(--bio-accent-soft); }
.card { background: var(--bio-surface); border: 1px solid var(--bio-line); border-radius: 14px; padding: 18px; display: grid; gap: 14px; min-width: 0; }
.card h2 { font-size: 17px; font-weight: 700; }
.card h3 { font-size: 15px; font-weight: 650; }
.hrow { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; }
.banner { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 14px; padding: 12px 16px; border-radius: 12px; }
.banner.info { background: var(--bio-info-soft); color: var(--bio-info); }
.banner.warn { background: var(--bio-warn-soft); color: var(--bio-warn); }
.banner p { flex: 1 1 260px; }
.btn { border: 1px solid var(--bio-line); background: var(--bio-surface); color: var(--bio-ink); border-radius: 9px; padding: 6px 12px; font-weight: 550; display: inline-flex; align-items: center; gap: 6px; }
.btn:hover { border-color: var(--bio-accent); }
.btn.primary { background: var(--bio-accent); border-color: var(--bio-accent); color: var(--bio-accent-ink); }
.btn.danger { color: var(--bio-warn); }
.btn.small { padding: 2px 8px; font-size: 12.5px; border-radius: 7px; }
.btn[disabled] { opacity: .5; cursor: default; }
.facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }
.fact { display: flex; gap: 10px; align-items: center; padding: 10px 12px; border-radius: 12px; background: var(--bio-night); min-width: 0; }
.fact ha-icon { color: var(--bio-muted); flex: none; }
.fact > div { display: grid; min-width: 0; }
.fact small { color: var(--bio-muted); font-size: 12.5px; }
.fact span, .fact select { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.fact select { border: 0; background: transparent; padding: 0; max-width: 100%; }
.toggles { display: flex; flex-wrap: wrap; gap: 8px; }
.toggle { display: inline-flex; align-items: center; gap: 8px; border: 1px solid var(--bio-line); background: var(--bio-surface); border-radius: 999px; padding: 5px 12px 5px 6px; font-weight: 550; }
.toggle .knob { width: 30px; height: 18px; border-radius: 9px; background: var(--bio-line); position: relative; transition: background .15s; }
.toggle .knob::after { content: ""; position: absolute; top: 2px; left: 2px; width: 14px; height: 14px; border-radius: 50%; background: #fff; transition: left .15s; box-shadow: 0 1px 2px rgba(0,0,0,.25); }
.toggle[aria-pressed="true"] .knob { background: var(--bio-accent); }
.toggle[aria-pressed="true"] .knob::after { left: 14px; }
.muted { color: var(--bio-muted); font-size: 13px; }
.section { display: flex; align-items: center; gap: 10px; margin: 10px 0 2px; font-size: 12.5px; font-weight: 650; letter-spacing: .04em; text-transform: uppercase; color: var(--bio-muted); }
.section::after { content: ""; flex: 1; height: 1px; background: var(--bio-line); }

/* timeline */
.tl { display: grid; gap: 4px; container-type: inline-size; }
.row { display: grid; grid-template-columns: minmax(150px, 230px) minmax(0, 1fr); gap: 4px 14px; align-items: center; padding: 4px 0; }
.row.open { background: var(--bio-accent-soft); border-radius: 10px; margin: 0 -8px; padding: 4px 8px; }
.row.moving { opacity: .6; }
.dayblock { background: color-mix(in srgb, var(--bio-sun) 9%, transparent); border: 1px solid color-mix(in srgb, var(--bio-sun) 35%, transparent); border-radius: 12px; padding: 6px 10px; margin: 0 -10px; }
.axis { display: grid; grid-template-columns: minmax(150px, 230px) minmax(0, 1fr); gap: 14px; }
.ticks { position: relative; height: 18px; }
.tick { position: absolute; transform: translateX(-50%); font-size: 11.5px; color: var(--bio-muted); font-variant-numeric: tabular-nums; }
.tick.first { transform: none; } .tick.last { transform: translateX(-100%); }
.lcell { display: flex; align-items: flex-start; gap: 4px; min-width: 0; }
.lcell > div { min-width: 0; flex: 1; }
.handle { flex: none; width: 22px; height: 34px; display: grid; place-items: center; color: var(--bio-muted); cursor: grab; touch-action: none; border-radius: 6px; margin-right: -6px; }
.handle:hover { background: var(--bio-night); color: var(--bio-ink); }
.label { display: flex; align-items: center; gap: 10px; min-width: 0; border: 0; background: transparent; padding: 2px; text-align: left; border-radius: 8px; width: 100%; }
button.label:hover .name { text-decoration: underline; }
.kicon { flex: none; width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; }
.ltext { min-width: 0; display: grid; }
.name { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sub { font-size: 12.5px; color: var(--bio-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-variant-numeric: tabular-nums; }
.track { position: relative; height: 34px; border-radius: 8px; background: var(--bio-night); overflow: hidden; }
.track.inactive { background: repeating-linear-gradient(135deg, var(--bio-night) 0 6px, transparent 6px 12px); display: grid; place-items: center; font-size: 12.5px; color: var(--bio-muted); cursor: pointer; }
.dayband { position: absolute; top: 0; bottom: 0; background: var(--bio-day); pointer-events: none; }
.gridline { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--bio-line); opacity: .7; pointer-events: none; }
.bar { position: absolute; top: 5px; bottom: 5px; border-radius: 6px; cursor: grab; touch-action: none; }
.bar.sun { top: 4px; bottom: 4px; background: var(--bio-sun); }
.bar.fixed { cursor: default; }
.bar.drag { cursor: grabbing; box-shadow: 0 0 0 2px var(--bio-ink); }
.bar.pulsed { overflow: hidden; }
.pulse { position: absolute; top: 0; bottom: 0; min-width: 2px; border-radius: 1px; pointer-events: none; }
.grip { position: absolute; top: 0; bottom: 0; width: 12px; cursor: ew-resize; touch-action: none; z-index: 1; }
.grip::after { content: ""; position: absolute; top: 25%; bottom: 25%; left: 4px; width: 4px; border-radius: 2px; background: rgba(255,255,255,.85); box-shadow: 0 0 0 1px rgba(0,0,0,.15); }
.grip.start { left: 0; } .grip.end { right: 0; }
.now { position: absolute; top: 0; bottom: 0; width: 2px; margin-left: -1px; background: var(--bio-ink); pointer-events: none; opacity: .8; }
.manual { position: absolute; top: 2px; bottom: 2px; border-radius: 6px; border: 2px dashed color-mix(in srgb, var(--bio-ink) 55%, transparent); pointer-events: none; }
.tip { position: absolute; top: 50%; transform: translate(-50%, -50%); padding: 2px 8px; border-radius: 6px; background: var(--bio-ink); color: var(--bio-surface); font-size: 12.5px; font-weight: 600; white-space: nowrap; pointer-events: none; font-variant-numeric: tabular-nums; z-index: 2; }
.extra { display: flex; flex-wrap: wrap; align-items: center; gap: 2px 10px; padding-left: 46px; }
.state { display: inline-flex; align-items: center; gap: 4px; font-size: 12.5px; }
.state::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--bio-line); }
.state.on::before { background: var(--bio-accent); }
.state.bad { color: var(--bio-warn); } .state.bad::before { background: var(--bio-warn); }
.problem { font-size: 12.5px; color: var(--bio-warn); font-weight: 550; }
.livetext { font-size: 12.5px; color: var(--bio-muted); }
.legend { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 12.5px; color: var(--bio-muted); }
@container (max-width: 600px) {
  .row, .axis { grid-template-columns: minmax(0, 1fr); }
  .axis > :first-child { display: none; }
}

/* forms */
.form { grid-column: 1 / -1; display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 12px 16px; padding: 12px 4px 8px; }
.form label { display: grid; gap: 4px; font-size: 13px; color: var(--bio-muted); font-weight: 500; align-content: start; }
.form input, .form select { border: 1px solid var(--bio-line); border-radius: 8px; padding: 6px 9px; background: var(--bio-surface); color: var(--bio-ink); font-size: 15px; min-width: 0; width: 100%; }
.form input[type="checkbox"] { width: 18px; height: 18px; accent-color: var(--bio-accent); }
.form .check { display: flex; align-items: center; gap: 8px; color: var(--bio-ink); font-size: 15px; align-self: center; }
.form .hint { font-size: 12px; color: var(--bio-muted); font-weight: 400; }
.form .warnhint { font-size: 12px; color: var(--bio-warn); font-weight: 550; }
.form .actions { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 8px; }
.form .pair { display: flex; gap: 6px; }
.form .wide { grid-column: 1 / -1; }
.form .section { grid-column: 1 / -1; }
.spanbox { grid-column: 1 / -1; display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 10px 14px; border: 1px solid var(--bio-line); border-radius: 10px; padding: 10px 12px; background: var(--bio-surface); }
.spanbox .shead { grid-column: 1 / -1; display: flex; align-items: center; gap: 8px; font-weight: 650; font-size: 14px; color: var(--bio-ink); }
.profileform { border-top: 1px solid var(--bio-line); border-bottom: 1px solid var(--bio-line); }
.chiplist { display: flex; flex-wrap: wrap; gap: 6px; }
.chiplist span { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--bio-line); border-radius: 999px; padding: 3px 4px 3px 10px; font-size: 13.5px; color: var(--bio-ink); }
.chiplist button { border: 0; background: transparent; width: 22px; height: 22px; border-radius: 50%; color: var(--bio-muted); padding: 0; }
.chiplist button:hover { background: var(--bio-night); color: var(--bio-ink); }

/* picker */
.pick .filters { display: flex; flex-wrap: wrap; gap: 8px; }
.pick input[type="search"], .pick select { border: 1px solid var(--bio-line); border-radius: 9px; padding: 7px 10px; background: var(--bio-surface); color: var(--bio-ink); }
.pick input[type="search"] { flex: 1 1 220px; min-width: 0; }
.pick select { flex: 0 1 220px; min-width: 0; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.chip { border: 1px solid var(--bio-line); background: transparent; color: var(--bio-muted); border-radius: 999px; padding: 4px 11px; font-size: 13px; }
.chip:hover { color: var(--bio-ink); border-color: var(--bio-accent); }
.chip[aria-pressed="true"] { background: var(--bio-accent); border-color: var(--bio-accent); color: var(--bio-accent-ink); font-weight: 600; }
.picklist { display: grid; gap: 2px; max-height: 380px; overflow: auto; border: 1px solid var(--bio-line); border-radius: 10px; padding: 4px; }
.picklist button { display: flex; align-items: center; gap: 10px; padding: 7px 8px; border-radius: 8px; border: 0; background: transparent; text-align: left; width: 100%; }
.picklist button:hover { background: var(--bio-night); }
.picklist button ha-icon { color: var(--bio-muted); flex: none; }
.pmain { display: grid; min-width: 0; flex: 1; }
.pname { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pmeta { font-size: 12.5px; color: var(--bio-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.padd { flex: none; font-size: 13px; font-weight: 600; color: var(--bio-accent); }

/* notes, log, empty */
.notes textarea { width: 100%; min-height: 200px; resize: vertical; border: 1px solid var(--bio-line); border-radius: 10px; padding: 10px 12px; background: var(--bio-surface); color: var(--bio-ink); line-height: 1.5; }
.log { display: grid; max-height: 320px; overflow: auto; }
.log div { display: grid; grid-template-columns: 92px minmax(0, 1fr); gap: 10px; padding: 6px 0; border-bottom: 1px solid var(--bio-line); font-size: 14px; }
.log div:last-child { border-bottom: 0; }
.log time { color: var(--bio-muted); font-variant-numeric: tabular-nums; }
.log .dry { color: var(--bio-info); }
.log .routine { color: var(--bio-muted); }
.pulses { display: grid; gap: 4px; padding: 8px 10px; border-radius: 10px; background: var(--bio-night); font-size: 13.5px; }
.pulses span { color: var(--bio-muted); }
.logtools { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; }
.logtools select { border: 1px solid var(--bio-line); border-radius: 8px; padding: 4px 8px; background: var(--bio-surface); color: var(--bio-ink); }
.logtools label { display: inline-flex; align-items: center; gap: 6px; font-size: 13.5px; }
.btn.switch { padding: 1px 8px; font-size: 12.5px; border-radius: 7px; }
.empty { text-align: center; padding: 30px 16px; color: var(--bio-muted); display: grid; gap: 10px; justify-items: center; }
.empty ha-icon { color: var(--bio-accent); }
.fold { border: 0; background: transparent; display: flex; align-items: center; gap: 8px; padding: 0; font-size: 17px; font-weight: 700; }

/* save bar */
.savebar { position: fixed; left: 50%; transform: translateX(-50%); bottom: calc(14px + env(safe-area-inset-bottom, 0px)); z-index: 5; display: flex; flex-wrap: wrap; align-items: center; gap: 10px 14px; padding: 10px 12px 10px 18px; border-radius: 14px; background: var(--bio-ink); color: var(--bio-surface); box-shadow: 0 6px 24px rgba(0,0,0,.25); max-width: calc(100% - 32px); }
.savebar .btn { background: transparent; color: var(--bio-surface); border-color: color-mix(in srgb, var(--bio-surface) 40%, transparent); }
.savebar .btn.primary { background: var(--bio-accent); border-color: var(--bio-accent); color: var(--bio-accent-ink); }
${INSIGHTS_STYLE}
`;

class BiomePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._biomes = [];
    this._i = 0;
    this._snap = null;
    this._draft = null;
    this._dirty = false;
    this._sel = null;
    this._open = null;
    this._profileForm = false;
    this._pick = null; // {kind: "device" | "sensor", query, room, cat}
    this._drag = null;
    this._saving = false;
    this._error = null;
    this._settingsOpen = false;
    this._logAll = false;
    this._logItems = null;
    this._logDevice = "";
    this._logPulses = true;
    this._units = new Map();
    this.insights = new Insights(this);
    const r = this.shadowRoot;
    r.addEventListener("click", (e) => this._onClick(e));
    r.addEventListener("dblclick", (e) => this._onDblClick(e));
    r.addEventListener("change", (e) => this._onChange(e));
    r.addEventListener("input", (e) => this._onInput(e));
    r.addEventListener("pointerdown", (e) => this._onDown(e));
    this._move = (e) => this._onMove(e);
    this._up = () => this._onUp();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    const dark = isDark(this.isConnected ? this : null, hass);
    if (dark !== this._dark) {
      this._dark = dark;
      this.toggleAttribute("dark", dark);
    }
    if (first) this._load();
  }

  set narrow(v) {
    this._narrow = v;
    const m = this.shadowRoot.querySelector(".menu");
    if (m) m.hidden = !v;
  }

  set panel(_v) {}
  set route(_v) {}

  connectedCallback() {
    for (const name of ["hass", "narrow", "panel", "route"]) {
      if (Object.hasOwn(this, name)) {
        const value = this[name];
        delete this[name];
        this[name] = value;
      }
    }
    this._timer = setInterval(() => {
      this._moveNow();
      this.insights.refresh();
    }, 30000);
    if (this._hass && this._biomes.length && !this._unsub) this._subscribe();
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    this._unsubscribe();
  }

  get _t() {
    return tr(this._hass);
  }

  get _lang() {
    return (this._hass?.locale?.language || this._hass?.language || "en").startsWith("de") ? "de" : "en";
  }

  get _b() {
    return this._biomes[this._i];
  }

  _profile(id = this._sel) {
    return this._draft?.profiles.find((p) => p.id === id) || null;
  }

  _device(id) {
    return this._draft?.devices.find((d) => d.id === id) || null;
  }

  _live(id) {
    return this._snap?.devices?.find((d) => d.id === id) || null;
  }

  // Today in the biome's time zone, as {y, m, d}.
  get _today() {
    const iso = (this._snap?.range?.[0] || new Date().toISOString()).slice(0, 10);
    const [y, m, d] = iso.split("-").map(Number);
    return { y, m, d };
  }

  _times(profile, day = this._today) {
    return dayTimes(profile, day, this._draft?.settings, this._snap);
  }

  // -- loading ----------------------------------------------------------------------------------------

  async _load() {
    try {
      this._biomes = await this._hass.callWS({ type: "cloudless_biome/biomes" });
    } catch (err) {
      this._biomes = [];
      this._error = err?.message || String(err);
    }
    this._i = Math.min(this._i, Math.max(0, this._biomes.length - 1));
    this._render();
    this._subscribe();
  }

  async _subscribe(tries = 0) {
    this._unsubscribe();
    const b = this._b;
    if (!b) return;
    try {
      this._unsub = await this._hass.connection.subscribeMessage((msg) => this._onSnap(msg), { type: "cloudless_biome/subscribe", entry_id: b.entry_id });
    } catch (err) {
      // Right after saving, the biome may still be starting.
      if (tries < 10) setTimeout(() => this._subscribe(tries + 1), 700);
      else {
        this._error = err?.message || String(err);
        this._render();
      }
    }
  }

  _unsubscribe() {
    if (this._unsub) {
      const unsub = this._unsub;
      this._unsub = null;
      Promise.resolve(unsub)
        .then((f) => typeof f === "function" && f())
        .catch(() => {});
    }
  }

  _onSnap(msg) {
    if (msg.reload) {
      this._unsubscribe();
      setTimeout(() => this._subscribe(), 500);
      return;
    }
    const first = !this._snap;
    this._snap = msg;
    if (!this._dirty || !this._draft) this._draft = clone(msg.config);
    if (!this._profile()) this._sel = msg.profile?.id || this._draft.profiles[0]?.id || null;
    if (!this._drag) this._render();
    if (first) this.insights.refresh(true);
  }

  _change() {
    this._dirty = true;
    this._render();
  }

  async _save() {
    if (!this._b || this._saving) return;
    this._saving = true;
    this._render();
    try {
      await this._hass.callWS({ type: "cloudless_biome/save", entry_id: this._b.entry_id, config: this._draft });
      this._dirty = false;
      this._error = null;
      this._open = null;
      this._profileForm = false;
    } catch (err) {
      this._error = err?.message || String(err);
    }
    this._saving = false;
    this._render();
    this.insights.refresh(true);
  }

  _discard() {
    this._dirty = false;
    this._draft = clone(this._snap.config);
    if (!this._profile()) this._sel = this._snap.profile?.id || this._draft.profiles[0]?.id;
    this._open = null;
    this._profileForm = false;
    this._render();
  }

  async _control(action, value, device) {
    if (!this._b) return;
    try {
      await this._hass.callWS({ type: "cloudless_biome/control", entry_id: this._b.entry_id, action, value, ...(device ? { device } : {}) });
      this._error = null;
    } catch (err) {
      this._error = err?.message || String(err);
      this._render();
    }
  }

  // The device's own setting for a profile, created from what it inherits when needed.
  _ensure(device, profile) {
    device.profiles = device.profiles || {};
    if (!device.profiles[profile.id]) device.profiles[profile.id] = settingOf(this._draft, device, profile);
    const s = device.profiles[profile.id];
    s.spans = s.spans || [daySpan()];
    return s;
  }

  // -- events -----------------------------------------------------------------------------------------

  _onClick(e) {
    const el = e.target.closest("[data-act]");
    if (!el || this._suppressClick) return;
    const act = el.dataset.act;
    const s = this._snap;
    switch (act) {
      case "menu":
        this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
        break;
      case "biome":
        if (this._dirty) return;
        this._i = Number(el.dataset.i);
        this._snap = this._draft = null;
        this._sel = this._open = null;
        this._render();
        this._subscribe();
        break;
      case "pause":
        this._control("pause", !s?.paused);
        break;
      case "dry-run":
        this._control("dry_run", !s?.dry_run);
        break;
      case "resume":
        this._control("resume", null, el.dataset.device);
        break;
      case "edit-profile":
        if (el.dataset.id === this._sel) this._profileForm = !this._profileForm;
        else {
          this._sel = el.dataset.id;
          this._profileForm = false;
        }
        this._render();
        break;
      case "add-profile": {
        const base = this._profile();
        const id = `new-${Date.now()}`;
        this._draft.profiles.push({
          id,
          name: this._t("New profile", "Neues Profil"),
          day_start: base?.day_start || "08:00",
          day_end: base?.day_end || "20:00",
          day_mode: base?.day_mode || "fixed",
          start_event: "date",
          start_date: null,
          start_offset: 0,
          transition: 0,
          copy_from: base?.id || null,
        });
        this._sel = id;
        this._profileForm = true;
        this._change();
        break;
      }
      case "remove-profile": {
        if (this._draft.profiles.length < 2) return;
        const id = this._sel;
        this._draft.profiles = this._draft.profiles.filter((p) => p.id !== id);
        for (const p of this._draft.profiles) if (p.copy_from === id) p.copy_from = null;
        for (const d of this._draft.devices) delete d.profiles?.[id];
        this._sel = this._draft.profiles[0].id;
        this._profileForm = false;
        this._change();
        break;
      }
      case "open":
        this._open = this._open === el.dataset.device ? null : el.dataset.device;
        this._render();
        break;
      case "move-up":
      case "move-down": {
        const list = this._draft.devices;
        const i = list.findIndex((d) => d.id === el.dataset.device);
        const j = act === "move-up" ? i - 1 : i + 1;
        if (i < 0 || j < 0 || j >= list.length) return;
        [list[i], list[j]] = [list[j], list[i]];
        this._change();
        break;
      }
      case "remove-device":
        this._draft.devices = this._draft.devices.filter((d) => d.id !== el.dataset.device);
        this._open = null;
        this._change();
        break;
      case "add-span": {
        const d = this._device(el.dataset.device);
        const p = this._profile();
        const st = this._ensure(d, p);
        const times = this._times(p);
        const last = st.spans.length ? model.spanMinutes(st.spans[st.spans.length - 1], times.start, times.len) : null;
        const from = last ? last.off + 60 : times.start;
        st.spans.push({ on: { ref: "clock", value: toMin(from) }, off: { ref: "clock", value: toMin(from + 60) }, every: null, pulse: null });
        st.mode = "windows";
        this._change();
        break;
      }
      case "remove-span": {
        const d = this._device(el.dataset.device);
        const st = this._ensure(d, this._profile());
        st.spans.splice(Number(el.dataset.index), 1);
        if (!st.spans.length) st.active = false;
        this._change();
        break;
      }
      case "adding":
      case "adding-sensor": {
        const kind = act === "adding" ? "device" : "sensor";
        const open = this._pick?.kind === kind;
        this._pick = open ? null : { kind, query: "", room: this._ownRoom(), cat: "" };
        this._render();
        if (this._pick) this.shadowRoot.querySelector(".pick")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
        break;
      }
      case "pick-cat":
        this._pick.cat = el.dataset.cat;
        this._render();
        break;
      case "pick-add":
        if (this._pick?.kind === "sensor") this._addSensor(el.dataset.e);
        else this._addDevice(el.dataset.e);
        break;
      case "remove-sensor":
        this._draft.settings.sensors = (this._draft.settings.sensors || []).filter((x) => x !== el.dataset.e);
        this._change();
        this.insights.refresh(true);
        break;
      case "switch": {
        // Switching here counts as switching by hand, with the device's setting for that.
        const entity = el.dataset.entity;
        const on = this._hass.states[entity]?.state === "on";
        this._hass.callService(entity.split(".")[0], on ? "turn_off" : "turn_on", { entity_id: entity }).catch((err) => {
          this._error = err?.message || String(err);
          this._render();
        });
        break;
      }
      case "log-all":
        this._logAll = !this._logAll;
        if (this._logAll) this._loadLog();
        else this._render();
        break;
      case "log-refresh":
        this._loadLog();
        break;
      case "settings":
        this._settingsOpen = !this._settingsOpen;
        this._render();
        break;
      case "save":
        this._save();
        break;
      case "discard":
        this._discard();
        break;
    }
  }

  // A double click on an empty spot of a device's row adds a time window there.
  _onDblClick(e) {
    const track = e.target.closest(".track[data-track]");
    if (!track || e.target.closest(".bar")) return;
    const d = this._device(track.dataset.track);
    const p = this._profile();
    if (!d || !p) return;
    const st = this._ensure(d, p);
    if (st.mode === "always") return;
    const rect = track.getBoundingClientRect();
    const at = snap(((e.clientX - rect.left) / rect.width) * DAY);
    st.active = true;
    st.spans.push({ on: { ref: "clock", value: toMin(at) }, off: { ref: "clock", value: toMin(at + 60) }, every: null, pulse: null });
    this._change();
  }

  _onInput(e) {
    const el = e.target;
    if (el.dataset.act === "notes") {
      this._notes = el.value;
      this._notesState = "dirty";
      this._paintNotesState();
      clearTimeout(this._notesTimer);
      this._notesTimer = setTimeout(() => this._saveNotes(), 1200);
      return;
    }
    if (el.dataset.act === "search" && this._pick) {
      this._pick.query = el.value;
      const list = this.shadowRoot.querySelector(".picklist");
      if (list) list.innerHTML = this._pickList();
    }
  }

  _onChange(e) {
    const el = e.target;
    if (el.dataset.act === "profile") return this._control("profile", el.value || null);
    if (el.dataset.act === "log-device") {
      this._logDevice = el.value;
      return this._render();
    }
    if (el.dataset.act === "log-pulses") {
      this._logPulses = el.checked;
      return this._render();
    }
    if (el.dataset.act === "pick-room" && this._pick) {
      this._pick.room = el.value;
      return this._render();
    }
    const num = (v, fallback = 0) => (v === "" || Number.isNaN(Number(v)) ? fallback : Number(v));
    const int = (v, fallback = 0) => Math.round(num(v, fallback));
    if (el.dataset.pfield) this._profileField(el, el.dataset.pfield, int);
    else if (el.dataset.dfield) {
      const d = this._device(el.dataset.device);
      const f = el.dataset.dfield;
      if (!d) return;
      if (f === "manual_minutes") d.manual_minutes = Math.max(1, int(el.value, 60));
      else if (f === "name") d.name = el.value.trim() || d.name;
      else if (f === "max_on_mode") d.max_on = el.value === "default" ? null : el.value === "none" ? 0 : limitOf(d, this._draft.settings) || 30;
      else if (f === "max_on") d.max_on = Math.max(1, int(el.value, 30));
      else d[f] = el.value;
    } else if (el.dataset.sfield) {
      const d = this._device(el.dataset.device);
      const p = this._profile();
      if (!d || !p) return;
      const s = this._ensure(d, p);
      const f = el.dataset.sfield;
      if (f === "active") {
        s.active = el.checked;
        if (s.active && !s.spans.length) s.spans.push(daySpan());
      } else if (f === "mode") s.mode = el.value;
      else if (f === "brightness") s.brightness = el.value === "" ? null : Math.max(1, Math.min(100, int(el.value)));
      else if (f === "ramp") s.ramp = Math.max(0, Math.min(240, int(el.value)));
    } else if (el.dataset.wfield) this._spanField(el, el.dataset.wfield, int, num);
    else if (el.dataset.gfield) this._settingsField(el, el.dataset.gfield, num);
    else return;
    this._change();
  }

  _profileField(el, f, int) {
    const p = this._profile();
    if (!p) return;
    if (f === "start_event") {
      if (el.value === "manual") {
        p.start_event = "date";
        p.start_date = null;
      } else {
        p.start_event = el.value;
        if (el.value === "date" && !p.start_date) p.start_date = "03-01";
      }
    } else if (f === "start_month" || f === "start_day") {
      const [m, d] = (p.start_date || "01-01").split("-");
      const month = f === "start_month" ? el.value : m;
      const day = f === "start_day" ? el.value : d;
      const max = new Date(2024, Number(month), 0).getDate();
      p.start_date = `${String(month).padStart(2, "0")}-${String(Math.min(Number(day) || 1, max)).padStart(2, "0")}`;
    } else if (f === "start_offset") p.start_offset = Math.max(-180, Math.min(180, int(el.value)));
    else if (f === "transition") p.transition = Math.max(0, Math.min(60, int(el.value)));
    else if (f === "name") p.name = el.value.trim() || p.name;
    else if (el.value) p[f] = el.value;
  }

  _spanField(el, f, int, num) {
    const d = this._device(el.dataset.device);
    const p = this._profile();
    if (!d || !p) return;
    const span = this._ensure(d, p).spans[Number(el.dataset.index)];
    if (!span) return;
    const times = this._times(p);
    const key = `${d.id}|${p.id}|${el.dataset.index}`;
    if (f === "on_ref" || f === "off_ref") {
      // Keep the time where it is, now counted from the new reference.
      const edge = f === "on_ref" ? span.on : span.off;
      const m = model.spanMinutes(span, times.start, times.len);
      const abs = m ? (f === "on_ref" ? m.on : m.off) : times.start;
      edge.ref = el.value;
      edge.value = this._edgeValue(edge.ref, abs, times);
    } else if (f === "on_value" || f === "off_value") {
      const edge = f === "on_value" ? span.on : span.off;
      edge.value = edge.ref === "clock" ? toMin(el.value) : Math.max(-720, Math.min(720, int(el.value)));
    } else if (f === "interval") {
      span.every = el.checked ? span.every || 15 : null;
      span.pulse = el.checked ? span.pulse || 60 : null;
    } else if (f === "every") span.every = Math.max(1, Math.min(1440, int(el.value, 15)));
    else if (f === "pulse") {
      const unit = this._units.get(key) || (span.pulse >= 300 && span.pulse % 60 === 0 ? "min" : "s");
      span.pulse = Math.max(1, Math.round(num(el.value, 1) * (unit === "min" ? 60 : 1)));
    } else if (f === "pulse_unit") this._units.set(key, el.value);
  }

  _edgeValue(ref, abs, times) {
    if (ref === "clock") return toMin(abs);
    const base = ref === "start" ? times.start : times.start + times.len;
    return Math.max(-720, Math.min(720, Math.round(abs - base)));
  }

  _settingsField(el, f, num) {
    const g = (this._draft.settings = this._draft.settings || {});
    const n = (g.natural = g.natural || {});
    if (f === "nat_place") {
      if (el.value === "ha") {
        n.latitude = null;
        n.longitude = null;
      } else {
        n.latitude = n.latitude ?? this._snap?.latitude ?? 50;
        n.longitude = n.longitude ?? this._snap?.longitude ?? 10;
      }
    } else if (f === "nat_preset") {
      const [lat, lon] = el.value.split(",").map(Number);
      if (Number.isFinite(lat)) {
        n.latitude = lat;
        n.longitude = lon;
      }
    } else if (f === "nat_lat") n.latitude = Math.max(-90, Math.min(90, num(el.value, 50)));
    else if (f === "nat_lon") n.longitude = Math.max(-180, Math.min(180, num(el.value, 10)));
    else if (f === "nat_center_mode") n.center = el.value === "sun" ? null : n.center || "13:00";
    else if (f === "nat_center") n.center = el.value || n.center;
    else if (f === "nat_min") n.min_length = Math.round(Math.max(0, Math.min(23.9, num(el.value, 10))) * 60);
    else if (f === "nat_max") n.max_length = Math.round(Math.max(0, Math.min(23.9, num(el.value, 14))) * 60);
    else if (f === "nat_factor") n.factor = Math.max(0, Math.min(150, num(el.value, 100))) / 100;
    else if (f === "nat_invert") n.invert = el.checked;
    else if (f.startsWith("maxon_")) {
      g.max_on = { ...(g.max_on ?? { rain: 30 }) };
      const v = Math.round(num(el.value, 0));
      if (v > 0) g.max_on[f.slice(6)] = v;
      else delete g.max_on[f.slice(6)];
    } else if (f === "price") g.price = el.value === "" ? null : Math.max(0, num(el.value, 0));
  }

  async _loadLog() {
    if (!this._b) return;
    try {
      this._logItems = await this._hass.callWS({ type: "cloudless_biome/log", entry_id: this._b.entry_id });
    } catch (err) {
      this._error = err?.message || String(err);
    }
    this._render();
  }

  async _saveNotes() {
    clearTimeout(this._notesTimer);
    if (this._notes == null || !this._b) return;
    this._notesState = "saving";
    this._paintNotesState();
    try {
      await this._hass.callWS({ type: "cloudless_biome/notes", entry_id: this._b.entry_id, text: this._notes });
      this._notesState = "saved";
    } catch (err) {
      this._notesState = "error";
      this._error = err?.message || String(err);
    }
    this._paintNotesState();
  }

  _paintNotesState() {
    const t = this._t;
    const el = this.shadowRoot.querySelector("[data-notes-state]");
    if (!el) return;
    el.textContent =
      { dirty: t("Not saved yet …", "Noch nicht gespeichert …"), saving: t("Saving …", "Speichert …"), saved: t("Saved", "Gespeichert"), error: t("Could not save", "Speichern fehlgeschlagen") }[
        this._notesState
      ] || "";
  }

  // -- dragging -----------------------------------------------------------------------------------------

  _listen() {
    window.addEventListener("pointermove", this._move);
    window.addEventListener("pointerup", this._up);
    window.addEventListener("pointercancel", this._up);
  }

  _onDown(e) {
    if (e.button > 0) return;
    const handle = e.target.closest("[data-reorder]");
    if (handle) {
      this._drag = { what: "order", id: handle.dataset.reorder, moved: false, x0: e.clientX, y0: e.clientY };
      e.preventDefault();
      return this._listen();
    }
    const el = e.target.closest("[data-drag]");
    if (!el) return;
    const track = el.closest(".track");
    const p = this._profile();
    if (!track || !p) return;
    const [what, id, index, mode] = el.dataset.drag.split("|");
    const times = this._times(p);
    const g = { what, id, index: Number(index), mode, x0: e.clientX, width: track.getBoundingClientRect().width, times, moved: false };
    if (what === "span") {
      const d = this._device(id);
      const span = settingOf(this._draft, d, p).spans[g.index];
      const m = span && model.spanMinutes(span, times.start, times.len);
      if (!m) return;
      g.on = m.on;
      g.off = m.off;
    }
    this._drag = g;
    e.preventDefault();
    this._listen();
  }

  _onMove(e) {
    const g = this._drag;
    if (!g) return;
    if (g.what === "order") return this._moveOrder(e, g);
    const dx = e.clientX - g.x0;
    if (!g.moved && Math.abs(dx) < 3) return;
    g.moved = true;
    const delta = (dx / Math.max(1, g.width)) * DAY;
    const p = this._profile();
    const { start: s0, len } = g.times;
    if (g.what === "day") {
      let start = s0,
        end = s0 + len;
      if (g.mode !== "end") start = snap(s0 + delta);
      if (g.mode === "end") end = snap(s0 + len + delta);
      if (g.mode === "move") end = start + len;
      if (end - start < SNAP || end - start >= DAY) return;
      p.day_start = clock(start);
      p.day_end = clock(end);
      g.tip = { at: g.mode === "end" ? end : g.mode === "move" ? (start + end) / 2 : start, text: g.mode === "move" ? `${clock(start)}–${clock(end)}` : clock(g.mode === "end" ? end : start) };
    } else {
      const span = this._ensure(this._device(g.id), p).spans[g.index];
      let on = g.on,
        off = g.off;
      if (g.mode !== "end") on = snap(g.on + delta);
      if (g.mode === "end") off = snap(g.off + delta);
      if (g.mode === "move") off = g.off + (on - g.on);
      if (off - on < SNAP || off - on > DAY) return;
      span.on.value = this._edgeValue(span.on.ref, on, g.times);
      span.off.value = this._edgeValue(span.off.ref, off, g.times);
      const label = (edge, abs) => (edge.ref === "clock" ? clock(abs) : `${clock(abs)} · ${signed(edge.value)} min`);
      g.tip =
        g.mode === "move"
          ? { at: (on + off) / 2, text: `${clock(on)}–${clock(off)}` }
          : g.mode === "start"
            ? { at: on, text: label(span.on, on) }
            : { at: off, text: label(span.off, off) };
    }
    this._dirty = true;
    this._renderTimeline();
  }

  // Drag a device up or down by its handle.
  _moveOrder(e, g) {
    if (!g.moved && Math.abs(e.clientY - g.y0) < 4) return;
    g.moved = true;
    const rows = [...this.shadowRoot.querySelectorAll(".row[data-row]")];
    let target = rows.length - 1;
    for (let i = 0; i < rows.length; i++) {
      const r = rows[i].getBoundingClientRect();
      if (e.clientY < r.top + r.height / 2) {
        target = i;
        break;
      }
    }
    const list = this._draft.devices;
    const from = list.findIndex((d) => d.id === g.id);
    if (from < 0) return;
    if (target > from) {
      const r = rows[target].getBoundingClientRect();
      if (e.clientY < r.top + r.height / 2) target -= 1;
    }
    if (target === from) return;
    list.splice(target, 0, list.splice(from, 1)[0]);
    this._dirty = true;
    this._renderTimeline();
  }

  _onUp() {
    const g = this._drag;
    window.removeEventListener("pointermove", this._move);
    window.removeEventListener("pointerup", this._up);
    window.removeEventListener("pointercancel", this._up);
    this._drag = null;
    if (!g) return;
    if (!g.moved && (g.what === "span" || g.what === "order")) this._open = this._open === g.id ? null : g.id;
    // The click that follows must not open or close the device again.
    this._suppressClick = true;
    setTimeout(() => (this._suppressClick = false), 0);
    this._render();
  }

  _moveNow() {
    const m = this._nowMin();
    for (const el of this.shadowRoot.querySelectorAll(".now")) el.style.left = `${pct(m)}%`;
  }

  _nowMin() {
    const tz = this._snap?.time_zone || this._hass?.config?.time_zone;
    const parts = new Intl.DateTimeFormat("en-GB", { timeZone: tz, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(new Date(Date.now()));
    const get = (type) => Number(parts.find((x) => x.type === type)?.value || 0);
    return get("hour") * 60 + get("minute");
  }

  // -- rooms and the picker ---------------------------------------------------------------------------

  _areaOf(entityId) {
    const h = this._hass;
    const entry = h.entities?.[entityId];
    const areaId = entry?.area_id || (entry?.device_id ? h.devices?.[entry.device_id]?.area_id : null);
    return areaId ? h.areas?.[areaId]?.name || "" : "";
  }

  // The biome's own room: the area of its device in Home Assistant, or else the room most of its devices are in.
  _ownRoom() {
    const h = this._hass;
    const areaId = h.devices?.[this._snap?.device_id]?.area_id;
    if (areaId && h.areas?.[areaId]) return h.areas[areaId].name;
    const count = new Map();
    for (const d of this._draft?.devices || []) {
      const area = this._areaOf(d.entity_id);
      if (area) count.set(area, (count.get(area) || 0) + 1);
    }
    return [...count.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || "";
  }

  _candidates(kind = this._pick?.kind || "device") {
    const h = this._hass;
    const used = new Set(kind === "device" ? this._draft.devices.map((d) => d.entity_id) : this._draft.settings?.sensors || []);
    const pattern = kind === "device" ? /^(switch|light)\./ : /^sensor\./;
    return Object.keys(h.states)
      .filter((id) => pattern.test(id) && !used.has(id) && h.entities?.[id]?.platform !== "cloudless_biome")
      .map((id) => {
        const st = h.states[id];
        const device = h.devices?.[h.entities?.[id]?.device_id];
        const name = st.attributes.friendly_name || id;
        const area = this._areaOf(id);
        const dev = device?.name_by_user || device?.name || "";
        const cat = kind === "device" ? id.split(".")[0] : ["temperature", "humidity", "power", "energy"].includes(st.attributes?.device_class) ? st.attributes.device_class : "other";
        return { id, name, area, device: dev, cat, text: `${name} ${id} ${area} ${dev}`.toLowerCase() };
      })
      .sort((a, b) => a.name.localeCompare(b.name));
  }

  _pickList() {
    const t = this._t;
    const h = this._hass;
    const p = this._pick;
    const words = (p.query || "").trim().toLowerCase().split(/\s+/).filter(Boolean);
    const hits = this._candidates().filter((x) => (!p.cat || x.cat === p.cat) && (!p.room || x.area === p.room) && words.every((w) => x.text.includes(w)));
    if (!hits.length) return `<p class="muted" style="padding:8px">${t("Nothing found.", "Nichts gefunden.")}${p.room ? ` ${t("Try “All rooms”.", "Versuche „Alle Räume“.")}` : ""}</p>`;
    const MAX = 60;
    return (
      hits
        .slice(0, MAX)
        .map((x) => {
          const st = h.states[x.id];
          const unit = st.attributes?.unit_of_measurement;
          const state =
            p.kind === "sensor" ? `${st.state}${unit ? ` ${unit}` : ""}` : st.state === "on" ? t("on", "an") : st.state === "off" ? t("off", "aus") : t("unreachable", "nicht erreichbar");
          const meta = [x.area, x.device && x.device !== x.name ? x.device : "", state].filter(Boolean).join(" · ");
          const ic = st.attributes?.icon || (p.kind === "sensor" ? "mdi:eye-outline" : x.cat === "light" ? "mdi:lightbulb-outline" : "mdi:power-socket-eu");
          return `<button data-act="pick-add" data-e="${esc(x.id)}">${icon(ic, 20)}<span class="pmain"><span class="pname">${esc(x.name)}</span><span class="pmeta">${esc(meta)}</span></span><span class="padd">${t("Add", "Hinzufügen")}</span></button>`;
        })
        .join("") + (hits.length > MAX ? `<p class="muted" style="padding:8px">${t(`${hits.length - MAX} more. Narrow the search.`, `${hits.length - MAX} weitere. Grenze die Suche ein.`)}</p>` : "")
    );
  }

  _addDevice(id) {
    const name = this._hass.states[id]?.attributes?.friendly_name || id;
    this._draft.devices.push({ id: `new-${id}`, name, entity_id: id, kind: guessKind(id, name), manual: "next", manual_minutes: 60, max_on: null, profiles: {} });
    this._change();
  }

  _addSensor(id) {
    const g = (this._draft.settings = this._draft.settings || {});
    g.sensors = [...(g.sensors || []), id];
    this._change();
  }

  // -- rendering --------------------------------------------------------------------------------------

  _render() {
    const t = this._t;
    const r = this.shadowRoot;
    const scroll = r.querySelector(".log")?.scrollTop ?? 0;
    const pick = r.querySelector(".picklist")?.scrollTop ?? 0;
    const focus = r.activeElement?.dataset?.act === "search";
    const notes = r.querySelector("[data-act=notes]");
    const notesFocus = notes && r.activeElement === notes ? { start: notes.selectionStart, end: notes.selectionEnd, top: notes.scrollTop } : null;
    const biomes =
      this._biomes.length > 1
        ? `<div class="tabs" role="tablist">${this._biomes.map((b, i) => `<button role="tab" data-act="biome" data-i="${i}" aria-selected="${i === this._i}">${esc(b.title)}</button>`).join("")}</div>`
        : "";
    r.innerHTML = `<style>${STYLE}</style>
      <div class="shell">
        <div class="top">
          <button class="menu" data-act="menu" aria-label="${t("Menu", "Menü")}" ${this._narrow ? "" : "hidden"}>${MENU_ICON}</button>
          <h1 class="mark">${icon("mdi:leaf", 24)}Biome</h1>
          ${biomes}
          <span class="spacer"></span>
          <a class="link" href="${SETTINGS}">${icon("mdi:cog-outline", 18)}${t("Home Assistant settings", "HA-Einstellungen")}</a>
        </div>
        ${this._error ? `<div class="banner warn"><p>${esc(this._error)}</p></div>` : ""}
        ${this._body()}
      </div>
      ${this._dirty ? this._saveBar() : ""}`;
    const log = r.querySelector(".log");
    if (log) log.scrollTop = scroll;
    const list = r.querySelector(".picklist");
    if (list) list.scrollTop = pick;
    if (notesFocus) {
      const area = r.querySelector("[data-act=notes]");
      area?.focus();
      area?.setSelectionRange(notesFocus.start, notesFocus.end);
      if (area) area.scrollTop = notesFocus.top;
    }
    this._paintNotesState();
    if (focus) {
      const input = r.querySelector('[data-act="search"]');
      input?.focus();
      input?.setSelectionRange(input.value.length, input.value.length);
    }
  }

  _renderTimeline() {
    const card = this.shadowRoot.querySelector("#timeline");
    if (card) card.innerHTML = this._timelineInner();
    if (this._dirty && !this.shadowRoot.querySelector(".savebar")) {
      const box = document.createElement("div");
      box.innerHTML = this._saveBar();
      this.shadowRoot.append(box.firstElementChild);
    }
  }

  _renderInsights() {
    if (this._drag || !this._snap) return;
    for (const [id, html] of [
      ["measurements", this.insights.measurementsHTML()],
      ["energy", this.insights.energyHTML()],
    ]) {
      const el = this.shadowRoot.getElementById(id);
      if (el) el.outerHTML = html;
    }
  }

  _saveBar() {
    const t = this._t;
    return `<div class="savebar"><span>${t("Unsaved changes", "Ungespeicherte Änderungen")}</span>
      <button class="btn" data-act="discard" ${this._saving ? "disabled" : ""}>${t("Discard", "Verwerfen")}</button>
      <button class="btn primary" data-act="save" ${this._saving ? "disabled" : ""}>${this._saving ? t("Saving …", "Speichert …") : t("Save", "Speichern")}</button></div>`;
  }

  _body() {
    const t = this._t;
    if (!this._biomes.length) {
      return `<div class="card empty">${icon("mdi:leaf", 40)}
        <h2>${t("No biome yet", "Noch kein Biom")}</h2>
        <p>${t("Add Cloudless Biome under Settings → Devices & services, for example for your terrarium.", "Füge Cloudless Biome unter Einstellungen → Geräte & Dienste hinzu, z. B. für dein Terrarium.")}</p>
        <a class="btn primary" href="/config/integrations/dashboard/add?domain=cloudless_biome">${t("Add biome", "Biom hinzufügen")}</a></div>`;
    }
    const s = this._snap;
    if (!s || !this._draft) return `<div class="card empty"><p>${t("Loading …", "Lädt …")}</p></div>`;
    return `${this._banners(s)}${this._overview(s)}${this.insights.measurementsHTML()}${this._pick?.kind === "device" ? this._pickCard() : ""}
      <section class="card" id="timeline">${this._timelineInner()}</section>
      ${this.insights.energyHTML()}${this._notesCard(s)}${this._settingsCard()}${this._log(s)}`;
  }

  _banners(s) {
    const t = this._t;
    let out = "";
    if (s.dry_run) {
      out += `<div class="banner info"><p><strong>${t("Dry run.", "Trockenlauf.")}</strong>
        ${t("Biome follows the plan and logs what it would switch, but switches nothing.", "Biome rechnet den Plan mit und protokolliert, was es schalten würde, schaltet aber nichts.")}</p>
        <button class="btn" data-act="dry-run">${t("Let Biome switch", "Biome schalten lassen")}</button></div>`;
    }
    if (s.paused) {
      out += `<div class="banner warn"><p><strong>${t("Paused.", "Pausiert.")}</strong>
        ${t("Biome switches nothing; the devices stay as they are.", "Biome schaltet nichts, die Geräte bleiben, wie sie sind.")}</p>
        <button class="btn" data-act="pause">${t("Resume", "Fortsetzen")}</button></div>`;
    }
    return out;
  }

  _overview(s) {
    const t = this._t;
    const h = this._hass;
    const p = s.profile || {};
    const hint = p.manual
      ? p.until
        ? t(`by hand until ${fmtDate(h, p.until, s)}`, `von Hand bis ${fmtDate(h, p.until, s)}`)
        : t("chosen by hand", "von Hand gewählt")
      : p.automatic
        ? t("active profile, by the calendar", "aktives Profil, nach Kalender")
        : t("active profile", "aktives Profil");
    const options = (s.profiles || []).map((x) => `<option value="${esc(x.id)}" ${x.id === p.id ? "selected" : ""}>${esc(x.name)}</option>`).join("");
    const change = p.transition ? t(`Moving from ${p.transition.from}: day ${p.transition.day} of ${p.transition.days}`, `Übergang von ${p.transition.from}: Tag ${p.transition.day} von ${p.transition.days}`) : "";
    const natural = (s.profiles || []).find((x) => x.id === p.id)?.day_mode === "natural" ? t("natural day", "natürlicher Tag") : "";
    const next = s.next ? `${fmtWhen(h, s.next.at, s)} · ${esc(s.next.name)} ${s.next.state ? t("on", "an") : t("off", "aus")}` : t("nothing planned", "nichts geplant");
    return `<section class="card">
      <div class="hrow"><h2>${esc(s.title)}</h2><span class="spacer"></span>
        <div class="toggles">
          <button class="toggle" data-act="dry-run" aria-pressed="${s.dry_run}"><span class="knob"></span>${t("Dry run", "Trockenlauf")}</button>
          <button class="toggle" data-act="pause" aria-pressed="${s.paused}"><span class="knob"></span>${t("Pause", "Pause")}</button>
        </div>
      </div>
      <div class="facts">
        <div class="fact">${icon(s.day ? "mdi:white-balance-sunny" : "mdi:weather-night", 22)}<div><small>${t("Biome day today", "Biom-Tag heute")}${natural ? ` · ${natural}` : ""}</small>
          <span>${s.day ? t("Day", "Tag") : t("Night", "Nacht")}${p.day_start ? ` · ${p.day_start}–${p.day_end}` : ""}</span>${change ? `<small>${esc(change)}</small>` : ""}</div></div>
        <div class="fact">${icon("mdi:calendar-sync-outline", 22)}<div><small>${esc(hint)}</small>
          <select data-act="profile" aria-label="${t("Active profile", "Aktives Profil")}" ${this._dirty ? "disabled" : ""}>${options}</select></div></div>
        <div class="fact">${icon("mdi:clock-outline", 22)}<div><small>${t("Next switching point", "Nächster Schaltpunkt")}</small><span>${next}</span></div></div>
      </div>
    </section>`;
  }

  _timelineInner() {
    const t = this._t;
    const cfg = this._draft;
    const p = this._profile();
    const tabs = cfg.profiles
      .map(
        (x) => `<button role="tab" data-act="edit-profile" data-id="${esc(x.id)}" aria-selected="${x.id === this._sel}" title="${t("Click again to edit the profile", "Nochmal klicken, um das Profil zu bearbeiten")}">${
          x.id === this._snap.profile?.id ? '<span class="dot" aria-hidden="true"></span>' : ""
        }${esc(x.name)}${x.id === this._sel ? icon("mdi:pencil-outline", 14) : ""}</button>`,
      )
      .join("");
    const head = `<div class="hrow"><h2>${t("Timeline", "Zeitleiste")}</h2>
      <div class="tabs" role="tablist" aria-label="${t("Profile to edit", "Profil zum Bearbeiten")}">${tabs}<button data-act="add-profile">${icon("mdi:plus", 16)}${t("Profile", "Profil")}</button></div>
      <span class="spacer"></span>
      <button class="btn" data-act="adding">${icon("mdi:plus", 18)}${t("Add devices", "Geräte hinzufügen")}</button></div>`;
    if (!p) return head;
    const times = this._times(p);
    const ticks = [0, 3, 6, 9, 12, 15, 18, 21, 24]
      .map((h, i, all) => `<span class="tick ${i === 0 ? "first" : i === all.length - 1 ? "last" : ""}" style="left:${pct(h * 60)}%">${String(h).padStart(2, "0")}</span>`)
      .join("");
    const now = this._nowMin();
    const dayPieces = pieces(times.start, times.start + times.len);
    const bands = dayPieces.map((x) => `<div class="dayband" style="left:${pct(x.a)}%;width:${pct(x.b - x.a)}%"></div>`).join("");
    const grid = [6, 12, 18].map((h) => `<div class="gridline" style="left:${pct(h * 60)}%"></div>`).join("");
    const tip = (g) => (g?.tip ? `<div class="tip" style="left:${Math.max(6, Math.min(94, pct(((g.tip.at % DAY) + DAY) % DAY)))}%">${esc(g.tip.text)}</div>` : "");
    const drag = this._drag;
    const sunBars = dayPieces
      .map((x) =>
        times.natural
          ? `<div class="bar sun fixed" style="left:${pct(x.a)}%;width:${pct(x.b - x.a)}%" title="${esc(t("Follows the sun", "Folgt der Sonne"))}"></div>`
          : `<div class="bar sun ${drag?.what === "day" ? "drag" : ""}" data-drag="day|||move" style="left:${pct(x.a)}%;width:${pct(x.b - x.a)}%">${
              x.startHere ? '<div class="grip start" data-drag="day|||start"></div>' : ""
            }${x.endHere ? '<div class="grip end" data-drag="day|||end"></div>' : ""}</div>`,
      )
      .join("");
    const sub = times.natural
      ? `${clock(times.start)}–${clock(times.start + times.len)} · ${hours(times.len)} · ${t("natural", "natürlich")}`
      : `${p.day_start}–${p.day_end} · ${hours(times.len)}`;
    const dayRow = `<div class="row dayblock">
        <div class="label"><div class="kicon" style="background:var(--bio-day);color:var(--bio-warn)">${icon("mdi:white-balance-sunny", 20)}</div>
          <div class="ltext"><span class="name">${t("Biome day", "Biom-Tag")}</span><span class="sub">${esc(sub)}</span></div></div>
        <div class="track">${grid}${sunBars}<div class="now" style="left:${pct(now)}%"></div>${drag?.what === "day" ? tip(drag) : ""}</div>
      </div>`;
    const rows = cfg.devices.map((d) => this._deviceRow(d, p, times, { bands, grid, now, tip })).join("");
    const empty = cfg.devices.length
      ? ""
      : `<div class="empty">${icon("mdi:power-socket-eu", 32)}<p>${t("No devices yet. Add your outlets and lights, then drag them into place.", "Noch keine Geräte. Füge deine Steckdosen und Leuchten hinzu und schiebe sie dann an ihren Platz.")}</p></div>`;
    return `${head}${this._profileForm ? this._profileFormHTML(p, times) : ""}
      <div class="tl"><div class="axis"><div></div><div class="ticks">${ticks}</div></div>${dayRow}${cfg.devices.length ? `<div class="section">${t("Devices", "Geräte")}</div>` : ""}${rows}</div>${empty}
      <div class="legend"><span>${t(
        "Drag a bar to move it, or its ends to change when it switches. Double-click an empty spot to add a time window. Drag the biome day and all windows that follow it move along. The handle on the left changes the order.",
        "Ziehe einen Balken, um ihn zu verschieben, oder seine Enden für Ein und Aus. Ein Doppelklick auf eine freie Stelle legt ein weiteres Zeitfenster an. Ziehst du den Biom-Tag, wandern alle Fenster mit, die sich nach ihm richten. Mit dem Griff links änderst du die Reihenfolge.",
      )}</span></div>`;
  }

  _deviceRow(d, p, times, { bands, grid, now, tip }) {
    const t = this._t;
    const h = this._hass;
    const kind = kindOf(d);
    const { s, list } = windowsOf(this._draft, d, p, times);
    const live = this._live(d.id);
    const drag = this._drag?.what === "span" && this._drag.id === d.id ? this._drag : null;
    const id = esc(d.id);
    let track;
    if (!s.active) {
      track = `<div class="track inactive" data-act="open" data-device="${id}">${esc(t(`Off in the “${p.name}” profile`, `Aus im Profil „${p.name}“`))}</div>`;
    } else {
      let bars = "";
      for (const w of list) {
        for (const x of pieces(w.on, w.off)) {
          if (w.index < 0) {
            bars += `<div class="bar fixed" style="left:0;width:100%;background:${kind.color}" title="${esc(t("On around the clock", "Durchgehend an"))}"></div>`;
            continue;
          }
          let bg = kind.color;
          let inner = "";
          if (w.pulses.length) {
            bg = `color-mix(in srgb, ${kind.color} 22%, transparent)`;
            if (w.pulses.length <= 400)
              inner = w.pulses
                .map(([a, b]) => [a + x.shift, b + x.shift])
                .filter(([a, b]) => b > x.a && a < x.b)
                .map(([a, b]) => `<div class="pulse" style="left:${((a - x.a) / (x.b - x.a)) * 100}%;width:${((b - a) / (x.b - x.a)) * 100}%;background:${kind.color}"></div>`)
                .join("");
          } else if (s.brightness != null && s.ramp > 0) {
            const r = Math.min(50, (s.ramp / Math.max(1, w.off - w.on)) * 100);
            bg = `linear-gradient(90deg, color-mix(in srgb, ${kind.color} 30%, transparent), ${kind.color} ${r}%, ${kind.color} ${100 - r}%, color-mix(in srgb, ${kind.color} 30%, transparent))`;
          }
          const active = drag && drag.index === w.index;
          bars += `<div class="bar ${active ? "drag" : ""} ${w.pulses.length ? "pulsed" : ""}" data-drag="span|${id}|${w.index}|move" style="left:${pct(x.a)}%;width:${pct(x.b - x.a)}%;background:${bg}">${inner}${
            x.startHere ? `<div class="grip start" data-drag="span|${id}|${w.index}|start"></div>` : ""
          }${x.endHere ? `<div class="grip end" data-drag="span|${id}|${w.index}|end"></div>` : ""}</div>`;
        }
      }
      let manual = "";
      if (p.id === this._snap.profile?.id && live?.override) {
        const until = live.override.until ? (new Date(live.override.until) - new Date(this._snap.range[0])) / 60000 : DAY;
        if (until > now) manual = `<div class="manual" style="left:${pct(now)}%;width:${pct(Math.min(DAY, until) - now)}%"></div>`;
      }
      track = `<div class="track" data-track="${id}">${bands}${grid}${bars}${manual}<div class="now" style="left:${pct(now)}%"></div>${drag ? tip(drag) : ""}</div>`;
    }
    const describe = (w) => `${clock(w.on)}–${clock(w.off)}${w.pulses.length ? ` (${t("every", "alle")} ${w.span.every} min)` : ""}`;
    const times_ = !s.active ? t("off in this profile", "in diesem Profil aus") : s.mode === "always" ? t("on around the clock", "durchgehend an") : list.length ? list.map(describe).join(", ") : t("no time window", "kein Zeitfenster");
    let extra;
    if (live) {
      const bad = live.actual !== "on" && live.actual !== "off";
      const problem = problemText(h, live, this._snap);
      const switcher = bad
        ? ""
        : `<button class="btn switch" data-act="switch" data-entity="${esc(d.entity_id)}" title="${esc(t("Switch now, by hand", "Jetzt von Hand schalten"))}">${live.actual === "on" ? t("Switch off", "Ausschalten") : t("Switch on", "Einschalten")}</button>`;
      extra = `<div class="extra"><span class="state ${live.actual === "on" ? "on" : ""} ${bad ? "bad" : ""}">${esc(actualText(h, live))}</span>${switcher}${
        live.reason === "manual" ? `<span class="livetext">${esc(statusText(h, live, this._snap))}</span>` : ""
      }${problem ? `<span class="problem">${esc(problem)}</span>` : ""}${
        live.override ? `<button class="btn small" data-act="resume" data-device="${id}">${t("Back to the plan", "Zurück zum Plan")}</button>` : ""
      }</div>`;
    } else extra = `<div class="extra"><span class="livetext">${t("new, not saved yet", "neu, noch nicht gespeichert")}</span></div>`;
    const open = this._open === d.id;
    const moving = this._drag?.what === "order" && this._drag.id === d.id && this._drag.moved;
    return `<div class="row ${open ? "open" : ""} ${moving ? "moving" : ""}" data-row="${id}">
        <div class="lcell"><span class="handle" data-reorder="${id}" title="${t("Drag to change the order", "Ziehen, um die Reihenfolge zu ändern")}">${DRAG_ICON}</span><div>
          <button class="label" data-act="open" data-device="${id}" aria-expanded="${open}">
            <div class="kicon" style="background:color-mix(in srgb, ${kind.color} 18%, transparent);color:${kind.color}">${icon(kind.icon, 20)}</div>
            <div class="ltext"><span class="name">${esc(d.name)}</span><span class="sub" title="${esc(times_)}">${esc(times_)}</span></div></button>${extra}</div></div>
        ${track}
        ${open ? this._deviceForm(d, p, times) : ""}
      </div>`;
  }

  _deviceForm(d, p, times) {
    const t = this._t;
    const h = this._hass;
    const s = settingOf(this._draft, d, p);
    const id = esc(d.id);
    const opts = (list, current) => list.map(([k, label]) => `<option value="${esc(k)}" ${String(current) === String(k) ? "selected" : ""}>${esc(label)}</option>`).join("");
    const kinds = opts(Object.entries(KINDS).map(([k, v]) => [k, t(v.en, v.de)]), d.kind);
    const entities = opts([d.entity_id, ...this._candidates("device").map((c) => c.id)].map((e) => [e, `${h.states[e]?.attributes?.friendly_name || e} (${e})`]), d.entity_id);
    const manual = opts(
      [
        ["next", t("Until the next switching point", "Bis zum nächsten Schaltpunkt")],
        ["duration", t("For a fixed time", "Für eine feste Dauer")],
        ["never", t("Back to the plan at once", "Sofort zurück zum Plan")],
      ],
      d.manual,
    );
    const kindDefault = Number((this._draft.settings?.max_on ?? { rain: 30 })[d.kind] || 0);
    const kindName = t(KINDS[d.kind]?.en || "", KINDS[d.kind]?.de || "");
    const limitMode = d.max_on == null ? "default" : d.max_on === 0 ? "none" : "custom";
    const limitOpts = opts(
      [
        ["default", kindDefault ? t(`Default for ${kindName}: ${kindDefault} s`, `Vorgabe für ${kindName}: ${kindDefault} s`) : t(`Default for ${kindName}: none`, `Vorgabe für ${kindName}: keine`)],
        ["custom", t("Own time", "Eigene Dauer")],
        ["none", t("No limit", "Keine Grenze")],
      ],
      limitMode,
    );
    const limit = limitOf(d, this._draft.settings);
    const light = d.entity_id.startsWith("light.");
    const runs = s.active;
    const spans =
      runs && s.mode !== "always"
        ? (s.spans || []).map((span, i) => this._spanForm(d, p, times, span, i, limit)).join("") +
          `<div class="actions"><button class="btn" data-act="add-span" data-device="${id}">${icon("mdi:plus", 16)}${t("Time window", "Zeitfenster")}</button></div>`
        : "";
    const dim =
      light && runs
        ? `<label>${t("Brightness (%)", "Helligkeit (%)")}<input type="number" min="1" max="100" data-sfield="brightness" data-device="${id}" value="${s.brightness ?? ""}" placeholder="${t("on/off only", "nur an/aus")}"></label>
           ${s.mode === "always" ? "" : `<label>${t("Dim up and down (min)", "Hoch- und Runterdimmen (Min.)")}<input type="number" min="0" max="240" data-sfield="ramp" data-device="${id}" value="${s.ramp || 0}"></label>`}`
        : "";
    const list = this._draft.devices;
    const index = list.findIndex((x) => x.id === d.id);
    return `<div class="form">
      <label>${t("Name", "Name")}<input data-dfield="name" data-device="${id}" value="${esc(d.name)}"></label>
      <label>${t("Kind", "Art")}<select data-dfield="kind" data-device="${id}">${kinds}</select></label>
      <label>${t("Switch or light", "Schalter oder Leuchte")}<select data-dfield="entity_id" data-device="${id}">${entities}</select></label>
      <label>${t("When switched by hand", "Bei Handschaltung")}<select data-dfield="manual" data-device="${id}">${manual}</select></label>
      ${d.manual === "duration" ? `<label>${t("Duration (min)", "Dauer (Min.)")}<input type="number" min="1" max="1440" data-dfield="manual_minutes" data-device="${id}" value="${d.manual_minutes}"></label>` : ""}
      <label>${t("Longest time on", "Maximale Einschaltdauer")}<select data-dfield="max_on_mode" data-device="${id}">${limitOpts}</select>
        <span class="hint">${t("Longer on and Biome switches it off, even after a manual switch.", "Länger an, und Biome schaltet ab, auch nach einer Handschaltung.")}</span></label>
      ${limitMode === "custom" ? `<label>${t("Seconds", "Sekunden")}<input type="number" min="1" data-dfield="max_on" data-device="${id}" value="${d.max_on}"></label>` : ""}
      <div class="section">${esc(t(`In the “${p.name}” profile`, `Im Profil „${p.name}“`))}</div>
      <label class="check"><input type="checkbox" data-sfield="active" data-device="${id}" ${runs ? "checked" : ""}>${t("Runs in this profile", "Läuft in diesem Profil")}</label>
      ${
        runs
          ? `<label>${t("Times", "Zeiten")}<select data-sfield="mode" data-device="${id}">${opts(
              [
                ["windows", t("In time windows", "In Zeitfenstern")],
                ["always", t("Around the clock", "Durchgehend an")],
              ],
              s.mode || "windows",
            )}</select></label>`
          : `<p class="hint" style="align-self:center">${t("Off: stays off in this profile, for example a heater in summer.", "Aus: bleibt in diesem Profil aus, z. B. eine Heizung im Sommer.")}</p>`
      }
      ${dim}${spans}
      <div class="actions">
        <button class="btn" data-act="move-up" data-device="${id}" ${index <= 0 ? "disabled" : ""}>${icon("mdi:arrow-up", 16)}${t("Up", "Nach oben")}</button>
        <button class="btn" data-act="move-down" data-device="${id}" ${index >= list.length - 1 ? "disabled" : ""}>${icon("mdi:arrow-down", 16)}${t("Down", "Nach unten")}</button>
        <span class="spacer"></span>
        <button class="btn danger" data-act="remove-device" data-device="${id}">${icon("mdi:delete-outline", 16)}${t("Remove from biome", "Aus dem Biom entfernen")}</button>
        <button class="btn" data-act="open" data-device="${id}">${t("Close", "Schließen")}</button></div>
    </div>`;
  }

  _spanForm(d, p, times, span, i, limit) {
    const t = this._t;
    const id = esc(d.id);
    const m = model.spanMinutes(span, times.start, times.len);
    const refs = (current) =>
      [
        ["start", t("after the day starts", "ab Tagesbeginn")],
        ["end", t("after the day ends", "ab Tagesende")],
        ["clock", t("at a time", "Uhrzeit")],
      ]
        .map(([k, l]) => `<option value="${k}" ${current === k ? "selected" : ""}>${esc(l)}</option>`)
        .join("");
    const edge = (which, e, abs) => {
      const label = which === "on" ? t("On", "Ein") : t("Off", "Aus");
      const input =
        e.ref === "clock"
          ? `<input type="time" data-wfield="${which}_value" data-device="${id}" data-index="${i}" value="${clock(e.value)}">`
          : `<input type="number" step="1" min="-720" max="720" data-wfield="${which}_value" data-device="${id}" data-index="${i}" value="${e.value}" title="${t("minutes, negative = before", "Minuten, negativ = davor")}">`;
      return `<label>${label}<span class="pair"><select data-wfield="${which}_ref" data-device="${id}" data-index="${i}" style="flex:1 1 60%">${refs(e.ref)}</select><span style="flex:1 1 40%">${input}</span></span>
        ${e.ref !== "clock" && abs != null ? `<span class="hint">${t("min", "Min.")} → ${clock(abs)}</span>` : ""}</label>`;
    };
    const key = `${d.id}|${p.id}|${i}`;
    const unit = this._units.get(key) || (span.pulse >= 300 && span.pulse % 60 === 0 ? "min" : "s");
    const pulseShown = span.pulse ? (unit === "min" ? span.pulse / 60 : span.pulse) : "";
    const interval = !!(span.every && span.pulse);
    const warn = interval && limit && span.pulse > limit ? `<span class="warnhint">${t(`Longer than the longest time on (${limit} s): Biome cuts it short.`, `Länger als die maximale Einschaltdauer (${limit} s): Biome schaltet vorher ab.`)}</span>` : "";
    return `<div class="spanbox"><div class="shead">${t("Time window", "Zeitfenster")} ${i + 1}${m ? ` · ${clock(m.on)}–${clock(m.off)}` : ` · ${t("not valid", "ungültig")}`}<span class="spacer"></span>
        <button class="btn small danger" data-act="remove-span" data-device="${id}" data-index="${i}">${t("Remove", "Entfernen")}</button></div>
      ${edge("on", span.on, m?.on)}${edge("off", span.off, m?.off)}
      <label class="check"><input type="checkbox" data-wfield="interval" data-device="${id}" data-index="${i}" ${interval ? "checked" : ""}>${t("Interval", "Intervall")}</label>
      ${
        interval
          ? `<label>${t("Every (min)", "Alle (Min.)")}<input type="number" min="1" max="1440" data-wfield="every" data-device="${id}" data-index="${i}" value="${span.every}"></label>
             <label>${t("For", "Für")}<span class="pair"><input type="number" min="1" step="1" data-wfield="pulse" data-device="${id}" data-index="${i}" value="${pulseShown}">
               <select data-wfield="pulse_unit" data-device="${id}" data-index="${i}" style="flex:0 0 76px"><option value="s" ${unit === "s" ? "selected" : ""}>s</option><option value="min" ${unit === "min" ? "selected" : ""}>min</option></select></span>${warn}</label>`
          : ""
      }
    </div>`;
  }

  _profileFormHTML(p, times) {
    const t = this._t;
    const others = this._draft.profiles.filter((x) => x.id !== p.id);
    const event = p.start_event && p.start_event !== "date" ? p.start_event : p.start_date ? "date" : "manual";
    const [month, day] = p.start_date ? p.start_date.split("-").map(Number) : [3, 1];
    const events = [
      ["manual", t("By hand only", "Nur von Hand")],
      ["date", t("On a date", "An einem Datum")],
      ["dst_start", t("When summer time starts", "Beginn der Sommerzeit")],
      ["dst_end", t("When summer time ends", "Ende der Sommerzeit")],
      ["spring", t("Start of spring (astronomical)", "Frühlingsanfang (astronomisch)")],
      ["summer", t("Start of summer (astronomical)", "Sommeranfang (astronomisch)")],
      ["autumn", t("Start of autumn (astronomical)", "Herbstanfang (astronomisch)")],
      ["winter", t("Start of winter (astronomical)", "Winteranfang (astronomisch)")],
    ]
      .map(([k, l]) => `<option value="${k}" ${event === k ? "selected" : ""}>${esc(l)}</option>`)
      .join("");
    const months = MONTHS[this._lang].map((name, i) => `<option value="${i + 1}" ${month === i + 1 ? "selected" : ""}>${name}</option>`).join("");
    const days = Array.from({ length: 31 }, (_, i) => `<option value="${i + 1}" ${day === i + 1 ? "selected" : ""}>${i + 1}.</option>`).join("");
    const saved = this._snap.profiles?.find((x) => x.id === p.id);
    const nextStart = !this._dirty && saved?.next_start ? t(`Next start: ${fmtDate(this._hass, saved.next_start, this._snap, { day: "numeric", month: "long", year: "numeric" })}`, `Nächster Beginn: ${fmtDate(this._hass, saved.next_start, this._snap, { day: "numeric", month: "long", year: "numeric" })}`) : "";
    const natural = p.day_mode === "natural";
    return `<div class="form profileform">
      <label>${t("Profile name", "Name des Profils")}<input data-pfield="name" value="${esc(p.name)}"></label>
      <label>${t("Biome day", "Biom-Tag")}<select data-pfield="day_mode">
        <option value="fixed" ${natural ? "" : "selected"}>${t("Fixed times", "Feste Zeiten")}</option>
        <option value="natural" ${natural ? "selected" : ""}>${t("Natural day (follows the sun)", "Natürlicher Tag (folgt der Sonne)")}</option></select></label>
      ${
        natural
          ? `<p class="hint" style="align-self:center">${t(`Today ${clock(times.start)}–${clock(times.start + times.len)}. Place and limits are in the biome settings below.`, `Heute ${clock(times.start)}–${clock(times.start + times.len)}. Ort und Grenzen stehen unten in den Biom-Einstellungen.`)}</p>`
          : `<label>${t("Day starts", "Tagesbeginn")}<input type="time" data-pfield="day_start" value="${esc(p.day_start)}"></label>
             <label>${t("Day ends", "Tagesende")}<input type="time" data-pfield="day_end" value="${esc(p.day_end)}"></label>`
      }
      <div class="section">${t("When the profile starts", "Wann das Profil beginnt")}</div>
      <label>${t("Starts", "Beginnt")}<select data-pfield="start_event">${events}</select>${nextStart ? `<span class="hint">${esc(nextStart)}</span>` : ""}</label>
      ${
        event === "date"
          ? `<label>${t("Every year on", "Jedes Jahr am")}<span class="pair"><select data-pfield="start_day" aria-label="${t("Day", "Tag")}" style="flex:0 0 76px">${days}</select><select data-pfield="start_month" aria-label="${t("Month", "Monat")}">${months}</select></span></label>`
          : ""
      }
      ${
        event !== "manual"
          ? `<label>${t("Days before (−) or after", "Tage davor (−) oder danach")}<input type="number" min="-180" max="180" data-pfield="start_offset" value="${p.start_offset || 0}"></label>
             <label>${t("Soft change (days)", "Weicher Übergang (Tage)")}<input type="number" min="0" max="60" data-pfield="transition" value="${p.transition || 0}">
               <span class="hint">${t("The day moves slowly from the previous profile's times.", "Der Tag rückt langsam von den Zeiten des vorigen Profils herüber.")}</span></label>`
          : ""
      }
      <div class="actions">${others.length ? `<button class="btn danger" data-act="remove-profile">${icon("mdi:delete-outline", 16)}${t("Delete profile", "Profil löschen")}</button>` : ""}
        <button class="btn" data-act="edit-profile" data-id="${esc(p.id)}">${t("Close", "Schließen")}</button></div>
    </div>`;
  }

  _settingsCard() {
    const t = this._t;
    const head = `<button class="fold" data-act="settings" aria-expanded="${this._settingsOpen}">${icon(this._settingsOpen ? "mdi:chevron-down" : "mdi:chevron-right", 20)}${t("Biome settings", "Biom-Einstellungen")}</button>`;
    if (!this._settingsOpen) return `<section class="card">${head}</section>`;
    const g = this._draft.settings || {};
    const n = g.natural || {};
    const nat = naturalOf(g, this._snap);
    const custom = n.latitude != null;
    const sun = !n.center;
    const today = this._today;
    const preview = (label, dayObj) => {
      const x = dayTimes({ day_mode: "natural" }, dayObj, g, this._snap);
      return `${label} ${clock(x.start)}–${clock(x.start + x.len)} (${hours(x.len)}${Math.abs(x.raw - x.len) > 5 ? `, ${t("outside", "draußen")} ${hours(Math.round(x.raw))}` : ""})`;
    };
    const presets = [
      ["", t("Choose a region …", "Region wählen …")],
      ["52.5,13.4", t("Central Europe (Berlin)", "Mitteleuropa (Berlin)")],
      ["-23.7,133.9", t("Central Australia (Alice Springs)", "Zentralaustralien (Alice Springs)")],
      ["-3.1,-60.0", t("Amazon (Manaus)", "Amazonas (Manaus)")],
      ["-18.9,47.5", t("Madagascar (Antananarivo)", "Madagaskar (Antananarivo)")],
      ["9.9,-84.1", t("Central America (Costa Rica)", "Mittelamerika (Costa Rica)")],
      ["23.4,25.7", t("Sahara (Egypt)", "Sahara (Ägypten)")],
      ["1.3,103.8", t("South East Asia (Singapore)", "Südostasien (Singapur)")],
    ]
      .map(([k, l]) => `<option value="${k}">${esc(l)}</option>`)
      .join("");
    const sensors = (g.sensors || [])
      .map((id) => `<span>${esc(this._hass.states[id]?.attributes?.friendly_name || id)}<button data-act="remove-sensor" data-e="${esc(id)}" aria-label="${t("Remove", "Entfernen")}">✕</button></span>`)
      .join("");
    const maxOn = g.max_on ?? { rain: 30 };
    const kinds = Object.entries(KINDS)
      .map(([k, v]) => `<label>${esc(t(v.en, v.de))}<input type="number" min="0" data-gfield="maxon_${k}" value="${maxOn[k] || ""}" placeholder="${t("no limit", "keine Grenze")}"></label>`)
      .join("");
    return `<section class="card">${head}
      <div class="form" style="padding-top:0">
        <div class="section">${t("Natural day", "Natürlicher Tag")}</div>
        <p class="hint wide">${t(
          "For profiles with a natural day: the length follows the sun at a place, kept between a shortest and a longest day. Centred on the sun's highest point, it matches the real daylight where you live.",
          "Für Profile mit natürlichem Tag: Die Länge folgt der Sonne an einem Ort und bleibt zwischen kürzestem und längstem Tag. Liegt die Mitte auf dem Sonnenhöchststand, passt der Tag zum echten Tageslicht bei dir.",
        )}</p>
        <label>${t("Place", "Ort")}<select data-gfield="nat_place"><option value="ha" ${custom ? "" : "selected"}>${t("Where Home Assistant is", "Standort von Home Assistant")}</option><option value="custom" ${custom ? "selected" : ""}>${t("Another place", "Anderer Ort")}</option></select></label>
        ${
          custom
            ? `<label>${t("Region", "Region")}<select data-gfield="nat_preset">${presets}</select></label>
               <label>${t("Latitude", "Breitengrad")}<input type="number" step="0.1" min="-90" max="90" data-gfield="nat_lat" value="${nat.latitude}"></label>
               <label>${t("Longitude", "Längengrad")}<input type="number" step="0.1" min="-180" max="180" data-gfield="nat_lon" value="${nat.longitude}"></label>`
            : ""
        }
        <label>${t("Middle of the day", "Mitte des Tages")}<select data-gfield="nat_center_mode"><option value="sun" ${sun ? "selected" : ""}>${t("Sun's highest point", "Sonnenhöchststand")}</option><option value="fixed" ${sun ? "" : "selected"}>${t("A fixed time", "Feste Uhrzeit")}</option></select></label>
        ${sun ? "" : `<label>${t("Time", "Uhrzeit")}<input type="time" data-gfield="nat_center" value="${esc(n.center || "13:00")}"></label>`}
        <label>${t("Shortest day (h)", "Kürzester Tag (Std.)")}<input type="number" step="0.25" min="0" max="23.9" data-gfield="nat_min" value="${nat.min / 60}"></label>
        <label>${t("Longest day (h)", "Längster Tag (Std.)")}<input type="number" step="0.25" min="0" max="23.9" data-gfield="nat_max" value="${nat.max / 60}"></label>
        <label>${t("Strength of the seasons (%)", "Stärke der Jahreszeiten (%)")}<input type="number" min="0" max="150" step="5" data-gfield="nat_factor" value="${Math.round(nat.factor * 100)}">
          <span class="hint">${t("100 = as nature, 50 = half the difference, 0 = always 12 hours", "100 = wie in der Natur, 50 = halber Unterschied, 0 = immer 12 Std.")}</span></label>
        <label class="check"><input type="checkbox" data-gfield="nat_invert" ${nat.invert ? "checked" : ""}>${t("Seasons of the other hemisphere", "Jahreszeiten der anderen Erdhälfte")}</label>
        <p class="hint wide">${esc(
          [preview(t("Today", "Heute"), today), preview(t("21 June", "21. Juni"), { y: today.y, m: 6, d: 21 }), preview(t("21 Dec", "21. Dez."), { y: today.y, m: 12, d: 21 })].join(" · "),
        )}</p>
        <div class="section">${t("Longest time on, by kind (seconds)", "Maximale Einschaltdauer je Art (Sekunden)")}</div>
        ${kinds}
        <p class="hint wide">${t("Each device can have its own time in its details.", "Jedes Gerät kann in seinen Details eine eigene Dauer bekommen.")}</p>
        <div class="section">${t("Measurements", "Messwerte")}</div>
        <div class="wide"><div class="chiplist">${sensors || `<span style="border:0;padding-left:0;color:var(--bio-muted)">${t("Automatic: sensors in the biome's room", "Automatisch: Sensoren im Raum des Bioms")}</span>`}</div></div>
        <div class="actions"><button class="btn" data-act="adding-sensor">${icon("mdi:plus", 16)}${t("Add sensor", "Sensor hinzufügen")}</button></div>
        ${this._pick?.kind === "sensor" ? `<div class="wide">${this._pickCard()}</div>` : ""}
        <div class="section">${t("Energy", "Energie")}</div>
        <label>${t("Price per kWh (€)", "Strompreis je kWh (€)")}<input type="number" step="0.01" min="0" data-gfield="price" value="${g.price ?? ""}"></label>
      </div></section>`;
  }

  _pickCard() {
    const t = this._t;
    const p = this._pick;
    const items = this._candidates();
    const areas = [...new Set(items.map((x) => x.area).filter(Boolean))];
    if (p.room && !areas.includes(p.room)) areas.push(p.room);
    areas.sort((a, b) => a.localeCompare(b));
    const kinds =
      p.kind === "device"
        ? [
            ["switch", t("Switches", "Schalter")],
            ["light", t("Lights", "Leuchten")],
          ]
        : [
            ["temperature", t("Temperature", "Temperatur")],
            ["humidity", t("Humidity", "Feuchte")],
            ["power", t("Power", "Leistung")],
            ["energy", t("Energy", "Energie")],
            ["other", t("Other", "Andere")],
          ];
    const inRoom = (x) => !p.room || x.area === p.room;
    const chips = [["", `${t("All", "Alle")} ${items.filter(inRoom).length}`], ...kinds.filter(([k]) => items.some((x) => x.cat === k)).map(([k, l]) => [k, `${l} ${items.filter((x) => x.cat === k && inRoom(x)).length}`])]
      .map(([k, l]) => `<button class="chip" data-act="pick-cat" data-cat="${esc(k)}" aria-pressed="${p.cat === k}">${esc(l)}</button>`)
      .join("");
    const rooms = `<select data-act="pick-room" aria-label="${t("Room", "Raum")}"><option value="">${t("All rooms", "Alle Räume")}</option>${areas
      .map((a) => `<option value="${esc(a)}" ${a === p.room ? "selected" : ""}>${esc(a)}</option>`)
      .join("")}</select>`;
    const title = p.kind === "device" ? t("Add devices", "Geräte hinzufügen") : t("Add sensors", "Sensoren hinzufügen");
    const act = p.kind === "device" ? "adding" : "adding-sensor";
    return `<section class="card pick"><div class="hrow"><h2>${title}</h2><span class="spacer"></span>
        <button class="btn primary" data-act="${act}">${t("Done", "Fertig")}</button></div>
      <div class="filters"><input type="search" data-act="search" placeholder="${t("Search by name, room or device", "Nach Name, Raum oder Gerät suchen")}" value="${esc(p.query)}" autocomplete="off">${rooms}</div>
      <div class="chips" role="group" aria-label="${t("Kind", "Art")}">${chips}</div>
      <div class="picklist">${this._pickList()}</div>
      ${p.kind === "device" ? `<p class="muted">${t("New devices start with the biome day; drag them into place on the timeline.", "Neue Geräte starten mit dem Biom-Tag. Auf der Zeitleiste schiebst du sie an ihren Platz.")}</p>` : ""}</section>`;
  }

  _notesCard(s) {
    const t = this._t;
    const text = this._notes ?? s.notes ?? "";
    return `<section class="card notes"><div class="hrow"><h2>${t("Notes", "Notizen")}</h2><span class="spacer"></span><small class="muted" data-notes-state></small></div>
      <textarea data-act="notes" placeholder="${t(
        "For example what your animals or plants need: temperatures, humidity, light, feeding …",
        "Zum Beispiel, was deine Tiere oder Pflanzen brauchen: Temperaturen, Luftfeuchte, Licht, Fütterung …",
      )}">${esc(text)}</textarea></section>`;
  }

  _log(s) {
    const t = this._t;
    const h = this._hass;
    const row = (i) => `<div><time datetime="${esc(i.at)}">${esc(fmtWhen(h, i.at, s))}</time><span class="${i.routine ? "routine" : i.kind === "would_switch" ? "dry" : ""}">${logText(h, i)}</span></div>`;
    const toggle = `<button class="btn small" data-act="log-all">${this._logAll ? t("Fewer", "Weniger") : t("Show all", "Alle anzeigen")}</button>`;
    if (this._logAll) {
      const devices = this._draft?.devices || [];
      const items = (this._logItems || [])
        .filter((i) => (this._logPulses || !i.routine) && (!this._logDevice || i.device === this._logDevice))
        .reverse();
      const options = `<option value="">${t("All devices", "Alle Geräte")}</option>${devices
        .map((d) => `<option value="${esc(d.id)}" ${d.id === this._logDevice ? "selected" : ""}>${esc(d.name)}</option>`)
        .join("")}`;
      return `<section class="card"><div class="hrow"><h2>${t("Log", "Protokoll")}</h2><span class="spacer"></span>${toggle}</div>
        <div class="logtools"><select data-act="log-device" aria-label="${t("Device", "Gerät")}">${options}</select>
          <label><input type="checkbox" data-act="log-pulses" ${this._logPulses ? "checked" : ""}>${t("Interval switches", "Intervall-Schaltungen")}</label>
          <button class="btn small" data-act="log-refresh">${t("Refresh", "Aktualisieren")}</button>
          <span class="muted">${items.length} ${t("entries", "Einträge")}</span></div>
        <div class="log" style="max-height:520px">${items.length ? items.map(row).join("") : `<p class="muted">${t("Nothing found.", "Nichts gefunden.")}</p>`}</div></section>`;
    }
    const names = Object.fromEntries((s.devices || []).map((d) => [d.id, d.name]));
    const pulses = Object.entries(s.pulse_log || {})
      .filter(([, list]) => list.length)
      .map(
        ([id, list]) =>
          `<div><b>${esc(names[id] || list[0].name || id)}</b> · ${t("interval", "Intervall")}: <span>${list
            .map((i) => `${esc(fmtWhen(h, i.at, s))} ${i.kind === "would_switch" ? t("would be", "würde") + " " : ""}${i.state === "on" ? t("on", "ein") : t("off", "aus")}`)
            .join(" · ")}</span></div>`,
      )
      .join("");
    const items = [...(s.log || [])].reverse();
    const rows = items.length ? items.map(row).join("") : `<p class="muted">${t("Nothing yet.", "Noch nichts.")}</p>`;
    return `<section class="card"><div class="hrow"><h2>${t("Log", "Protokoll")}</h2><span class="spacer"></span>${toggle}</div>
      ${pulses ? `<div class="pulses">${pulses}</div>` : ""}<div class="log">${rows}</div></section>`;
  }

}

if (!customElements.get("biome-panel")) customElements.define("biome-panel", BiomePanel);
