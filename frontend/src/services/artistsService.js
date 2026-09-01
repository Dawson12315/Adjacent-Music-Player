import { apiClient } from "./apiClient";

/**
 * Artist names are path segments on the backend (`{artist_name:path}`), so they are
 * encoded on the way out. Names containing slashes are why that route uses `:path`.
 */
const encode = (name) => encodeURIComponent(name);

/** Bare string array, sourced from track_artists so it includes featured artists. */
export function listArtists(options) {
  return apiClient.get("/api/artists", options);
}

/**
 * Matches on `tracks.artist` exactly and case-sensitively, unlike most artist lookups.
 * An artist reachable elsewhere can legitimately return an empty list here.
 */
export function getArtistGenres(artistName, options) {
  return apiClient.get(`/api/artists/${encode(artistName)}/genres`, options);
}

/** The whole artist-artwork lookup table in one request, keyed by artist key. */
export async function getAllArtistArtwork(options) {
  const data = await apiClient.get("/api/artists/artwork", options);
  return data.artwork || {};
}

/** Always 200; `artwork_path` is null when the artist has no artwork. */
export function getArtistArtwork(artistName, options) {
  return apiClient.get(`/api/artists/${encode(artistName)}/artwork`, options);
}

export function uploadArtistArtwork(artistName, file) {
  const formData = new FormData();
  formData.append("file", file);

  return apiClient.post(`/api/artists/${encode(artistName)}/artwork`, formData);
}

/** Admin only. Updates `tracks.artist` but not `track_artists` or stored artwork keys. */
export function renameArtist(currentArtist, newArtist) {
  return apiClient.patch("/api/artists/rename", {
    current_artist: currentArtist,
    new_artist: newArtist,
  });
}

/** Admin only. Both artists must already exist. */
export function transferArtist(sourceArtist, targetArtist) {
  return apiClient.patch("/api/artists/transfer", {
    source_artist: sourceArtist,
    target_artist: targetArtist,
  });
}
