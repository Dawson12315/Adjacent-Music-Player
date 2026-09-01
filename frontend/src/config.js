/**
 * Single source of truth for the API origin.
 *
 * In production `frontend/Dockerfile` writes `/config.js` into the nginx docroot at
 * container start, setting `window.APP_CONFIG`. `index.html` loads that file as a
 * classic script before the app bundle, so the global is always set by the time this
 * module is evaluated. In development no value is injected and we fall back to the
 * backend's default port on the current host.
 */
export const API_BASE_URL =
  window.APP_CONFIG?.API_BASE_URL ||
  `${window.location.protocol}//${window.location.hostname}:8000`;

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
