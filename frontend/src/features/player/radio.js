/**
 * Radio in the browser, the pure parts.
 *
 * A station plays under the `radio` source with the station's id as the
 * source id, so every play is recorded against it, the end of the queue
 * asks the station for more rather than stopping, and the player bar can
 * name the station.
 */

import { RADIO_API_VERSION, RADIO_FEEDBACK_API_VERSION } from "../../services/radioService";

export const RADIO_SOURCE_TYPE = "radio";

/** The playback source a station plays under. */
export function radioSource(stationId) {
  return { source_type: RADIO_SOURCE_TYPE, source_id: stationId ?? null };
}

export function isRadioSource(source) {
  return source?.source_type === RADIO_SOURCE_TYPE && source?.source_id != null;
}

/** Whether the server has radio at all, and whether it takes feedback. */
export function radioAvailableFor({ apiVersion = 0, capabilities = [] } = {}) {
  return apiVersion >= RADIO_API_VERSION || (Array.isArray(capabilities) && capabilities.includes("radio"));
}

export function radioFeedbackAvailableFor({ apiVersion = 0 } = {}) {
  return apiVersion >= RADIO_FEEDBACK_API_VERSION;
}

/** How many tracks are left to play when the station is asked for more. */
export const REFILL_AHEAD = 3;

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

/**
 * Whether a reason says the station reached past the seed's own corner —
 * shown quieter than "Close to Fen", so the listener can tell the two apart.
 */
export function isWideReason(reason) {
  const text = String(reason || "");
  return (
    text.startsWith("Back around to") ||
    text.startsWith("Shares a genre with") ||
    text.startsWith("Further afield from") ||
    text.startsWith("From what you play most") ||
    text.startsWith("Somewhere else in your library")
  );
}

/** One notice per station, when a batch had to reach wider than the seed. */
export function reachNotice(reach, seedName) {
  const name = seedName || "this seed";
  switch (reach) {
    case "again":
      return `${name}'s corner of your library has all played; the station is coming back round.`;
    case "library":
      return `Your library is thin around ${name}; the station is reaching across all of it.`;
    case "listener":
      return `Your library is thin around ${name}; the station is reaching into what you play most.`;
    case "artist":
    case "genre":
    default:
      return `Your library is thin around ${name}; the station is reaching a little wider.`;
  }
}

/** What the listener has said about a track on this station. */
export function feedbackState(feedback, track) {
  const artist = String(track?.artist || "").toLowerCase();
  return {
    more: Boolean(track?.id != null && feedback?.more_track_ids?.includes(track.id)),
    less: Boolean(track?.id != null && feedback?.less_track_ids?.includes(track.id)),
    lessArtist: Boolean(
      artist && (feedback?.less_artists || []).some((name) => String(name).toLowerCase() === artist),
    ),
  };
}

/** The line under a station's name: kind, place, and whether more is coming. */
export function stationLine({ kind, position = 0, total = 0, live = false, isLoop = false } = {}) {
  const parts = [kind];
  if (total > 0) parts.push(`${position} of ${total}`);
  if (live) parts.push(isLoop ? "repeat is on, so nothing more arrives" : "more arrives as it plays");
  return parts.join(" · ");
}

/** Other parts of the app learn that the station list changed (a delete, a start). */
export const STATIONS_CHANGED_EVENT = "adjacent:stations-changed";

export function announceStationsChanged() {
  if (typeof window !== "undefined" && typeof window.dispatchEvent === "function") {
    window.dispatchEvent(new Event(STATIONS_CHANGED_EVENT));
  }
}

export const EXHAUSTED_STATION_NOTICE = "That station has played everything it can find for now.";
export const RADIO_UNAVAILABLE_NOTICE = "Radio needs a newer Adjacent server.";
export const STATION_GONE_NOTICE = "That station is gone: its seed is no longer in your library.";
