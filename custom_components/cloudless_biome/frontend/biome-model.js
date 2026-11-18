// The plan arithmetic of the Biome page: the same rules as the backend (schedule.py, astro.py), for the draft being edited.

export const DAY = 1440;
export const SNAP = 5; // minutes

export const toMin = (value) => {
  if (typeof value === "number") return ((Math.round(value) % DAY) + DAY) % DAY;
  const [h, m] = String(value || "0:0").split(":").map(Number);
  return ((((h || 0) * 60 + (m || 0)) % DAY) + DAY) % DAY;
};
export const clock = (min) => {
  const m = ((Math.round(min) % DAY) + DAY) % DAY;
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
};
export const snap = (min) => Math.round(min / SNAP) * SNAP;
export const signed = (n) => (n > 0 ? `+${n}` : n < 0 ? `−${-n}` : "±0");
export const clone = (x) => JSON.parse(JSON.stringify(x));
export const pct = (min) => (min / DAY) * 100;
export const hours = (min) => {
  const h = Math.floor(min / 60),
    m = Math.round(min % 60);
  return m ? `${h} h ${m} min` : `${h} h`;
};

export const daySpan = () => ({ on: { ref: "start", value: 0 }, off: { ref: "end", value: 0 }, every: null, pulse: null });
export const DEFAULT_SETTING = { active: true, mode: "windows", spans: [daySpan()], brightness: null, ramp: 0 };
export const DEFAULT_MAX_ON = { rain: 30 };

export const EVENTS = ["date", "dst_start", "dst_end", "spring", "summer", "autumn", "winter"];

// The setting of a device in a profile, following copy_from when the profile is new to the device.
export function settingOf(cfg, device, profile) {
  const seen = new Set();
  let p = profile;
  while (p && !seen.has(p.id)) {
    if (device.profiles?.[p.id]) return { ...clone(DEFAULT_SETTING), ...clone(device.profiles[p.id]) };
    seen.add(p.id);
    p = cfg.profiles.find((x) => x.id === p.copy_from);
  }
  const first = Object.values(device.profiles || {})[0];
  return { ...clone(DEFAULT_SETTING), ...clone(first || {}) };
}

// -- the sun -------------------------------------------------------------------------------------------

const rad = (d) => (d * Math.PI) / 180;
const dayOfYear = (d) => Math.round((Date.UTC(d.y, d.m - 1, d.d) - Date.UTC(d.y, 0, 0)) / 86400000);
export const addDays = (d, n) => {
  const x = new Date(Date.UTC(d.y, d.m - 1, d.d + n));
  return { y: x.getUTCFullYear(), m: x.getUTCMonth() + 1, d: x.getUTCDate() };
};

export function naturalLength(day, latitude) {
  const n = dayOfYear(day);
  const decl = rad(23.44) * Math.sin((2 * Math.PI * (284 + n)) / 365);
  const phi = rad(Math.max(-89.9, Math.min(89.9, latitude)));
  const cos = (Math.sin(rad(-0.833)) - Math.sin(phi) * Math.sin(decl)) / (Math.cos(phi) * Math.cos(decl));
  if (cos <= -1) return DAY;
  if (cos >= 1) return 0;
  return ((2 * ((Math.acos(cos) * 180) / Math.PI)) / 15) * 60;
}

