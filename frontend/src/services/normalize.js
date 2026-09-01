/**
 * The API returns tracks in four different shapes depending on the endpoint.
 *
 *   GET /api/tracks                      full: genres, artists and artwork populated
 *   GET /api/mobile/.../tracks           full
 *   GET /api/playlists/{id}/tracks       raw ORM rows: genres [], artists [], artwork null
 *   GET /api/tracks/{id}/similar         raw ORM rows
 *   GET /api/stats/...                   genres and artists, but never artwork
 *
 * Components used to consume all four as if they were the same object, which is how a
 * track edited from a playlist could have its genres wiped: the form seeded an empty
 * genre list from a response that never carried one, and `PATCH /api/tracks/{id}`
 * replaces rather than merges.
 *
 * `metadataComplete` records whether the source endpoint actually populates genres and
 * artists, so callers can tell "this track has no genres" apart from "this response
 * doesn't carry genres".
 */
export function normalizeTrack(raw, { metadataComplete = false } = {}) {
  if (!raw) {
    return null;
  }

  return {
    id: raw.id,
    title: raw.title ?? "",
    artist: raw.artist ?? null,
    album: raw.album ?? null,
    genre: raw.genre ?? null,
    genres: raw.genres ?? [],
    artists: raw.artists ?? [],
    file_path: raw.file_path ?? null,
    artwork_path: raw.artwork_path ?? null,
    album_artwork_path: raw.album_artwork_path ?? null,
    artist_artwork_path: raw.artist_artwork_path ?? null,
    raw_title: raw.raw_title ?? null,
    raw_artist: raw.raw_artist ?? null,
    raw_album: raw.raw_album ?? null,
    raw_genre: raw.raw_genre ?? null,
    musicbrainz_recording_id: raw.musicbrainz_recording_id ?? null,
    lastfm_tags_enriched: raw.lastfm_tags_enriched ?? false,
    metadataComplete,
    // Recommendation responses attach an explanation object; keep it when present.
    ...(raw.debug ? { debug: raw.debug } : {}),
  };
}

export function normalizeTracks(rawList, options) {
  if (!Array.isArray(rawList)) {
    return [];
  }

  return rawList.map((raw) => normalizeTrack(raw, options)).filter(Boolean);
}
