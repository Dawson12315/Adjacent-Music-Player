import { apiClient } from "./apiClient";

/**
 * The shape of the app settings row, in one place. `PUT /api/settings` is a full
 * replace — every optional field left out is written as null — so both the read and the
 * write go through these mappers to guarantee the round trip keeps every field.
 * Dropping two of them on the way back in is what previously let a second save silently
 * turn off scheduled Last.fm enrichment.
 *
 * The two secrets are the exception: the API is write-only for them and reports only
 * `*_set` booleans. `lastfm_api_secret` here is a local input buffer — empty means
 * "leave the stored secret alone" and maps to null on save.
 */
export function toAppSettings(data) {
  return {
    cleanup_enabled: Boolean(data.cleanup_enabled),
    cleanup_time: data.cleanup_time || "",
    scan_enabled: Boolean(data.scan_enabled),
    scan_time: data.scan_time || "",
    lastfm_enrichment_enabled: Boolean(data.lastfm_enrichment_enabled),
    lastfm_enrichment_time: data.lastfm_enrichment_time || "",
    lastfm_api_key: data.lastfm_api_key || "",
    lastfm_api_secret: "",
    lastfm_api_secret_set: Boolean(data.lastfm_api_secret_set),
    lastfm_username: data.lastfm_username || "",
    lastfm_session_key_set: Boolean(data.lastfm_session_key_set),
  };
}

export async function getSettings(options) {
  const data = await apiClient.get("/api/settings", options);
  return toAppSettings(data);
}

export async function saveSettings(settings) {
  const data = await apiClient.put("/api/settings", {
    cleanup_enabled: settings.cleanup_enabled,
    cleanup_time: settings.cleanup_time || null,
    scan_enabled: settings.scan_enabled,
    scan_time: settings.scan_time || null,
    lastfm_enrichment_enabled: settings.lastfm_enrichment_enabled,
    lastfm_enrichment_time: settings.lastfm_enrichment_time || null,
    lastfm_api_key: settings.lastfm_api_key?.trim() || null,
    // null keeps the stored secret; the session key is server-managed only.
    lastfm_api_secret: settings.lastfm_api_secret?.trim() || null,
    lastfm_username: settings.lastfm_username || null,
  });

  return toAppSettings(data);
}

/* ---------- library maintenance ---------- */

/**
 * Starts a background scan; resolves to { started, reason }. The scan itself can run
 * for a long time on a big library — poll getScanProgress() to follow it.
 */
export function scanLibrary(limit = 100000) {
  return apiClient.post("/api/scan", undefined, { params: { limit }, noStore: true });
}

/** In-memory on the server: { is_running, files_seen, added, last_result, error }. */
export function getScanProgress(options) {
  return apiClient.get("/api/scan/progress", { ...options, noStore: true });
}

export function runCleanup() {
  return apiClient.post("/api/maintenance/cleanup");
}

/* ---------- Last.fm ---------- */

export function getLastfmAuthUrl(callbackUrl) {
  return apiClient.get("/api/settings/lastfm/auth-url", {
    params: { callback_url: callbackUrl },
  });
}

export async function createLastfmSession(token) {
  const data = await apiClient.post("/api/settings/lastfm/session", undefined, {
    params: { token },
  });

  return toAppSettings(data);
}

export function startLastfmEnrichment() {
  return apiClient.post("/api/settings/lastfm/enrich", undefined, { noStore: true });
}

export function stopLastfmEnrichment() {
  return apiClient.post("/api/settings/lastfm/stop", undefined, { noStore: true });
}

/** In-memory on the server, so it resets on restart. Poll-friendly. */
export function getLastfmProgress(options) {
  return apiClient.get("/api/settings/lastfm/progress", { ...options, noStore: true });
}

export function getLastfmReadiness(options) {
  return apiClient.get("/api/settings/lastfm/readiness", { ...options, noStore: true });
}

/* ---------- MusicBrainz ---------- */

export function resumeMusicbrainzBackfill() {
  return apiClient.post("/api/settings/musicbrainz/resume");
}

/* ---------- database / multi-user ---------- */

export function getDatabaseStatus(options) {
  return apiClient.get("/api/settings/database", { ...options, noStore: true });
}

export function testDatabaseConnection(connection) {
  return apiClient.post("/api/settings/database/test", connection);
}

export function startDatabaseMigration(connection) {
  return apiClient.post("/api/settings/database/migrate", connection);
}

export function getDatabaseMigrationProgress(options) {
  return apiClient.get("/api/settings/database/migration", {
    ...options,
    noStore: true,
  });
}

export function pingHealth(options) {
  return apiClient.get("/api/health", { ...options, noStore: true });
}