export function solarNoon(day, longitude, tz) {
  const n = dayOfYear(day);
  const b = (2 * Math.PI * (n - 81)) / 364;
  const eot = 9.87 * Math.sin(2 * b) - 7.53 * Math.cos(b) - 1.5 * Math.sin(b);
  const ms = Date.UTC(day.y, day.m - 1, day.d) + (720 - 4 * longitude - eot) * 60000;
  const parts = new Intl.DateTimeFormat("en-GB", { timeZone: tz, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(new Date(ms));
  const get = (t) => Number(parts.find((x) => x.type === t)?.value || 0);
  return get("hour") * 60 + get("minute");
}

// Where a natural day takes its sun from, and its limits, with the defaults of the backend.
export function naturalOf(settings, snap) {
  const n = settings?.natural || {};
  return {
    latitude: n.latitude ?? snap?.latitude ?? 50,
    longitude: n.longitude ?? snap?.longitude ?? 10,
    min: n.min_length ?? 600,
    max: n.max_length ?? 840,
    center: n.center ? toMin(n.center) : null,
    factor: n.factor ?? 1,
    invert: !!n.invert,
  };
}

// Start and length in minutes of a profile's biome day on a day {y, m, d}.
export function dayTimes(profile, day, settings, snap) {
  if (profile.day_mode !== "natural") return { start: toMin(profile.day_start), len: (toMin(profile.day_end) - toMin(profile.day_start) + DAY) % DAY, natural: false };
  const n = naturalOf(settings, snap);
  const sunDay = n.invert ? addDays(day, 182) : day;
  let len = 720 + (naturalLength(sunDay, n.latitude) - 720) * n.factor;
  len = Math.max(0, Math.min(DAY - 1, Math.max(n.min, Math.min(n.max, len))));
  const center = n.center ?? solarNoon(day, n.longitude, snap?.time_zone);
  return { start: Math.round(center - len / 2), len: Math.round(len), natural: true, raw: naturalLength(sunDay, n.latitude) };
}

// -- windows -------------------------------------------------------------------------------------------

// A window's start and end in minutes from midnight; the end may reach into the next day.
export function spanMinutes(span, start, len) {
  const edge = (e) => (e.ref === "clock" ? toMin(e.value) : e.ref === "start" ? start + Number(e.value || 0) : start + len + Number(e.value || 0));
  const clockOn = span.on.ref === "clock",
    clockOff = span.off.ref === "clock";
  if (!(clockOn && clockOff) && !len) return null;
  let on = edge(span.on),
    off = edge(span.off);
  if (clockOn && !clockOff && on > off) on -= DAY;
  if (off <= on) {
    if (!(clockOn || clockOff)) return null;
    off += DAY;
  }
  if (off - on > DAY) return null;
  return { on, off };
}

// All windows of a device in a profile: [{on, off, index, span}], plus the pulses of interval windows.
export function windowsOf(cfg, device, profile, times) {
  const s = settingOf(cfg, device, profile);
  if (!s.active) return { s, list: [] };
  if (s.mode === "always") return { s, list: [{ on: 0, off: DAY, index: -1, span: null }] };
  const list = [];
  (s.spans || []).forEach((span, index) => {
    const m = spanMinutes(span, times.start, times.len);
    if (!m) return;
    const pulses = [];
    if (span.every && span.pulse) for (let t = m.on; t < m.off && pulses.length < 2000; t += span.every) pulses.push([t, Math.min(t + span.pulse / 60, m.off)]);
    list.push({ ...m, index, span, pulses });
  });
  return { s, list };
}

// Pieces of a window on today's 0-1440 axis, including the parts that belong to yesterday or tomorrow.
export function pieces(on, off) {
  const out = [];
  for (const shift of [-DAY, 0, DAY]) {
    const a = Math.max(0, on + shift),
      b = Math.min(DAY, off + shift);
    if (b > a) out.push({ a, b, shift, startHere: on + shift >= 0 && on + shift <= DAY, endHere: off + shift >= 0 && off + shift <= DAY });
  }
  return out;
}

// A first guess at the kind from the entity's name.
export function guessKind(entityId, name) {
  const s = `${entityId} ${name}`.toLowerCase();
  if (/heiz|wärme|waerme|heat|warm|basking/.test(s)) return "heat";
  if (/regen|beregn|nebel|sprüh|spruh|rain|mist|fog|spray/.test(s)) return "rain";
  if (/lüft|luft|fan|vent/.test(s)) return "air";
  if (entityId.startsWith("light.") || /licht|lamp|leucht|light|led|uv|spot/.test(s)) return "light";
  return "other";
}

// The longest time a device may stay on, in seconds; 0 means no limit.
export function limitOf(device, settings) {
  if (device.max_on != null) return Math.max(0, Number(device.max_on));
  const kinds = settings?.max_on ?? DEFAULT_MAX_ON;
  return Math.max(0, Number(kinds[device.kind] || 0));
}
