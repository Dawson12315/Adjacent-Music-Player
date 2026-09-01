import { API_BASE_URL } from "../config";
import { apiClient } from "./apiClient";
import { normalizeTrack, normalizeTracks } from "./normalize";

/**
 * `GET /api/tracks` returns a bare array when `limit` is omitted and a paginated
 * envelope when it is supplied. The app loads the whole library, so this helper always
 * takes the bare-array path; `listPage` covers the envelope for future use.
 */
export async function listTracks(options) {
  const data = await apiClient.get("/api/tracks", options);
  return normalizeTracks(data, { metadataComplete: true });
}

export async function listTracksPage({ limit = 100, offset = 0, search, sortBy, section } = {}) {
  const data = await apiClient.get("/api/tracks", {
    params: { limit, offset, search, sort_by: sortBy, section },
  });

  return {
    items: normalizeTracks(data.items, { metadataComplete: true }),
    total: data.total,
    limit: data.limit,
    offset: data.offset,
    hasMore: data.has_more,
  };
}

export function getTrackCount() {
  return apiClient.get("/api/tracks/count");
}

/** The URL the audio element points at. Auth rides on the cookie. */
export function streamUrl(trackId) {
  return `${API_BASE_URL}/api/tracks/${trackId}/stream`;
}

/**
 * `PATCH /api/tracks/{id}` is a full replace, not a merge: any field omitted is written
 * as null, and a `genres` array replaces every genre row for the track. `genres` is
 * therefore only sent when the caller actually has authoritative genre data — see
 * normalize.js for why that distinction matters.
 */
export async function updateTrack(trackId, { title, artist, album, genres }) {
  const payload = {
    title,
    artist: artist || null,
    album: album || null,
  };

  if (genres !== undefined) {
    payload.genres = genres;
  }

  const data = await apiClient.patch(`/api/tracks/${trackId}`, payload);
  return normalizeTrack(data, { metadataComplete: true });
}

export function purgeTracks() {
  return apiClient.delete("/api/tracks/purge");
}

/** Returns raw ORM rows: no genres, no artists, no artwork. */
export async function getSimilarTracks(trackId, options) {
  const data = await apiClient.get(`/api/tracks/${trackId}/similar`, options);
  return normalizeTracks(data, { metadataComplete: false });
}

export function updateNowPlaying(trackId) {
  return apiClient.post(`/api/tracks/${trackId}/lastfm/now-playing`);
}

export function scrobble(trackId) {
  return apiClient.post(`/api/tracks/${trackId}/lastfm/scrobble`);
}
