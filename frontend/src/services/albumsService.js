import { apiClient } from "./apiClient";

const encode = (name) => encodeURIComponent(name);

/** Bare string array of album names. */
export function listAlbums(options) {
  return apiClient.get("/api/albums", options);
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
