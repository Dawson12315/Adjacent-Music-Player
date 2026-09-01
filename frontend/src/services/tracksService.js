import { API_BASE_URL } from "../config";
import { apiClient } from "./apiClient";
import { normalizeTrack, normalizeTracks } from "./normalize";

/**
 * `GET /api/tracks` returns a bare array when `limit` is omitted and a paginated
 * envelope when it is supplied.
 *
 * The app always supplies one now. Loading the whole library meant 21 MB of uncompressed
 * JSON on every startup for a 36,534-track collection, parsed into 36,534 objects and
 * then filtered in JavaScript on every keystroke.
 */
export async function listTracksPage({
  limit = 60,
  offset = 0,
  search,
  sortBy = "artist",
  section,
  signal,
} = {}) {
  const data = await apiClient.get("/api/tracks", {
    params: { limit, offset, search: search || undefined, sort_by: sortBy, section },
    signal,
  });

  return {
    items: normalizeTracks(data.items, { metadataComplete: true }),
    total: data.total,
    offset: data.offset,
    hasMore: data.has_more,
  };
}

export function getTrackCount(options) {
  return apiClient.get("/api/tracks/count", options);
}

/** Full metadata for a single track, used when the editor needs authoritative genres. */
export async function getTrack(trackId, options) {
  const data = await apiClient.get(`/api/tracks/${trackId}`, options);
  return normalizeTrack(data, { metadataComplete: true });
}

/**
 * Resolve many tracks by id, in the order asked for. Used to rebuild a saved playback
 * queue after a reload, now that the whole library is no longer held in memory.
 */
export async function getTracksByIds(ids, options) {
  if (!ids || ids.length === 0) {
    return [];
  }

  const data = await apiClient.get("/api/tracks/by-ids", {
    ...options,
    params: { ids: ids.slice(0, 500).join(",") },
  });

  return normalizeTracks(data, { metadataComplete: true });
}

/** Every track for one artist. Exact, case-insensitive match on the credited artists. */
export async function getArtistTracks(artistName, options) {
  const data = await apiClient.get(
    `/api/artists/${encodeURIComponent(artistName)}/tracks`,
    options,
  );

  return normalizeTracks(data, { metadataComplete: true });
}

/** Every track on one album. */
export async function getAlbumTracks(albumName, options) {
  const data = await apiClient.get(
    `/api/albums/${encodeURIComponent(albumName)}/tracks`,
    options,
  );

  return normalizeTracks(data, { metadataComplete: true });
}

/** Genre tracks are paginated server-side and carry a per-track play count. */
export async function getGenreTracks(genreName, { limit = 100, offset = 0, signal } = {}) {
  const data = await apiClient.get(
    `/api/genres/${encodeURIComponent(genreName)}/tracks`,
    { params: { limit, offset }, signal },
  );

  return {
    items: normalizeTracks(data.items, { metadataComplete: false }),
    total: data.total,
    offset: data.offset,
    hasMore: data.has_more,
  };
}

/** The URL the audio element points at. Auth rides on the session cookie. */
export function streamUrl(trackId) {
  return `${API_BASE_URL}/api/tracks/${trackId}/stream`;
}

/**
 * `PATCH /api/tracks/{id}` is a full replace, not a merge: any field omitted is written
 * as null, and a `genres` array replaces every genre row for the track. `genres` is only
 * sent when the caller actually holds authoritative genre data.
 */
export async function updateTrack(trackId, { title, artist, album, genres }) {
  const payload = { title, artist: artist || null, album: album || null };

  if (genres !== undefined) {
    payload.genres = genres;
  }

  const data = await apiClient.patch(`/api/tracks/${trackId}`, payload);
  return normalizeTrack(data, { metadataComplete: true });
}

export function purgeTracks() {
  return apiClient.delete("/api/tracks/purge");
}

export async function getSimilarTracks(trackId, options) {
  const data = await apiClient.get(`/api/tracks/${trackId}/similar`, options);
  return normalizeTracks(data, { metadataComplete: true });
}

export function updateNowPlaying(trackId) {
  return apiClient.post(`/api/tracks/${trackId}/lastfm/now-playing`);
}

export function scrobble(trackId) {
  return apiClient.post(`/api/tracks/${trackId}/lastfm/scrobble`);
}
