import { artworkUrl } from "../config";
import { isLikedSongsPlaylist } from "./playlists";

const GRADIENT_CLASSES = [
  "playlist-art--gradient-1",
  "playlist-art--gradient-2",
  "playlist-art--gradient-3",
  "playlist-art--gradient-4",
  "playlist-art--gradient-5",
  "playlist-art--gradient-6",
];

/** Album artwork is cached under a trimmed name; keep the key derivation in one place. */
export function getAlbumKey(albumName) {
  return (albumName || "").trim();
}

export function getInitials(name) {
  if (!name) {
    return "♪";
  }

  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() || "")
    .join("");
}

/** Stable per-name gradient so the same album always gets the same generated art. */
export function getGradientClass(name) {
  let hash = 0;

  for (let index = 0; index < (name || "").length; index += 1) {
    hash = name.charCodeAt(index) + ((hash << 5) - hash);
  }

  return GRADIENT_CLASSES[Math.abs(hash) % GRADIENT_CLASSES.length];
}

/**
 * Artwork descriptors are either a real image or a generated initials tile. Returning a
 * discriminated object lets callers resolve artwork once per row instead of twice.
 */
function generated(name) {
  return {
    type: "generated",
    initials: getInitials(name),
    gradientClass: getGradientClass(name),
  };
}

export function resolveAlbumArtwork(albumName, artworkMap) {
  const path = artworkMap[getAlbumKey(albumName)];

  if (path) {
    return { type: "image", src: artworkUrl(path) };
  }

  return generated(albumName);
}

export function resolvePlaylistArtwork(playlist) {
  if (isLikedSongsPlaylist(playlist)) {
    return { type: "image", src: "/ducking-good.png" };
  }

  if (playlist.artwork_path) {
    return { type: "image", src: artworkUrl(playlist.artwork_path) };
  }

  return generated(playlist.name);
}
