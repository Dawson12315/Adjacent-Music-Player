import { apiClient } from "./apiClient";

const encode = (name) => encodeURIComponent(name);

/** Bare string array of album names. */
export function listAlbums(options) {
  return apiClient.get("/api/albums", options);
}

/**
 * The whole album-artwork lookup table in one request, keyed by album key.
 *
 * Replaces one HTTP request per album. The albums page used to fire 80 on open, and with
 * 7 artworks in a 4,240-album library, 79 of them returned null.
 */
export async function getAllAlbumArtwork(options) {
  const data = await apiClient.get("/api/albums/artwork", options);
  return data.artwork || {};
}

/** Always 200; `artwork_path` is null when the album has no artwork. */
export function getAlbumArtwork(albumName, options) {
  return apiClient.get(`/api/albums/${encode(albumName)}/artwork`, options);
}

export function uploadAlbumArtwork(albumName, file) {
  const formData = new FormData();
  formData.append("file", file);

  return apiClient.post(`/api/albums/${encode(albumName)}/artwork`, formData);
}
