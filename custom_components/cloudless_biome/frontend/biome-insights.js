// Measurements and energy on the Biome page: values of sensors with their last 24 hours, and the power and
// energy of the Home Assistant devices behind the biome's outlets.

const shared = await import(new URL(`./biome-shared.js${new URL(import.meta.url).search}`, import.meta.url).href);
const { esc, icon, tr } = shared;

const HOUR = 3600000;
const MEASURE_CLASSES = ["temperature", "humidity", "illuminance", "pressure", "moisture", "carbon_dioxide", "pm25"];
const CLASS_ICONS = {
  temperature: "mdi:thermometer",
  humidity: "mdi:water-percent",
  illuminance: "mdi:brightness-5",
  pressure: "mdi:gauge",
  moisture: "mdi:water",
  carbon_dioxide: "mdi:molecule-co2",
  power: "mdi:flash",
  energy: "mdi:lightning-bolt",
};
const REFRESH = 5 * 60000;

export const INSIGHTS_STYLE = `
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 10px; }
.tile { border-radius: 12px; background: var(--bio-night); padding: 10px 12px; display: grid; gap: 4px; min-width: 0; }
.tile .head { display: flex; align-items: center; gap: 6px; color: var(--bio-muted); font-size: 13px; min-width: 0; }
.tile .head span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tile .value { font-size: 24px; font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: -.01em; }
.tile .value small { font-size: 14px; font-weight: 600; color: var(--bio-muted); margin-left: 3px; }
.tile svg { width: 100%; height: 42px; display: block; }
.tile .range { font-size: 12px; color: var(--bio-muted); font-variant-numeric: tabular-nums; }
.energy { overflow-x: auto; }
.energy table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; min-width: 520px; }
.energy th, .energy td { text-align: right; padding: 7px 8px; border-bottom: 1px solid var(--bio-line); white-space: nowrap; }
.energy th:first-child, .energy td:first-child { text-align: left; white-space: normal; }
.energy th { font-size: 12.5px; color: var(--bio-muted); font-weight: 600; }
.energy td small { display: block; color: var(--bio-muted); font-size: 12px; }
.energy tr.total td { font-weight: 700; border-bottom: 0; }
`;

const num = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};
const fmt = (hass, v, digits = 1) =>
  v == null ? "–" : new Intl.NumberFormat(hass?.locale?.language || hass?.language || "en", { maximumFractionDigits: digits, minimumFractionDigits: 0 }).format(v);

export class Insights {
  constructor(panel) {
    this.panel = panel;
    this.history = {};
    this.stats = {};
    this.loaded = 0;
    this.loading = false;
  }

  get hass() {
    return this.panel._hass;
  }

  // The sensors to show: chosen in the settings, or else the measuring sensors in the biome's room.
  sensors() {
    const chosen = this.panel._draft?.settings?.sensors || [];
    if (chosen.length) return { ids: chosen.filter((id) => this.hass.states[id]), auto: false };
    const room = this.panel._ownRoom();
    if (!room) return { ids: [], auto: true, room };
    const ids = Object.keys(this.hass.states).filter((id) => {
      if (!id.startsWith("sensor.")) return false;
      const dc = this.hass.states[id].attributes?.device_class;
      return MEASURE_CLASSES.includes(dc) && this.panel._areaOf(id) === room;
    });
    return { ids: ids.sort((a, b) => this._name(a).localeCompare(this._name(b))), auto: true, room };
  }

  // The Home Assistant devices behind the biome's outlets, with their power and energy sensors.
  groups() {
    const h = this.hass;
    const groups = new Map();
    for (const d of this.panel._draft?.devices || []) {
      const devId = h.entities?.[d.entity_id]?.device_id;
      if (!devId) continue;
      if (!groups.has(devId)) {
        const dev = h.devices?.[devId];
        groups.set(devId, { id: devId, name: dev?.name_by_user || dev?.name || d.name, outlets: [], power: [], energy: [] });
      }
      groups.get(devId).outlets.push(d.name);
    }
    for (const [eid, ent] of Object.entries(h.entities || {})) {
      const g = groups.get(ent.device_id);
      const st = h.states[eid];
      if (!g || !st || !eid.startsWith("sensor.")) continue;
      const dc = st.attributes?.device_class;
      const unit = st.attributes?.unit_of_measurement;
      if (dc === "power" || unit === "W" || unit === "kW") g.power.push(eid);
      else if (dc === "energy" || unit === "kWh" || unit === "Wh") g.energy.push(eid);
    }
    return [...groups.values()];
  }

