/**
 * Which zone the listener's days are counted in.
 *
 * The server buckets Insights in the account's saved zone, else the zone a
 * request hints, else its own. The browser's zone is the hint.
 */

/** The browser's IANA zone, or null where the runtime cannot say. */
export function browserTimeZone() {
  try {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return typeof zone === "string" && zone.includes("/") ? zone : null;
  } catch {
    return null;
  }
}

/** Every zone the browser knows, or a short list where it will not say. */
export function timeZoneChoices() {
  try {
    const all = Intl.supportedValuesOf("timeZone");
    if (Array.isArray(all) && all.length) return all;
  } catch {
    // Older browsers: fall through to the curated list.
  }
  return FALLBACK_ZONES;
}

/** "America/Los_Angeles" reads as "Los Angeles (America)". */
export function zoneLabel(name) {
  if (!name) return "";
  const [region, ...rest] = String(name).split("/");
  if (!rest.length) return name;
  return `${rest.join(" / ").replace(/_/g, " ")} (${region})`;
}

const FALLBACK_ZONES = [
  "Pacific/Honolulu", "America/Anchorage", "America/Los_Angeles", "America/Denver",
  "America/Phoenix", "America/Chicago", "America/New_York", "America/Toronto",
  "America/Mexico_City", "America/Bogota", "America/Sao_Paulo", "America/Argentina/Buenos_Aires",
  "Atlantic/Reykjavik", "Europe/London", "Europe/Dublin", "Europe/Lisbon", "Europe/Paris",
  "Europe/Berlin", "Europe/Madrid", "Europe/Rome", "Europe/Amsterdam", "Europe/Stockholm",
  "Europe/Warsaw", "Europe/Athens", "Europe/Helsinki", "Europe/Istanbul", "Europe/Moscow",
  "Africa/Cairo", "Africa/Johannesburg", "Africa/Lagos", "Africa/Nairobi", "Asia/Dubai",
  "Asia/Karachi", "Asia/Kolkata", "Asia/Dhaka", "Asia/Bangkok", "Asia/Jakarta",
  "Asia/Singapore", "Asia/Hong_Kong", "Asia/Shanghai", "Asia/Manila", "Asia/Seoul",
  "Asia/Tokyo", "Australia/Perth", "Australia/Adelaide", "Australia/Brisbane",
  "Australia/Sydney", "Australia/Melbourne", "Pacific/Auckland", "UTC",
];
