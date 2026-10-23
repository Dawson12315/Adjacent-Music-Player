import { apiClient } from "./apiClient";
import { normalizeTrack } from "./normalize";

/**
 * Radio stations: a seed, a memory, and "what next" in batches.
 *
 * The server owns the station and what it has played; the browser asks for
 * the next batch when its queue runs out and reports each track as it
 * starts. Needs a server at API version 10 or later; an older one answers
 * 404 to every route here.
 */

export const RADIO_API_VERSION = 10;

/**
 * The listener's station for `seed`, made the first time and found after
 * that. `seed` is `{ seed_type: "track", seed_track_id }`, `{ seed_type:
 * "album", seed_album, seed_album_artist }` or `{ seed_type: "artist",
 * seed_artist }`.
 */
export function createStation(seed, options) {
  return apiClient.post("/api/radio/stations", seed, options);
}

/** Recent stations, the one played last first. */
export function getStations({ limit = 12, signal } = {}) {
  return apiClient.get("/api/radio/stations", { params: { limit }, signal });
}

export function getStation(stationId, options) {
  return apiClient.get(`/api/radio/stations/${stationId}`, options);
}

/**
 * The station's next batch. `excludeIds` is what the browser already holds,
 * so the batch does not repeat it before the plays are reported. Answers
 * `{ station, tracks, thin }` with the tracks normalised like any other list.
 */
export async function getStationNext(stationId, { limit = 20, excludeIds = [], signal } = {}) {
  const exclude = (excludeIds || []).filter((id) => id != null).join(",");
  const params = { limit };
  if (exclude) params.exclude_track_ids = exclude;
  const data = await apiClient.get(`/api/radio/stations/${stationId}/next`, { params, signal });
  return {
    station: data?.station ?? null,
    tracks: (data?.tracks || []).map((track) => ({ ...normalizeTrack(track), reason: track.reason ?? null })),
    thin: Boolean(data?.thin),
  };
}

/** What the station played; those stay out of the next two hundred. */
export function reportStationPlays(stationId, trackIds) {
  return apiClient.post(`/api/radio/stations/${stationId}/played`, {
    track_ids: (trackIds || []).filter((id) => id != null),
  });
}

export function deleteStation(stationId) {
  return apiClient.delete(`/api/radio/stations/${stationId}`);
}