  _name(id) {
    return this.hass.states[id]?.attributes?.friendly_name || id;
  }

  // Fetch the last 24 hours of the sensors and 30 days of energy, at most every few minutes.
  async refresh(force = false) {
    if (this.loading || (!force && Date.now() - this.loaded < REFRESH) || !this.hass) return;
    this.loading = true;
    const now = new Date();
    const sensors = this.sensors().ids;
    const groups = this.groups();
    try {
      if (sensors.length) {
        const res = await this.hass.callWS({
          type: "history/history_during_period",
          start_time: new Date(now - 24 * HOUR).toISOString(),
          end_time: now.toISOString(),
          entity_ids: sensors,
          minimal_response: true,
          no_attributes: true,
        });
        this.history = {};
        for (const [id, rows] of Object.entries(res || {})) {
          this.history[id] = rows
            .map((r) => [r.lu != null ? r.lu * 1000 : r.lc != null ? r.lc * 1000 : Date.parse(r.last_updated || r.last_changed), num(r.s ?? r.state)])
            .filter(([t, v]) => Number.isFinite(t) && v != null);
        }
      }
      const energy = groups.flatMap((g) => g.energy);
      if (energy.length) {
        const midnight = new Date(now);
        midnight.setHours(0, 0, 0, 0);
        this.today = midnight.getTime();
        const res = await this.hass.callWS({
          type: "recorder/statistics_during_period",
          start_time: new Date(midnight.getTime() - 29 * 24 * HOUR).toISOString(),
          end_time: now.toISOString(),
          statistic_ids: energy,
          period: "day",
          types: ["change"],
        });
        this.stats = res || {};
      }
    } catch (err) {
      this.error = err?.message || String(err);
    }
    this.loaded = Date.now();
    this.loading = false;
    this.panel._renderInsights();
  }

  _sum(id, days) {
    const rows = this.stats[id] || [];
    const from = (this.today || 0) - (days - 1) * 24 * HOUR;
    const unit = this.hass.states[id]?.attributes?.unit_of_measurement;
    const scale = unit === "Wh" ? 0.001 : unit === "MWh" ? 1000 : 1;
    let total = null;
    for (const r of rows) {
      const start = typeof r.start === "number" ? r.start : Date.parse(r.start);
      if (start >= from && r.change != null) total = (total || 0) + r.change * scale;
    }
    return total;
  }

  _spark(points, now) {
    if (points.length < 2) return "";
    const vals = points.map((p) => p[1]);
    const lo = Math.min(...vals),
      hi = Math.max(...vals);
    const span = hi - lo || 1;
    const t0 = now - 24 * HOUR;
    let d = "";
    let last = null;
    for (const [t, v] of points) {
      const x = Math.max(0, Math.min(100, ((t - t0) / (24 * HOUR)) * 100));
      const y = 38 - ((v - lo) / span) * 34;
      d += last == null ? `M${x.toFixed(2)},${y.toFixed(2)}` : `H${x.toFixed(2)}V${y.toFixed(2)}`;
      last = y;
    }
    d += "H100";
    return `<svg viewBox="0 0 100 42" preserveAspectRatio="none" aria-hidden="true"><path d="${d}" fill="none" stroke="var(--bio-accent)" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`;
  }

