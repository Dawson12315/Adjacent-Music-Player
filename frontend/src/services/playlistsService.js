import { apiClient } from "./apiClient";
import { normalizeTracks } from "./normalize";

/**
 * Note: `GET /api/playlists` and `GET /api/playlists/liked-songs` create the user's
 * system playlist as a side effect, so neither can be treated as a cacheable read.
 */
export function listPlaylists(options) {
  return apiClient.get("/api/playlists", options);
}

export function createPlaylist(name) {
  return apiClient.post("/api/playlists", { name });
}

export function renamePlaylist(playlistId, name) {
  return apiClient.patch(`/api/playlists/${playlistId}`, { name });
}

export function deletePlaylist(playlistId) {
  return apiClient.delete(`/api/playlists/${playlistId}`);
}

/**
 * Declared as list[TrackResponse] but returns raw ORM rows, so genres, artists and
 * every artwork field come back empty regardless of the underlying data.
 */
export async function getPlaylistTracks(playlistId, options) {
  const data = await apiClient.get(`/api/playlists/${playlistId}/tracks`, options);
  return normalizeTracks(data, { metadataComplete: false });
}

export function addTrackToPlaylist(playlistId, trackId) {
  return apiClient.post(`/api/playlists/${playlistId}/tracks`, { track_id: trackId });
}

export function removeTrackFromPlaylist(playlistId, trackId) {
  return apiClient.delete(`/api/playlists/${playlistId}/tracks/${trackId}`);
}

/** Admin only, and rejected outright for system playlists. */
export function uploadPlaylistArtwork(playlistId, file) {
  const formData = new FormData();
  formData.append("file", file);

  return apiClient.post(`/api/playlists/${playlistId}/artwork`, formData);
}

export function getLikedSongsPlaylist(options) {
  return apiClient.get("/api/playlists/liked-songs", options);
}

export async function isTrackLiked(trackId, options) {
  const data = await apiClient.get(
    `/api/playlists/liked-songs/tracks/${trackId}`,
    options,
  );

  return Boolean(data.liked);
}

export async function likeTrack(trackId) {
  const data = await apiClient.post("/api/playlists/liked-songs/tracks", {
    track_id: trackId,
  });

  return Boolean(data.liked);
}

export async function unlikeTrack(trackId) {
  const data = await apiClient.delete(`/api/playlists/liked-songs/tracks/${trackId}`);
  return Boolean(data.liked);
}
