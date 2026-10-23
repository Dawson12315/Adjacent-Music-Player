/**
 * Radio in the browser, the pure parts.
 *
 * A station plays under the `radio` source with the station's id as the
 * source id, so every play is recorded against it, the end of the queue
 * asks the station for more rather than stopping, and the player bar can
 * name the station.
 */

export const RADIO_SOURCE_TYPE = "radio";

/** The playback source a station plays under. */
export function radioSource(stationId) {
  return { source_type: RADIO_SOURCE_TYPE, source_id: stationId ?? null };
}

export function isRadioSource(source) {
  return source?.source_type === RADIO_SOURCE_TYPE && source?.source_id != null;
}

/** The seed payload for a station from a track, an album or an artist. */
export function stationSeedFor({ track = null, album = null, artist = null } = {}) {
  if (track?.id != null) return { seed_type: "track", seed_track_id: track.id };
  if (album?.name) {
    return {
      seed_type: "album",
      seed_album: album.name,
      seed_album_artist: album.artist || album.album_artist || null,
    };
  }
  if (typeof artist === "string" ? artist : artist?.name) {
    return { seed_type: "artist", seed_artist: typeof artist === "string" ? artist : artist.name };
  }
  return null;
}

/** "Track radio", "Album radio", "Artist radio": the kind, for a station card. */
export function stationKindLabel(station) {
  switch (station?.seed_type) {
    case "track":
      return "Track radio";
    case "album":
      return "Album radio";
    case "artist":
      return "Artist radio";
    default:
      return "Radio";
  }
}

/** The name the seed has, without the " radio" the server appends. */
export function stationSeedName(station) {
  const name = String(station?.name || "");
  return name.endsWith(" radio") ? name.slice(0, -" radio".length) : name;
}

/**
 * A batch worth playing: each track once, in the station's order, and
 * none that the browser has just played.
 */
export function stationBatchCandidates(tracks, { excludeIds = new Set() } = {}) {
  const seen = new Set();
  const excluded = new Set([...excludeIds].map(String));

  return (Array.isArray(tracks) ? tracks : []).filter((track) => {
    const id = track?.id;
    if (id == null) return false;
    const key = String(id);
    if (excluded.has(key) || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/** The reasons a batch came with, keyed by track id, for the player's line. */
export function reasonsByTrackId(tracks) {
  const reasons = new Map();
  (Array.isArray(tracks) ? tracks : []).forEach((track) => {
    if (track?.id != null && track.reason) reasons.set(String(track.id), track.reason);
  });
  return reasons;
}

export const THIN_STATION_NOTICE =
  "Your library is small for this station, so it will repeat before long.";
export const EXHAUSTED_STATION_NOTICE = "That station has played everything it can find for now.";