  measurementsHTML() {
    const t = tr(this.hass);
    const h = this.hass;
    const { ids, auto, room } = this.sensors();
    const now = Date.now();
    const hint = auto
      ? room
        ? t(`Sensors in the room ${room}. Choose others in the biome settings.`, `Sensoren im Raum ${room}. Andere wählst du in den Biom-Einstellungen.`)
        : t("Choose sensors in the biome settings, or give the biome device a room.", "Wähle Sensoren in den Biom-Einstellungen, oder gib dem Biom-Gerät einen Raum.")
      : "";
    const tiles = ids
      .map((id) => {
        const st = h.states[id];
        const unit = st.attributes?.unit_of_measurement || "";
        const dc = st.attributes?.device_class;
        const points = this.history[id] || [];
        const vals = points.map((p) => p[1]);
        const range = vals.length ? `24 h: ${fmt(h, Math.min(...vals))} – ${fmt(h, Math.max(...vals))} ${esc(unit)}` : "";
        return `<div class="tile"><div class="head">${icon(st.attributes?.icon || CLASS_ICONS[dc] || "mdi:eye-outline", 16)}<span>${esc(this._name(id))}</span></div>
          <div class="value">${esc(fmt(h, num(st.state)) === "–" ? st.state : fmt(h, num(st.state)))}<small>${esc(unit)}</small></div>
          ${this._spark(points, now)}<div class="range">${range}</div></div>`;
      })
      .join("");
    return `<section class="card" id="measurements"><div class="hrow"><h2>${t("Measurements", "Messwerte")}</h2><span class="spacer"></span><small class="muted">${esc(hint)}</small></div>
      ${ids.length ? `<div class="tiles">${tiles}</div>` : `<p class="muted">${t("No sensors yet.", "Noch keine Sensoren.")}</p>`}</section>`;
  }

  energyHTML() {
    const t = tr(this.hass);
    const h = this.hass;
    const groups = this.groups().filter((g) => g.power.length || g.energy.length);
    const price = this.panel._draft?.settings?.price;
    if (!groups.length) {
      return `<section class="card" id="energy"><h2>${t("Energy", "Energie")}</h2><p class="muted">${t(
        "None of the biome's devices reports power or energy.",
        "Keines der Geräte im Biom meldet Leistung oder Energie.",
      )}</p></section>`;
    }
    const cost = (kwh) => (price != null && kwh != null ? `<small>${fmt(h, kwh * price, 2)} €</small>` : "");
    const total = { now: null, d1: null, d7: null, d30: null };
    const add = (k, v) => v != null && (total[k] = (total[k] || 0) + v);
    const rows = groups
      .map((g) => {
        let watts = null;
        for (const id of g.power) {
          const st = h.states[id];
          const v = num(st?.state);
          if (v != null) watts = (watts || 0) + (st.attributes?.unit_of_measurement === "kW" ? v * 1000 : v);
        }
        const sum = (days) => g.energy.reduce((acc, id) => {
          const v = this._sum(id, days);
          return v == null ? acc : (acc || 0) + v;
        }, null);
        const d1 = sum(1),
          d7 = sum(7),
          d30 = sum(30);
        add("now", watts);
        add("d1", d1);
        add("d7", d7);
        add("d30", d30);
        return `<tr><td>${esc(g.name)}<small>${esc(g.outlets.join(", "))}</small></td><td>${watts == null ? "–" : `${fmt(h, watts, 0)} W`}</td>
          <td>${d1 == null ? "–" : `${fmt(h, d1, 2)} kWh`}${cost(d1)}</td><td>${d7 == null ? "–" : `${fmt(h, d7, 2)} kWh`}${cost(d7)}</td><td>${d30 == null ? "–" : `${fmt(h, d30, 1)} kWh`}${cost(d30)}</td></tr>`;
      })
      .join("");
    const totalRow =
      groups.length > 1
        ? `<tr class="total"><td>${t("Total", "Gesamt")}</td><td>${total.now == null ? "–" : `${fmt(h, total.now, 0)} W`}</td><td>${total.d1 == null ? "–" : `${fmt(h, total.d1, 2)} kWh`}${cost(total.d1)}</td>
          <td>${total.d7 == null ? "–" : `${fmt(h, total.d7, 2)} kWh`}${cost(total.d7)}</td><td>${total.d30 == null ? "–" : `${fmt(h, total.d30, 1)} kWh`}${cost(total.d30)}</td></tr>`
        : "";
    return `<section class="card" id="energy"><div class="hrow"><h2>${t("Energy", "Energie")}</h2><span class="spacer"></span>
        ${price == null ? `<small class="muted">${t("Set a price per kWh in the biome settings to see costs.", "Mit einem Strompreis in den Biom-Einstellungen siehst du die Kosten.")}</small>` : ""}</div>
      <div class="energy"><table><thead><tr><th>${t("Device", "Gerät")}</th><th>${t("Now", "Jetzt")}</th><th>${t("Today", "Heute")}</th><th>${t("7 days", "7 Tage")}</th><th>${t("30 days", "30 Tage")}</th></tr></thead>
      <tbody>${rows}${totalRow}</tbody></table></div></section>`;
  }
}
