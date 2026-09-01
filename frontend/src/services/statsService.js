import { apiClient } from "./apiClient";
import { normalizeTracks } from "./normalize";

/**
 * The `-detailed` endpoints return the play/like/skip counters alongside each track.
 *
 * The original endpoints join TrackUserStats, order by play_count, and then discard it —
 * which is why the insights page could only ever show the *length* of each list.
 */
function withStats(rawList) {
  const tracks = normalizeTracks(rawList, { metadataComplete: true });

  return tracks.map((track, index) => ({
    ...track,
    play_count: rawList[index]?.play_count ?? 0,
    skip_count: rawList[index]?.skip_count ?? 0,
    completion_count: rawList[index]?.completion_count ?? 0,
    like_count: rawList[index]?.like_count ?? 0,
    last_played_at: rawList[index]?.last_played_at ?? null,
  }));
}

async function detailed(path, limit, signal) {
  const data = await apiClient.get(path, { params: { limit }, signal });
  return withStats(data);
}

export const getTopPlayed = (limit, signal) =>
  detailed("/api/stats/top-played-detailed", limit, signal);

export const getMostLiked = (limit, signal) =>
  detailed("/api/stats/most-liked-detailed", limit, signal);

export const getMostSkipped = (limit, signal) =>
  detailed("/api/stats/most-skipped-detailed", limit, signal);

export const getRecentlyPlayed = (limit, signal) =>
  detailed("/api/stats/recently-played-detailed", limit, signal);

/** Headline totals, rates and streaks. */
export function getSummary(options) {
  return apiClient.get("/api/stats/summary", options);
}

export function getPlaysOverTime({ days = 30, signal } = {}) {
  return apiClient.get("/api/stats/plays-over-time", { params: { days }, signal });
}

export function getTopArtists({ limit = 10, signal } = {}) {
  return apiClient.get("/api/stats/top-artists", { params: { limit }, signal });
}

export function getTopAlbums({ limit = 10, signal } = {}) {
  return apiClient.get("/api/stats/top-albums", { params: { limit }, signal });
}

/**
 * Where listening starts from — library, playlist, artist, album, recommendation.
 * `source_type` has been recorded on every event since the beginning and was never
 * queried by anything.
 */
export function getBySource(options) {
  return apiClient.get("/api/stats/by-source", options);
}

export function getByHour(options) {
  return apiClient.get("/api/stats/by-hour", options);
}

/** The original overview, still used for its top_genres aggregate. */
export async function getStatsOverview(options) {
  const data = await apiClient.get("/api/stats/overview", options);

  return {
    top_played: normalizeTracks(data.top_played, { metadataComplete: true }),
    most_liked: normalizeTracks(data.most_liked, { metadataComplete: true }),
    most_skipped: normalizeTracks(data.most_skipped, { metadataComplete: true }),
    recently_played: normalizeTracks(data.recently_played, { metadataComplete: true }),
    top_genres: data.top_genres || [],
  };
}
