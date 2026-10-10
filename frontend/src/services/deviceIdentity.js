/**
 * This browser's identity as a playback device: a stable id and a readable
 * name. The id lives in localStorage, so it is per-browser and survives a
 * sign-out; two tabs of the same browser share it and so count as one device,
 * the way Spotify's web player treats tabs.
 *
 * The naming is a pure function of the user-agent string so it can be tested.
 */

const DEVICE_ID_KEY = "adjacent_device_id";
const DEVICE_NAME_KEY = "adjacent_device_name";

function newId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

let cachedId = null;

/** The stable device id, minted and stored the first time it is asked for. */
export function getDeviceId() {
  if (cachedId) return cachedId;
  try {
    const stored = localStorage.getItem(DEVICE_ID_KEY);
    if (stored) {
      cachedId = stored;
      return stored;
    }
  } catch {
    // Storage blocked (private mode): a session-only id still works.
  }
  const fresh = newId();
  cachedId = fresh;
  try {
    localStorage.setItem(DEVICE_ID_KEY, fresh);
  } catch {
    // Not persisted; a new id comes next load.
  }
  return fresh;
}

/** "Chrome on Mac", "Safari on iPad", "Firefox on Windows" — from the UA. */
export function browserNameFrom(userAgent = "", platformHint = "") {
  const ua = String(userAgent);
  const browser =
    /Edg\//.test(ua) ? "Edge" :
    /OPR\//.test(ua) || /Opera/.test(ua) ? "Opera" :
    /Firefox\//.test(ua) ? "Firefox" :
    /Chrome\//.test(ua) ? "Chrome" :
    /Safari\//.test(ua) ? "Safari" :
    "Browser";

  const platform = String(platformHint || ua);
  const os =
    /iPad/.test(ua) ? "iPad" :
    /iPhone/.test(ua) ? "iPhone" :
    /Android/.test(ua) ? "Android" :
    /Mac/i.test(platform) ? "Mac" :
    /Win/i.test(platform) ? "Windows" :
    /Linux|X11/i.test(platform) ? "Linux" :
    "";

  return os ? `${browser} on ${os}` : browser;
}

/** The name the pickers show: the owner's override, else the browser's own. */
export function getDeviceName() {
  try {
    const override = localStorage.getItem(DEVICE_NAME_KEY);
    if (override && override.trim()) return override.trim().slice(0, 80);
  } catch {
    // Fall through to the computed name.
  }
  const nav = typeof navigator !== "undefined" ? navigator : {};
  return browserNameFrom(nav.userAgent, nav.platform);
}

/** Save a name the owner typed in Settings; empty clears to the default. */
export function setDeviceNameOverride(name) {
  const trimmed = (name || "").trim().slice(0, 80);
  try {
    if (trimmed) localStorage.setItem(DEVICE_NAME_KEY, trimmed);
    else localStorage.removeItem(DEVICE_NAME_KEY);
  } catch {
    // Non-fatal.
  }
}

/** Everything the `hello` frame needs. */
export function describeDevice() {
  const nav = typeof navigator !== "undefined" ? navigator : {};
  return {
    deviceId: getDeviceId(),
    name: getDeviceName(),
    kind: "web",
    platform: nav.platform || "web",
    appVersion: "web",
  };
}
