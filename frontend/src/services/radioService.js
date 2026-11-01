import { apiClient } from "./apiClient";
import { normalizeTrack } from "./normalize";

/**
 * Radio stations: a seed, a memory, and "what next" in batches.
 *
 * The server owns the station, what it has played and what it has handed
 * out; the browser asks for the next batch as its queue runs low and
 * reports each track as it starts playing. Radio needs a server at API
 * version 10 or later; feedback (more like this, not this one, less of
 * this artist) and the `reach` of a batch need 12.
 */

export const RADIO_API_VERSION = 10;
export const RADIO_FEEDBACK_API_VERSION = 12;

function stationTracks(rows) {
  return (rows || []).map((track) => ({ ...normalizeTrack(track), reason: track.reason ?? null }));
}

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
 * `{ station, tracks, thin, reach }`: `thin` when the seed's corner of the
 * library could not fill the batch, `reach` how far the station went for
 * the rest ("genre", "artist", "listener", "library", "again"). A 410 means
 * the seed is no longer in the library.
 */
export async function getStationNext(stationId, { limit = 20, excludeIds = [], signal } = {}) {
  const exclude = (excludeIds || []).filter((id) => id != null).join(",");
  const params = { limit };
  if (exclude) params.exclude_track_ids = exclude;
  const data = await apiClient.get(`/api/radio/stations/${stationId}/next`, { params, signal });
  return {
    station: data?.station ?? null,
    tracks: stationTracks(data?.tracks),
    thin: Boolean(data?.thin),
    reach: data?.reach ?? null,
  };
}

/**
 * Where the station was left: its lineup from the track the listener got
 * to, onward. `resumable` is false when the station has never played or it
 * has been ten days since it last did; an older server answers 404.
 */
export async function getStationLineup(stationId, options) {
  const data = await apiClient.get(`/api/radio/stations/${stationId}/lineup`, options);
  return {
    station: data?.station ?? null,
    tracks: stationTracks(data?.tracks),
    resumable: Boolean(data?.resumable),
    savedAt: data?.saved_at ?? null,
  };
}

/** What the station played; those stay out of the next two hundred. */
export function reportStationPlays(stationId, trackIds) {
  return apiClient.post(`/api/radio/stations/${stationId}/played`, {
    track_ids: (trackIds || []).filter((id) => id != null),
  });
}

/**
 * What the listener says about a track on the station. `kind` is "more"
 * (the track joins the seeds), "less" (it stays off the station) or
 * "less_artist" (the artist leaves the neighbours; 409 for the station's
 * own artist). Answers the station's feedback as it now stands.
 */
export function giveStationFeedback(stationId, trackId, kind) {
  return apiClient.post(`/api/radio/stations/${stationId}/feedback`, { track_id: trackId, kind });
}

export function takeBackStationFeedback(stationId, trackId, kind) {
  return apiClient.delete(`/api/radio/stations/${stationId}/feedback`, { params: { track_id: trackId, kind } });
}

export function deleteStation(stationId) {
  return apiClient.delete(`/api/radio/stations/${stationId}`);
}
