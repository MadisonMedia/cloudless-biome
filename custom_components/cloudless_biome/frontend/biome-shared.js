// Shared by the Biome page and, later, the Biome card: language, times, texts and the day timeline.

export const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
export const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

export const langOf = (hass) => (hass?.locale?.language || hass?.language || "en").split("-")[0];
export const tr = (hass) => {
  const de = langOf(hass) === "de";
  return (en, german) => (de ? german : en);
};

// Biome's times are wall-clock times of the Home Assistant server.
export const tzOf = (hass, snap) => snap?.time_zone || hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;

const formatters = new Map();
function formatter(lang, tz, opts) {
  const key = `${lang}|${tz}|${JSON.stringify(opts)}`;
  if (!formatters.has(key)) formatters.set(key, new Intl.DateTimeFormat(lang, { timeZone: tz, ...opts }));
  return formatters.get(key);
}
export const fmtTime = (hass, iso, snap) =>
  iso ? formatter(langOf(hass), tzOf(hass, snap), { hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(iso)) : "";
export const fmtDate = (hass, iso, snap, opts = { day: "numeric", month: "short" }) =>
  iso ? formatter(langOf(hass), tzOf(hass, snap), opts).format(new Date(iso.length === 10 ? `${iso}T12:00:00Z` : iso)) : "";
// Time, with the date when it is not today.
export function fmtWhen(hass, iso, snap) {
  if (!iso) return "";
  const day = (x) => formatter("en-CA", tzOf(hass, snap), { year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(x));
  const time = fmtTime(hass, iso, snap);
  if (day(iso) === day(snap?.now || Date.now())) return time;
  return `${fmtDate(hass, iso, snap, { weekday: "short" })} ${time}`;
}

export const KINDS = {
  light: { icon: "mdi:lightbulb-outline", color: "#e9a81c", en: "Light", de: "Licht" },
  heat: { icon: "mdi:heat-wave", color: "#e0613a", en: "Heat", de: "Wärme" },
  rain: { icon: "mdi:weather-pouring", color: "#3a8edb", en: "Rain", de: "Beregnung" },
  air: { icon: "mdi:fan", color: "#22a699", en: "Air", de: "Lüftung" },
  other: { icon: "mdi:power-socket-eu", color: "#8a93a6", en: "Other", de: "Sonstiges" },
};
export const kindOf = (device) => KINDS[device?.kind] || KINDS.other;

export const icon = (name, size = 20) =>
  name ? `<ha-icon icon="${esc(name)}" style="--mdc-icon-size:${size}px" aria-hidden="true"></ha-icon>` : "";

// Uses the color actually behind the element, because a theme can be dark without being the dark mode.
export function isDark(el, hass) {
  const bg = el ? getComputedStyle(el).backgroundColor : "";
  if (/^rgba?\(/.test(bg)) {
    const parts = bg.match(/[\d.]+/g).map(Number);
    if (parts[3] === undefined || parts[3] >= 0.5) return (0.299 * parts[0] + 0.587 * parts[1] + 0.114 * parts[2]) / 255 < 0.45;
  }
  return !!hass?.themes?.darkMode;
}

// -- texts --------------------------------------------------------------------------------------------

// The actual state of the entity, as a short word.
export function actualText(hass, device) {
  const t = tr(hass);
  if (device.actual === "on") return t("On", "An");
  if (device.actual === "off") return t("Off", "Aus");
  if (device.actual == null) return t("Missing", "Fehlt");
  return t("Unreachable", "Nicht erreichbar");
}

// One line on what the device should do and why.
export function statusText(hass, device, snap) {
  const t = tr(hass);
  const when = (iso) => fmtWhen(hass, iso, snap);
  if (device.reason === "inactive") return t(`Inactive in the ${snap?.profile?.name ?? ""} profile`, `Inaktiv im Profil ${snap?.profile?.name ?? ""}`);
  if (device.reason === "manual") {
    const until = device.override?.until;
    const state = device.on ? t("On by hand", "Von Hand an") : t("Off by hand", "Von Hand aus");
    return until ? `${state} ${t("until", "bis")} ${when(until)}` : `${state} ${t("until you resume", "bis zur Rückkehr zum Plan")}`;
  }
  const state = device.on ? t("On", "An") : t("Off", "Aus");
  if (!device.next_change) return state;
  return `${state} ${t("until", "bis")} ${when(device.next_change)}`;
}

// What is wrong right now, or null.
export function problemText(hass, device, snap) {
  const t = tr(hass);
  if (device.problem === "missing") return t("The entity does not exist", "Die Entität gibt es nicht");
  if (device.problem === "unavailable") return t("Biome switches it once it is back", "Biome schaltet, sobald es wieder da ist");
  if (device.problem === "failed") return t("Does not follow the command", "Folgt dem Befehl nicht");
  if (device.problem === "max_on") return t(`Switched off after ${device.max_on} s (longest time on)`, `Nach ${device.max_on} s abgeschaltet (maximale Einschaltdauer)`);
  if (snap?.paused && device.actual !== (device.on ? "on" : "off")) return t("Differs from the plan (paused)", "Weicht vom Plan ab (Pause)");
  if (snap?.dry_run && device.would)
    return device.would === "on" ? t("Would switch on (dry run)", "Würde einschalten (Trockenlauf)") : t("Would switch off (dry run)", "Würde ausschalten (Trockenlauf)");
  return null;
}

export function logText(hass, item) {
  const t = tr(hass);
  const name = esc(item.name ?? "");
  const st = (s) => (s === "on" ? t("on", "ein") : t("off", "aus"));
  switch (item.kind) {
    case "switched":
      return item.state === "on" ? t(`${name} switched on`, `${name} eingeschaltet`) : t(`${name} switched off`, `${name} ausgeschaltet`);
    case "would_switch":
      return item.state === "on" ? t(`${name} would switch on`, `${name} würde einschalten`) : t(`${name} would switch off`, `${name} würde ausschalten`);
    case "manual":
      return t(`${name} switched ${st(item.state)} by hand`, `${name} von Hand ${item.state === "on" ? "ein" : "aus"}geschaltet`);
    case "corrected":
      return t(`${name} switched by hand, back to the plan`, `${name} von Hand geschaltet, zurück zum Plan`);
    case "resumed":
      return t(`${name} follows the plan again`, `${name} folgt wieder dem Plan`);
    case "override_ended":
      return t(`${name}: manual switch ended`, `${name}: Handschaltung beendet`);
    case "max_on":
      return t(`${name} switched off after ${item.seconds} s, its longest time on`, `${name} nach ${item.seconds} s abgeschaltet (maximale Einschaltdauer)`);
    case "failed":
      return t(`${name} does not follow the command`, `${name} folgt dem Befehl nicht`);
    case "paused":
      return t("Paused", "Pausiert");
    case "running":
      return t("Running again", "Läuft wieder");
    case "dry_run_on":
      return t("Dry run started", "Trockenlauf gestartet");
    case "dry_run_off":
      return t("Biome switches the devices", "Biome schaltet die Geräte");
    case "profile":
      return item.manual ? t(`Profile ${esc(item.profile)} chosen by hand`, `Profil ${esc(item.profile)} von Hand gewählt`) : t(`Profile ${esc(item.profile)} by date`, `Profil ${esc(item.profile)} nach Datum`);
    case "profile_auto":
      return t("Profile follows the date again", "Profil folgt wieder dem Datum");
    default:
      return esc(item.kind);
  }
}

// -- the timeline -------------------------------------------------------------------------------------

export const TIMELINE_STYLE = `
.tl { display: grid; gap: 6px; container-type: inline-size; }
.tl-row { display: grid; grid-template-columns: minmax(150px, 220px) minmax(0, 1fr); gap: 4px 14px; align-items: center; }
.tl-axis { display: grid; grid-template-columns: minmax(150px, 220px) minmax(0, 1fr); gap: 14px; }
.tl-ticks { position: relative; height: 18px; }
.tl-tick { position: absolute; transform: translateX(-50%); font-size: 11.5px; color: var(--bio-muted); font-variant-numeric: tabular-nums; white-space: nowrap; }
.tl-tick:first-child { transform: none; }
.tl-tick:last-child { transform: translateX(-100%); }
.tl-label { display: flex; align-items: center; gap: 10px; min-width: 0; }
.tl-icon { flex: none; width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; }
.tl-text { min-width: 0; display: grid; }
.tl-name { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tl-status { font-size: 12.5px; color: var(--bio-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tl-track { position: relative; height: 30px; border-radius: 8px; background: var(--bio-night); overflow: hidden; }
.tl-daylight { position: absolute; top: 0; bottom: 0; background: var(--bio-day); }
.tl-bar { position: absolute; top: 5px; bottom: 5px; border-radius: 6px; }
.tl-manual { position: absolute; top: 3px; bottom: 3px; border-radius: 6px; border: 2px dashed color-mix(in srgb, var(--bio-ink) 55%, transparent); background: var(--bio-night); }
.tl-manual.on { background: repeating-linear-gradient(135deg, var(--kind) 0 5px, color-mix(in srgb, var(--kind) 55%, transparent) 5px 9px); }
.tl-now { position: absolute; top: 0; bottom: 0; width: 2px; margin-left: -1px; background: var(--bio-ink); pointer-events: none; }
.tl-grid { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--bio-line); opacity: .7; pointer-events: none; }
.tl-off .tl-icon { opacity: .55; }
@container (max-width: 560px) {
  .tl-row { grid-template-columns: minmax(0, 1fr); }
  .tl-axis { grid-template-columns: minmax(0, 1fr); }
  .tl-axis > :first-child { display: none; }
}
`;

const pct = (snap, iso) => {
  const t0 = new Date(snap.range[0]).getTime(),
    t1 = new Date(snap.range[1]).getTime();
  return clamp(((new Date(iso).getTime() - t0) / Math.max(1, t1 - t0)) * 100, 0, 100);
};

export const nowPct = (snap, now = Date.now()) => pct(snap, new Date(now).toISOString());

function daylight(snap) {
  return (snap.day_windows || []).map(([a, b]) => `<div class="tl-daylight" style="left:${pct(snap, a)}%;width:${pct(snap, b) - pct(snap, a)}%"></div>`).join("");
}

function grid() {
  return [6, 12, 18].map((h) => `<div class="tl-grid" style="left:${(h / 24) * 100}%"></div>`).join("");
}

// The bars of one device: one per window, faded where the light dims up or down.
function bars(snap, device) {
  const color = kindOf(device).color;
  return (device.windows || [])
    .map((w) => {
      const a = pct(snap, w.span[0]),
        b = pct(snap, w.span[1]);
      let bg = color;
      if (w.ramp > 0) {
        const full = new Date(w.end) - new Date(w.start);
        const r = Math.min(50, ((w.ramp * 60000) / Math.max(1, full)) * 100);
        bg = `linear-gradient(90deg, color-mix(in srgb, ${color} 25%, transparent), ${color} ${r}%, ${color} ${100 - r}%, color-mix(in srgb, ${color} 25%, transparent))`;
      }
      return `<div class="tl-bar" style="left:${a}%;width:${Math.max(0.4, b - a)}%;background:${bg}" title="${esc(w.start)} – ${esc(w.end)}"></div>`;
    })
    .join("");
}

// A manual override from now until it ends: hatched when on, dashed outline when off.
function manualBar(snap, device, now) {
  if (!device.override) return "";
  const a = nowPct(snap, now);
  const b = device.override.until ? pct(snap, device.override.until) : 100;
  if (b <= a) return "";
  return `<div class="tl-manual ${device.on ? "on" : ""}" style="left:${a}%;width:${b - a}%;--kind:${kindOf(device).color}"></div>`;
}

// The hour labels above the rows.
export function axisHTML(hass, snap) {
  const ticks = [0, 3, 6, 9, 12, 15, 18, 21, 24]
    .map((h) => `<span class="tl-tick" style="left:${(h / 24) * 100}%">${String(h).padStart(2, "0")}</span>`)
    .join("");
  return `<div class="tl-axis"><div></div><div class="tl-ticks">${ticks}</div></div>`;
}

// One row per device. extra(device) adds HTML below the status line (buttons on the page).
export function rowsHTML(hass, snap, { extra = () => "", now = Date.now() } = {}) {
  const n = nowPct(snap, now);
  return (snap.devices || [])
    .map((d) => {
      const kind = kindOf(d);
      const off = d.reason === "inactive";
      return `<div class="tl-row ${off ? "tl-off" : ""}" data-device="${esc(d.id)}">
        <div class="tl-label">
          <div class="tl-icon" style="background:color-mix(in srgb, ${kind.color} 18%, transparent);color:${kind.color}">${icon(kind.icon, 20)}</div>
          <div class="tl-text"><span class="tl-name">${esc(d.name)}</span><span class="tl-status">${esc(statusText(hass, d, snap))}</span>${extra(d)}</div>
        </div>
        <div class="tl-track">${daylight(snap)}${grid()}${bars(snap, d)}${manualBar(snap, d, now)}<div class="tl-now" style="left:${n}%"></div></div>
      </div>`;
    })
    .join("");
}
