/**
 * The themes the app can wear, and when.
 *
 * A theme is a palette: an accent in five steps, a bias for the near-black
 * grounds, and the ten gradients the generated artwork draws from. The CSS
 * for each lives in tokens.css under `:root[data-theme]`; this file is the
 * catalogue — ids, names, calendar windows, the duck's dress — shared word
 * for word with the phone, so both clients turn on the same day.
 *
 * Adjacent is the default and the look the app ships with. There is no
 * green theme and no free colour: the list is the whole menu, and a test
 * (noGreen.test.js) refuses any palette that reaches into the green arc.
 */

export const DEFAULT_THEME = "adjacent";

/** Year-round colours, then the eight that follow the calendar. */
export const THEMES = [
  { id: "adjacent", name: "Adjacent", kind: "year", accent: "#2F7CFF", ground: "#0A0C11", dress: null, blurb: "The blue it ships with." },
  { id: "ultraviolet", name: "Ultraviolet", kind: "year", accent: "#8A6BFF", ground: "#0B0A12", dress: null, blurb: "Violet on violet-black." },
  { id: "rosewood", name: "Rosewood", kind: "year", accent: "#FF5C8A", ground: "#120A0D", dress: null, blurb: "Rose on wine-black." },
  { id: "ember", name: "Ember", kind: "year", accent: "#FF7A45", ground: "#120D0A", dress: null, blurb: "Coral on warm black." },
  { id: "graphite", name: "Graphite", kind: "year", accent: "#E8ECF5", ground: "#0A0B0E", dress: null, blurb: "Off-white on neutral black; the duck is the only colour." },
  { id: "spring", name: "Spring", kind: "season", accent: "#F07CB0", ground: "#0E0A12", dress: "crown", from: [3, 20], to: [6, 20], blurb: "Blossom, lilac and sky." },
  { id: "summer", name: "Summer", kind: "season", accent: "#3FA7FF", ground: "#0A0D14", dress: "shades", from: [6, 21], to: [9, 21], blurb: "Sea blue, coral and sun." },
  { id: "autumn", name: "Autumn", kind: "season", accent: "#E8742E", ground: "#110C09", dress: "scarf", from: [9, 22], to: [11, 30], blurb: "Rust, amber and plum." },
  { id: "halloween", name: "Halloween", kind: "holiday", accent: "#FF7A1A", ground: "#0C0813", dress: "witch", from: [10, 24], to: [10, 31], blurb: "Pumpkin on violet-black." },
  { id: "winter", name: "Winter", kind: "season", accent: "#7FB4FF", ground: "#090C12", dress: "beanie", from: [12, 1], to: [3, 19], blurb: "Ice, steel and silver." },
  { id: "festive", name: "Festive", kind: "holiday", accent: "#E8415A", ground: "#120A0C", dress: "santa", from: [12, 14], to: [12, 26], blurb: "Crimson and gold." },
  { id: "newyear", name: "New Year", kind: "holiday", accent: "#FFD166", ground: "#080A14", dress: "party", from: [12, 31], to: [1, 1], blurb: "Gold on midnight." },
  { id: "valentine", name: "Valentine's", kind: "holiday", accent: "#FF4F79", ground: "#120A0E", dress: "heart", from: [2, 10], to: [2, 14], blurb: "Rose and blush." },
];

export const THEME_IDS = THEMES.map((theme) => theme.id);
const BY_ID = Object.fromEntries(THEMES.map((theme) => [theme.id, theme]));

export function themeById(id) {
  return BY_ID[id] || BY_ID[DEFAULT_THEME];
}

export function isThemeId(id) {
  return typeof id === "string" && Object.prototype.hasOwnProperty.call(BY_ID, id);
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "24 Oct – 31 Oct", for a theme with a window; "" for a year-round one. */
export function windowLabel(theme) {
  if (!theme?.from) return "";
  const [fm, fd] = theme.from;
  const [tm, td] = theme.to;
  return `${fd} ${MONTHS[fm - 1]} – ${td} ${MONTHS[tm - 1]}`;
}

function inWindow(theme, month, day) {
  if (!theme.from) return false;
  const [fm, fd] = theme.from;
  const [tm, td] = theme.to;
  const value = month * 100 + day;
  const start = fm * 100 + fd;
  const end = tm * 100 + td;
  // A window that wraps the year end (Winter, New Year) is two spans.
  return start <= end ? value >= start && value <= end : value >= start || value <= end;
}

/**
 * The theme the calendar picks for a date: a holiday first, else the
 * season. `southern` moves the four seasons by six months; holidays keep
 * their dates. Always answers — the seasons cover the whole year.
 */
export function themeForDate(date, { southern = false } = {}) {
  const month = date.getMonth() + 1;
  const day = date.getDate();
  const holiday = THEMES.find((theme) => theme.kind === "holiday" && inWindow(theme, month, day));
  if (holiday) return holiday;
  const seasonMonth = southern ? ((month + 5) % 12) + 1 : month;
  return THEMES.find((theme) => theme.kind === "season" && inWindow(theme, seasonMonth, day)) || BY_ID[DEFAULT_THEME];
}

/**
 * What the app wears, from the account's preference and the date: the
 * calendar's theme when the seasons are followed, else the chosen one.
 */
export function effectiveTheme({ theme, seasonal = false, southern = false } = {}, date = new Date()) {
  if (seasonal) return themeForDate(date, { southern });
  return themeById(theme);
}

/** One line for the day itself, never for a whole season. */
export function dayLineFor(date = new Date()) {
  const month = date.getMonth() + 1;
  const day = date.getDate();
  if (month === 10 && day === 31) return "Happy Halloween.";
  if ((month === 12 && day === 31) || (month === 1 && day === 1)) return "Happy New Year.";
  if (month === 2 && day === 14) return "Happy Valentine's Day.";
  return "";
}

/** The next local midnight after `date`, when a window may begin. */
export function nextMidnight(date = new Date()) {
  const next = new Date(date);
  next.setHours(24, 0, 0, 0);
  return next;
}

/** What the duck can wear; the vectors live in DuckMark. */
export const DRESS_IDS = ["crown", "shades", "scarf", "witch", "beanie", "santa", "party", "heart"];

/** The theme the account asks for, from the user record the server sends. */
export function preferencesOf(user) {
  return {
    theme: isThemeId(user?.theme) ? user.theme : DEFAULT_THEME,
    seasonal: Boolean(user?.theme_seasonal),
    southern: Boolean(user?.theme_southern),
  };
}

export const THEME_STORAGE_KEY = "adjacent.theme";
