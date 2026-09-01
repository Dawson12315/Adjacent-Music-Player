import { artworkUrl } from "../config";
import { isLikedSongsPlaylist } from "./playlists";

/**
 * Ten tones on a single arc from Adjacent Blue through indigo and violet into Duck
 * Yellow. This is not a fallback style: 7 of 4,240 albums in a real library have cover
 * art, so the generated tile is what the app looks like 99.8% of the time.
 */
const TONE_COUNT = 10;

/**
 * The artwork maps from `/api/albums/artwork` and `/api/artists/artwork` are keyed by
 * the backend's *normalized* names, not display names. These two mirror the Python
 * normalizers (`normalize_album_name`, `normalize_artist_name`) — look up with a raw
 * display name and every "AC/DC" or "Awaken, My Love!" silently misses its photo.
 */
export function getAlbumKey(albumName) {
  // Python: " ".join(name.strip().casefold().split())
  return (albumName || "").trim().toLowerCase().split(/\s+/).join(" ");
}

export function getArtistKey(artistName) {
  if (!artistName) {
    return "";
  }

  return (
    artistName
      .trim()
      .normalize("NFKC")
      .toLowerCase()
      .replaceAll("&", " and ")
      .replace(/[‘’`´]/g, "'")
      .replace(/[.\-_/]+/g, " ")
      // Python's \w is unicode-aware; \p{L}\p{N}_ is the JS equivalent.
      .replace(/[^\p{L}\p{N}_\s']/gu, " ")
      .replace(/\s+/g, " ")
      .trim()
  );
}

/** The header hero needs the raw path (not a descriptor) for its backdrop image. */
export function getArtistArtworkPath(artistName, artworkMap) {
  return artworkMap?.[getArtistKey(artistName)] || null;
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
  const path = getArtistArtworkPath(artistName, artworkMap);

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
