/**
 * Single source of truth for the API origin.
 *
 * In production `frontend/Dockerfile` writes `/config.js` into the nginx docroot at
 * container start, setting `window.APP_CONFIG`. `index.html` loads that file as a
 * classic script before the app bundle, so the global is always set by the time this
 * module is evaluated. In development no value is injected and we fall back to the
 * backend's default port on the current host.
 *
 * Three shapes are accepted:
 *
 *   ""            unset — the LAN default, API on port 8000 of the current host
 *   "/"           same origin, for a reverse proxy that serves both the app and
 *                 /api from one hostname
 *   "http://…"    an explicit origin, for the two-port LAN layout
 *
 * The same-origin form is the one to use behind a domain, and until now it could
 * not be expressed: an empty value fell through to the port-8000 guess, so a site
 * on https://example.com had its API pointed at https://example.com:8000 or at a
 * LAN IP. Both fail from outside the network, and the second is also blocked as
 * mixed content — which the browser reports as a request that simply hangs.
 */
function resolveApiBaseUrl() {
  const configured = String(window.APP_CONFIG?.API_BASE_URL ?? "").trim();

  // Trailing slashes are stripped rather than rejected: every path this is
  // joined to already begins with one, and "/" is how you say "same origin".
  const trimmed = configured.replace(/\/+$/, "");

  if (trimmed) return trimmed;

  // An explicit "/" normalises to "" and means same origin — relative URLs.
  if (configured) return "";

  return `${window.location.protocol}//${window.location.hostname}:8000`;
}

export const API_BASE_URL = resolveApiBaseUrl();

/**
 * Build an absolute URL for an uploaded asset.
 *
 * Artwork paths are stored by the backend already root-relative and already carrying
 * their `/uploads` (or legacy `/legacy-uploads`) prefix, and are served from the API
 * origin outside the `/api` namespace. Returns an empty string for missing paths so
 * callers can test truthiness without a null check.
 */
export function artworkUrl(path) {
  if (!path) {
    return "";
  }

  if (/^https?:\/\//i.test(path)) {
    return path;
  }

  return `${API_BASE_URL}${path}`;
}
