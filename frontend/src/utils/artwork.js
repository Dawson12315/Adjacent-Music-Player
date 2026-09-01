import { artworkUrl } from "../config";
import { isLikedSongsPlaylist } from "./playlists";

/**
 * Ten tones on a single arc from Adjacent Blue through indigo and violet into Duck
 * Yellow. This is not a fallback style: 7 of 4,240 albums in a real library have cover
 * art, so the generated tile is what the app looks like 99.8% of the time.
 */
const TONE_COUNT = 10;

/** Album artwork is cached under a trimmed name; keep the key derivation in one place. */
export function getAlbumKey(albumName) {
  return (albumName || "").trim();
}

export function getInitials(name) {
  if (!name) {
    return "♪";
  }

  return (
    name
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((word) => word[0]?.toUpperCase() || "")
      .join("") || "♪"
  );
}

/**
 * Stable per-name tone, so the same album always gets the same tile. djb2-style hash;
 * the absolute value guards against the sign flip on long names.
 */
export function getTone(name) {
  let hash = 0;

  for (let index = 0; index < (name || "").length; index += 1) {
    hash = name.charCodeAt(index) + ((hash << 5) - hash);
    hash |= 0;
  }

  return (Math.abs(hash) % TONE_COUNT) + 1;
}

/**
 * Artwork descriptors are either a real image or a generated tile. Returning one shape
 * lets callers resolve artwork once per row instead of testing and reading separately.
 */
function generated(name) {
  return {
    type: "generated",
    initials: getInitials(name),
    tone: getTone(name),
  };
}

export function resolveAlbumArtwork(albumName, artworkMap) {
  const path = artworkMap?.[getAlbumKey(albumName)];

  if (path) {
    return { type: "image", src: artworkUrl(path), alt: albumName || "" };
  }

  return generated(albumName);
}

export function resolveArtistArtwork(artistName, artworkMap) {
  const path = artworkMap?.[artistName];

  if (path) {
    return { type: "image", src: artworkUrl(path), alt: artistName || "" };
  }

  return generated(artistName);
}

export function resolvePlaylistArtwork(playlist) {
  if (isLikedSongsPlaylist(playlist)) {
    return { type: "duck", alt: playlist.name };
  }

  if (playlist.artwork_path) {
    return { type: "image", src: artworkUrl(playlist.artwork_path), alt: playlist.name };
  }

  return generated(playlist.name);
}
